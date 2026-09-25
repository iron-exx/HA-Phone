"""Doorbell rings phones of people who are away only when nobody is at home."""
import httpx
import pytest

from backend import ha_presence
from backend.models import RingGroup
from backend.routers.time_conditions import _build_dial_string

M = {"13": "person.sandro", "14": "person.larissa"}


def test_someone_home_leaves_out_the_away_phones():
    assert ha_presence.excluded_extensions(M, {"person.sandro": "not_home", "person.larissa": "home"}) == {"13"}


def test_nobody_home_rings_everyone():
    assert ha_presence.excluded_extensions(M, {"person.sandro": "not_home", "person.larissa": "work"}) == frozenset()


def test_unknown_state_never_silences_a_phone():
    assert ha_presence.excluded_extensions(M, {"person.sandro": None, "person.larissa": "home"}) == frozenset()
    assert ha_presence.excluded_extensions(M, {"person.sandro": "unavailable", "person.larissa": "home"}) == frozenset()


def test_zone_other_than_home_counts_as_away():
    assert ha_presence.excluded_extensions(M, {"person.sandro": "Büro", "person.larissa": "home"}) == {"13"}


def test_dial_string_skips_excluded_extensions():
    rg = RingGroup(name="klingel", extension_numbers="11,13,14")
    filtered = _build_dial_string(rg, exclude={"13"})
    assert "PJSIP/11" in filtered and "PJSIP/14" in filtered and "PJSIP/13" not in filtered
    assert "PJSIP/13" in _build_dial_string(rg)


@pytest.mark.asyncio
async def test_fetch_states_via_supervisor(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok")

    def handler(req):
        assert req.headers["authorization"] == "Bearer tok"
        if req.url.path.endswith("person.sandro"):
            return httpx.Response(200, json={"state": "home"})
        return httpx.Response(404)
    states = await ha_presence.fetch_states({"person.sandro", "person.gone"}, transport=httpx.MockTransport(handler))
    assert states == {"person.sandro": "home", "person.gone": None}


def test_ha_person_is_validated(client):
    resp = None
    for number in range(99, 9, -1):
        resp = client.post("/api/extensions", json={"number": number, "display_name": "P", "sip_password": "securepass1234567"})
        if resp.status_code in (200, 201):
            break
    ext_id = resp.json()["id"]
    try:
        assert client.patch(f"/api/extensions/{ext_id}", json={"ha_person": "Person Sandro"}).status_code == 422
        ok = client.patch(f"/api/extensions/{ext_id}", json={"ha_person": "person.sandro"})
        assert ok.status_code == 200 and ok.json()["ha_person"] == "person.sandro"
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_home_zone_name_counts_as_home():
    """Real install: people at home report "Zuhause" (zone.home friendly name)."""
    states = {"person.sandro": "not_home", "person.larissa": "Zuhause"}
    home = frozenset({"home", "Zuhause"})
    assert ha_presence.excluded_extensions(M, states, home) == {"13"}
    # Without knowing the zone name, "Zuhause" is away -> nobody home -> everyone rings.
    assert ha_presence.excluded_extensions(M, states) == frozenset()


def test_overlapping_zone_counts_as_home():
    """Real install: zone.home "Home" plus a separate zone.zuhause around the house."""
    zones = [
        {"entity_id": "zone.home", "attributes": {"friendly_name": "Home", "latitude": 52.0, "longitude": 8.0, "radius": 100}},
        {"entity_id": "zone.zuhause", "attributes": {"friendly_name": "Zuhause", "latitude": 52.0005, "longitude": 8.0, "radius": 50}},
        {"entity_id": "zone.buero", "attributes": {"friendly_name": "Büro", "latitude": 52.1, "longitude": 8.1, "radius": 100}},
    ]
    assert ha_presence.home_zone_names(zones) == {"home", "Home", "Zuhause"}
    assert ha_presence.home_zone_names([]) == {"home"}
