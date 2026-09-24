import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

from backend.conf_safety import strip_line_breaks

_tmpl_dir = Path(__file__).parent / "conf_templates"


def render_conf(template_name: str, context: dict, output_path: Path) -> None:
    """Render a Jinja2 conf template atomically to output_path.

    Defense in depth against config injection: `finalize` strips CR/LF (and other
    control characters) from EVERY rendered expression, so no value -- even one
    that bypassed the API validators (old DB rows, internal callers) -- can start
    a new conf line/section."""
    env = Environment(
        loader=FileSystemLoader(str(_tmpl_dir)),
        autoescape=False,
        finalize=strip_line_breaks,
    )
    template = env.get_template(template_name)
    context["generated_at"] = datetime.now(timezone.utc).isoformat()
    content = template.render(**context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=output_path.parent, delete=False, suffix=".tmp", encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, output_path)
