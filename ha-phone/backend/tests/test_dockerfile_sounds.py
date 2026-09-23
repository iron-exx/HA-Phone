"""menuselect --disable-all also drops every sound package; without prompts
VoiceMailMain()/Voicemail() hang up immediately. Guard the explicit re-enables."""
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_asterisk_build_includes_prompts_and_hold_music():
    text = DOCKERFILE.read_text()
    assert "--disable-all" in text
    assert "--enable CORE-SOUNDS-EN-WAV" in text
    assert "--enable MOH-OPSOUND-WAV" in text
