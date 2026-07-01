import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

_tmpl_dir = Path(__file__).parent / "conf_templates"


def render_conf(template_name: str, context: dict, output_path: Path) -> None:
    """Render a Jinja2 conf template atomically to output_path."""
    env = Environment(loader=FileSystemLoader(str(_tmpl_dir)), autoescape=False)
    template = env.get_template(template_name)
    context["generated_at"] = datetime.now(timezone.utc).isoformat()
    content = template.render(**context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=output_path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, output_path)
