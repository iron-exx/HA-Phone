"""menuselect --disable-all also drops every sound package; without prompts
VoiceMailMain()/Voicemail() hang up immediately. Guard the explicit re-enables."""
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_asterisk_build_includes_prompts_and_hold_music():
    text = DOCKERFILE.read_text()
    assert "--disable-all" in text
    assert "--enable CORE-SOUNDS-EN-WAV" in text
    assert "--enable MOH-OPSOUND-WAV" in text


def test_german_prompts_are_bundled_with_matching_format_modules():
    text = DOCKERFILE.read_text()
    assert "core-sounds-de" in text and "sha256sum -c" in text
    # format_pcm reads alaw, ulaw AND g722 files; there is no separate format_g722.
    assert "--enable format_pcm" in text and "format_g722" not in text
    modules = (DOCKERFILE.parent / "rootfs/etc/asterisk/modules.conf").read_text()
    assert "load = format_pcm.so" in modules


def test_directed_pickup_module_is_built_and_loaded():
    assert "--enable app_directed_pickup" in DOCKERFILE.read_text()
    modules = (DOCKERFILE.parent / "rootfs/etc/asterisk/modules.conf").read_text()
    assert "load = app_directed_pickup.so" in modules


def test_mixmonitor_module_is_built_and_loaded():
    """Call recording from the app (POST /api/mobile/recording) runs AMI MixMonitor."""
    assert "--enable app_mixmonitor" in DOCKERFILE.read_text()
    modules = (DOCKERFILE.parent / "rootfs/etc/asterisk/modules.conf").read_text()
    assert "load = app_mixmonitor.so" in modules


def test_mixmonitor_dependencies_are_built_and_loaded_first():
    """app_mixmonitor needs func_periodic_hook (beep option), which needs app_chanspy,
    func_cut, func_groupcount and func_uri (.requires in the Asterisk 22 sources).
    Without them Asterisk logged "Error loading module 'app_mixmonitor.so', missing
    dependency: func_periodic_hook" and call recording silently did nothing."""
    dockerfile = DOCKERFILE.read_text()
    modules = (DOCKERFILE.parent / "rootfs/etc/asterisk/modules.conf").read_text()
    for name in ("app_chanspy", "func_cut", "func_groupcount", "func_uri", "func_periodic_hook"):
        assert f"--enable {name} " in dockerfile, name
        assert f"load = {name}.so" in modules, name
        assert modules.index(f"load = {name}.so") < modules.index("load = app_mixmonitor.so"), name
