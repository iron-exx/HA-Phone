"""Config-injection hardening for free-text fields rendered into Asterisk/msmtp confs.

Asterisk .conf files and msmtprc are line-oriented: a CR/LF inside a value starts
a new line, so a display name like "Bob\\n[evil]\\ncontext=..." would inject a whole
new section or option (e.g. `passwordeval` in msmtprc = command execution). The
field validators below reject such values at the API boundary; render_conf()
additionally strips CR/LF from every rendered expression (defense in depth).

- conf_text: any value written into a conf (passwords, hosts, numbers):
  no control characters (CR, LF, TAB, NUL, ESC, DEL, ...).
- conf_name: human-readable names (display_name, ring group / IVR names, SMTP
  from_name): additionally no  [ ] < > " ; $ \\  -- they break sections
  (`[`/`]`), the `"name" <number>` callerid syntax (`<`, `>`, `"`), start a
  conf comment (`;`) or trigger dialplan variable/function expansion (`$`).
"""
import re

from markupsafe import Markup

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_NAME_FORBIDDEN_RE = re.compile(r'[\[\]<>";$\\]')


def conf_text(value: str | None, what: str = "Feld") -> str | None:
    if value is None:
        return value
    if _CONTROL_RE.search(value):
        raise ValueError(f"{what}: Zeilenumbrüche und Steuerzeichen sind nicht erlaubt")
    return value


def conf_name(value: str | None, what: str = "Name") -> str | None:
    if value is None:
        return value
    conf_text(value, what)
    if _NAME_FORBIDDEN_RE.search(value):
        raise ValueError(f'{what}: die Zeichen [ ] < > " ; $ \\ sind nicht erlaubt')
    return value


def strip_line_breaks(value):
    """Jinja2 `finalize` hook: every rendered string loses CR/LF (and other
    control characters except TAB), so no expression can ever start a new
    conf line.

    Exception: Markup values. A template macro's multi-line output (e.g.
    dest_action() in extensions_routing.conf.j2) is marked with `|safe` at the
    call site so its own newlines survive - the values INSIDE the macro were
    already finalized when the macro body rendered."""
    if isinstance(value, Markup):
        return value
    if isinstance(value, str):
        return re.sub(r"[\x00-\x08\x0a-\x1f\x7f]", " ", value)
    return value
