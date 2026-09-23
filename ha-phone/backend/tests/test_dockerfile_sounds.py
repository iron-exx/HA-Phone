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
