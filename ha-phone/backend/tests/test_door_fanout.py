"""Türklingel-Verteiler: a door station ringing a group of several devices gets one leg
per device (Local channel with a single Dial) joined to a ConfBridge, so every device
sees the door's video as early media before answering. app_dial only forwards early
media to a SINGLE callee, which is why a plain group Dial loses the preview."""
import re
from pathlib import Path

import pytest

from backend import doorbell, ha_presence
from backend.routers.time_conditions import dial_target

ADDON = Path(__file__).resolve().parents[2]
NEW_MODULES = (
    "app_confbridge", "app_originate", "app_stack", "res_agi", "res_speech", "func_lock",
    "func_global", "func_frame_drop", "func_cut", "app_exec", "app_userevent",
    "res_timing_timerfd", "chan_bridge_media", "res_pjsip_rfc3326",
)


class Numbers:
    door = audio = video1 = video2 = ""


@pytest.fixture
def setup(client, tmp_data_dir):
    """A door (internal-only), one audio phone and two video phones on free numbers, plus
    a group of the three phones. setup(group_number, members) adds more groups."""
    used = {e["number"] for e in client.get("/api/extensions").json()}
    used |= {g["number"] for g in client.get("/api/ring-groups").json()}
    free = [n for n in range(40, 80) if n not in used]
    made, groups = [], []

    def ext(number, **extra):
        resp = client.post("/api/extensions", json={
            "number": number, "display_name": f"Fanout {number}",
            "sip_password": "securepass1234567", **extra})
        assert resp.status_code == 200, resp.text
        made.append(resp.json()["id"])
        return str(number)

    def group(members, timeout=25):
        number = free.pop()
        resp = client.post("/api/ring-groups", json={
            "number": number, "name": f"Klingel {number}", "extension_numbers": members,
            "ring_timeout": timeout})
        assert resp.status_code == 200, resp.text
        groups.append(resp.json()["id"])
        return number

    try:
        n = Numbers()
        n.door = ext(free.pop(0), is_door=True, internal_only=True)
        n.audio = ext(free.pop(0))
        n.video1 = ext(free.pop(0), video_capable=True)
        n.video2 = ext(free.pop(0), video_capable=True)
        n.group = group(f"{n.audio},{n.video1},{n.video2}")
        n.add_group = group
        yield n
    finally:
        for gid in groups:
            client.delete(f"/api/ring-groups/{gid}")
        for eid in made:
            client.delete(f"/api/extensions/{eid}")


def _routing(tmp_data_dir) -> str:
    return (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()


def _context(routing: str, name: str) -> str:
    return routing.split(f"[{name}]\n")[1].split("\n[")[0]


def _group_entry(context: str, number: int) -> str:
    return context.split(f"exten => {number},1,")[1].split("\nexten =>")[0]


# ── build: modules ──

def test_all_fanout_modules_are_built_and_loaded():
    dockerfile = (ADDON / "Dockerfile").read_text()
    modules = (ADDON / "rootfs/etc/asterisk/modules.conf").read_text()
    for name in NEW_MODULES:
        assert f"--enable {name} " in dockerfile, name
        assert f"load = {name}.so" in modules, name


def test_confbridge_profiles():
    conf = (ADDON / "rootfs/etc/asterisk/confbridge.conf").read_text()
    bridge = conf.split("[haphone_door_bridge]")[1].split("\n[")[0]
    assert "video_mode = first_marked" in bridge
    ringing = conf.split("[haphone_door_ringing]")[1].split("\n[")[0]
    assert "answer_channel = no" in ringing and "marked = yes" in ringing and "quiet = yes" in ringing
    talking = conf.split("[haphone_door_talking]")[1].split("\n[")[0]
    assert "marked = yes" in talking and "answer_channel" not in talking
    leg = conf.split("[haphone_door_leg]")[1].split("\n[")[0]
    assert "dtmf_passthrough = yes" in leg and "quiet = yes" in leg and "startmuted" not in leg


# ── dialplan ──

def test_door_ringing_a_group_uses_the_fanout_in_both_contexts(setup, tmp_data_dir):
    n = setup
    routing = _routing(tmp_data_dir)
    for ctx in ("from-internal-restricted", "from-internal"):
        entry = _group_entry(_context(routing, ctx), n.group)
        # Only a door's own endpoint takes the fanout (caller id could be faked).
        doors = re.search(r'GotoIf\(\$\[\$\{REGEX\("\^\(([0-9|]+)\)\$" \$\{CHANNEL\(endpoint\)\}\)\}\]\?door\)', entry)
        assert doors and n.door in doors.group(1).split("|"), ctx
        assert f"n(door),Gosub(haphone-door-fanout,s,1({n.audio}&{n.video1}&{n.video2},25))" in entry, ctx
        # Everybody else keeps the plain group Dial (every device of every member).
        assert f"Dial({dial_target(n.audio)}&{dial_target(n.video1)}&{dial_target(n.video2)},25)" in entry, ctx
        # Every step is its own dialplan line (a collapsed single line would be one broken command).
        assert "\n same => n(door),Gosub(haphone-door-fanout," in entry, ctx
        assert entry.count("\n same => n") >= 4, ctx


def test_single_member_group_uses_the_fanout_too(setup, tmp_data_dir):
    """One extension can still be several devices (app + desk phone): each needs its own leg."""
    number = setup.add_group(setup.video1)
    entry = _group_entry(_context(_routing(tmp_data_dir), "from-internal-restricted"), number)
    assert f"Gosub(haphone-door-fanout,s,1({setup.video1},25))" in entry


def test_door_calling_one_extension_directly_uses_the_fanout(setup, tmp_data_dir):
    restricted = _context(_routing(tmp_data_dir), "from-internal-restricted")
    for number in (setup.audio, setup.video1):
        entry = _group_entry(restricted, number)
        assert f"Gosub(haphone-door-fanout,s,1({number},30))" in entry
        assert f"Dial({dial_target(number)},30)" in entry  # everybody else: all devices ring


def test_presence_rule_applies_to_the_fanout(setup, tmp_data_dir, monkeypatch):
    n = setup
    monkeypatch.setattr(ha_presence, "door_excluded", frozenset({n.video2}))
    number = n.add_group(f"{n.audio},{n.video1},{n.video2}")  # regenerates the dialplan
    entry = _group_entry(_context(_routing(tmp_data_dir), "from-internal-restricted"), number)
    assert f"Gosub(haphone-door-fanout,s,1({n.audio}&{n.video1},25))" in entry


def test_presence_rule_down_to_one_phone_still_fans_out(setup, tmp_data_dir, monkeypatch):
    n = setup
    monkeypatch.setattr(ha_presence, "door_excluded", frozenset({n.audio, n.video2}))
    number = n.add_group(f"{n.audio},{n.video1},{n.video2}")
    entry = _group_entry(_context(_routing(tmp_data_dir), "from-internal-restricted"), number)
    assert f"Gosub(haphone-door-fanout,s,1({n.video1},25))" in entry


def test_the_door_itself_is_never_a_fanout_target(setup, tmp_data_dir):
    n = setup
    number = n.add_group(f"{n.door},{n.video1},{n.video2}")
    entry = _group_entry(_context(_routing(tmp_data_dir), "from-internal-restricted"), number)
    assert f"Gosub(haphone-door-fanout,s,1({n.video1}&{n.video2},25))" in entry


def test_one_leg_entry_per_extension_dials_one_contact(setup, tmp_data_dir):
    n = setup
    legs = _context(_routing(tmp_data_dir), "haphone-door-leg")
    for number in (n.audio, n.video1):
        entry = legs.split(f"exten => {number},1,")[1].split("\nexten =>")[0]
        assert entry.startswith(f"Set(HAPHONE_DOOR_TARGET=PJSIP/{number})")
        # the HAPHONE_DOOR_CONTACT-th registered contact, never IF()/ExecIf with a URI
        assert f"Set(HAPHONE_DOOR_CS=${{PJSIP_DIAL_CONTACTS({number})}})" in entry
        assert "CUT(HAPHONE_DOOR_CS,&,${HAPHONE_DOOR_CONTACT})" in entry
        code = "\n".join(line for line in entry.splitlines() if not line.lstrip().startswith(";"))
        assert "IF(" not in code.replace("GotoIf(", "")
    assert f"exten => {n.door}," not in legs  # the door itself is never a leg
    assert " same => n(go),Goto(haphone-door-ring,s,1)" in legs


def test_fanout_originates_one_leg_per_contact(setup, tmp_data_dir):
    fanout = _context(_routing(tmp_data_dir), "haphone-door-fanout")
    assert "PJSIP_DIAL_CONTACTS(${target})" in fanout
    assert "^HAPHONE_DOOR_CONTACT=${j}))" in fanout
    assert "Set(SHARED(DOOR_LEGS)=${legs})" in fanout
    # the leg count is final before the first leg can fail
    assert fanout.index("Set(SHARED(DOOR_LEGS)=${legs})") < fanout.index("Originate(")


def test_fanout_dialplan_avoids_unbuilt_apps(setup, tmp_data_dir):
    routing = _routing(tmp_data_dir)
    assert "While(" not in routing  # app_while is not built
    for ctx in ("haphone-door-fanout", "haphone-door-ring", "haphone-door-win", "haphone-door-join"):
        commands = [l for l in _context(routing, ctx).splitlines() if not l.lstrip().startswith(";")]
        assert not any(";" in l for l in commands), ctx  # ';' would cut the line (comment)


def test_static_fanout_contexts(setup, tmp_data_dir):
    routing = _routing(tmp_data_dir)
    fanout = _context(routing, "haphone-door-fanout")
    # One Local leg per device; h264 in the codecs, or the Local channel drops the video.
    assert "Originate(Local/${target}@haphone-door-leg/n,exten,haphone-door-join,s,1,${ARG2},aC(alaw,ulaw,g722,h264)" in fanout
    assert "Progress()" in fanout and "CONFBRIDGE(user,template)=haphone_door_ringing" in fanout
    assert "Hangup(19)" in fanout  # nobody answered: 480 to the door
    win = _context(routing, "haphone-door-win")
    assert "LOCK(" in win and "GOSUB_RESULT=ABORT" in win and "FRAME_DROP(RX)=NONE" in win
    # Kicking everybody would tear the conference down under the winner.
    assert "ConfKick(${ARG1},all)" not in win
    assert "UserEvent(HaPhoneDoorAnswered," in win
    ring = _context(routing, "haphone-door-ring")
    assert "b(haphone-door-predial^s^1)" in ring and "U(haphone-door-win^" in ring
    assert "CALLERID(num)=${SHARED(DOOR_CIDNUM,${HAPHONE_DOOR_CHAN})}" in ring
    assert "Set(FRAME_DROP(RX)=VOICE,DTMF_BEGIN,DTMF_END)" in _context(routing, "haphone-door-predial")
    assert "Hangup(26)" in _context(routing, "haphone-door-join")


# ── doorbell history ──

def _ring(t):
    t.on_event({"Event": "Newchannel", "Channel": "PJSIP/17-0001", "Uniqueid": "1.1",
                "CallerIDNum": "17", "Exten": "20"})


def test_fanout_answer_comes_from_the_userevent():
    t = doorbell.DoorbellTracker(lambda n: n == "17")
    _ring(t)
    # A leg's own DialEnd belongs to the Local channel, not to the door.
    assert t.on_event({"Event": "DialEnd", "Uniqueid": "1.5", "DialStatus": "ANSWER",
                       "DestCallerIDNum": "12"}) == []
    answered = {"Event": "UserEvent", "UserEvent": "HaPhoneDoorAnswered",
                "DoorUniqueid": "1.1", "By": "12"}
    assert t.on_event(answered) == [doorbell.Answered("1.1", "12")]
    assert t.on_event(dict(answered, By="13")) == []
    assert t.on_event({"Event": "UserEvent", "UserEvent": "HaPhoneDoorAnswered",
                       "DoorUniqueid": "9.9", "By": "12"}) == []


def test_leg_events_map_to_the_door():
    t = doorbell.DoorbellTracker(lambda n: n == "17")
    _ring(t)
    t.on_event({"Event": "UserEvent", "UserEvent": "HaPhoneDoorLeg", "Uniqueid": "1.5",
                "DoorUniqueid": "1.1"})
    assert t.door_of("1.5") == "1.1"
    assert t.door_of("1.1") == "1.1"
    assert t.door_of("7.7") is None
    t.on_event({"Event": "Hangup", "Uniqueid": "1.1"})
    assert t.door_of("1.5") is None


def test_listener_logs_fanout_legs(client, caplog):
    from backend.doorbell_listener import DoorbellListener
    listener = DoorbellListener(fetch=None)
    listener.tracker = doorbell.DoorbellTracker(lambda n: n == "17")
    _ring(listener.tracker)
    listener.handle({"Event": "UserEvent", "UserEvent": "HaPhoneDoorLeg", "Uniqueid": "1.5",
                     "DoorUniqueid": "1.1"})
    with caplog.at_level("INFO", logger="backend.doorbell_listener"):
        listener.handle({"Event": "DialBegin", "Uniqueid": "1.5", "DestChannel": "PJSIP/12-0004",
                         "DialString": "PJSIP/12"})
    assert "dialing PJSIP/12-0004" in caplog.text


def test_leg_log_uses_asterisk_time_and_shows_listener_lag(client, caplog, monkeypatch):
    """With timestampevents the offsets are Asterisk's own clock, not when Python got
    around to the event (on a busy box the listener lagged ~3 s behind the real call)."""
    from backend import doorbell_listener as dl
    assert "timestampevents = yes" in (ADDON / "rootfs/etc/asterisk/manager.conf").read_text()
    listener = dl.DoorbellListener(fetch=None)
    listener.tracker = doorbell.DoorbellTracker(lambda n: n == "17")
    monkeypatch.setattr(dl.time, "time", lambda: 1000.0 + 3.5)
    listener.handle({"Event": "Newchannel", "Uniqueid": "9.1", "Linkedid": "9.1", "CallerIDNum": "17",
                     "Channel": "PJSIP/17-0009", "Exten": "20", "Timestamp": "1000.000000"})
    listener.handle({"Event": "UserEvent", "UserEvent": "HaPhoneDoorLeg", "Uniqueid": "9.5",
                     "DoorUniqueid": "9.1", "Timestamp": "1000.050000"})
    with caplog.at_level("INFO", logger="backend.doorbell_listener"):
        listener.handle({"Event": "DialBegin", "Uniqueid": "9.5", "DestChannel": "PJSIP/12-0009",
                         "DialString": "PJSIP/12", "Timestamp": "1000.120000"})
    assert "at +0.1 s" in caplog.text
    assert "listener 3.4 s behind" in caplog.text
