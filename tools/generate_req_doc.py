#!/usr/bin/env python3
"""Generate a formatted HTML requirements document from a Cameo-exported requirements.json."""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PRIORITY_COLORS = {
    "Critical": "#e74c3c",
    "High": "#e67e22",
    "Medium": "#f1c40f",
    "Low": "#27ae60",
}

PRIORITY_BG_COLORS = {
    "Critical": "#fdecea",
    "High": "#fdf2e9",
    "Medium": "#fef9e7",
    "Low": "#eafaf1",
}


def load_requirements(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_hierarchy(requirements: list[dict]) -> dict[str | None, list[dict]]:
    """Group requirements by parentRequirementId."""
    children: dict[str | None, list[dict]] = {}
    for req in requirements:
        parent = req.get("parentRequirementId") or None
        children.setdefault(parent, []).append(req)
    return children


def compute_statistics(requirements: list[dict]) -> str:
    total = len(requirements)
    by_priority = Counter(r.get("priority", "Unspecified") for r in requirements)
    by_status = Counter(r.get("status", "Unspecified") for r in requirements)
    by_verification: Counter = Counter()
    for r in requirements:
        vms = r.get("verificationMethods", [])
        if vms:
            for vm in vms:
                by_verification[vm.get("method", "Unspecified")] += 1
        else:
            # Legacy fallback for single verificationMethod field
            by_verification[r.get("verificationMethod", "Unspecified")] += 1

    def stat_table(title: str, counts: Counter) -> str:
        rows = ""
        for key, count in sorted(counts.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total else 0
            rows += f"<tr><td>{escape(str(key))}</td><td>{count}</td><td>{pct:.1f}%</td></tr>\n"
        return (
            f'<div class="stat-block">'
            f"<h3>{escape(title)}</h3>"
            f"<table><tr><th>Value</th><th>Count</th><th>%</th></tr>{rows}</table>"
            f"</div>"
        )

    return (
        '<div class="statistics">'
        f"<h2>Summary Statistics</h2>"
        f'<p class="total">Total Requirements: <strong>{total}</strong></p>'
        f'<div class="stat-grid">'
        f"{stat_table('By Priority', by_priority)}"
        f"{stat_table('By Status', by_status)}"
        f"{stat_table('By Verification Method', by_verification)}"
        f"</div></div>"
    )


def render_toc_entries(
    children: dict[str | None, list[dict]],
    parent_id: str | None,
    depth: int,
) -> str:
    reqs = children.get(parent_id, [])
    if not reqs:
        return ""
    items = ""
    for req in reqs:
        rid = escape(req.get("requirementId", ""))
        title = escape(req.get("title", "Untitled"))
        priority = req.get("priority", "")
        color = PRIORITY_COLORS.get(priority, "#555")
        items += (
            f'<li><a href="#req-{rid}">{rid} &mdash; {title}</a>'
            f' <span class="toc-priority" style="color:{color};">[{escape(priority)}]</span>'
        )
        sub = render_toc_entries(children, req.get("requirementId"), depth + 1)
        if sub:
            items += sub
        items += "</li>\n"
    return f"<ul>{items}</ul>"


def render_field(label: str, value: object) -> str:
    if value is None or value == "" or value == []:
        return ""
    if isinstance(value, list):
        escaped = ", ".join(escape(str(v)) for v in value)
    else:
        escaped = escape(str(value))
    return f'<div class="field"><span class="field-label">{escape(label)}:</span> {escaped}</div>'


def render_requirements(
    children: dict[str | None, list[dict]],
    parent_id: str | None,
    depth: int,
) -> str:
    reqs = children.get(parent_id, [])
    if not reqs:
        return ""
    html_parts: list[str] = []
    for req in reqs:
        rid = escape(req.get("requirementId", ""))
        title = escape(req.get("title", "Untitled"))
        priority = req.get("priority", "")
        border_color = PRIORITY_COLORS.get(priority, "#bbb")
        bg_color = PRIORITY_BG_COLORS.get(priority, "#fafafa")
        indent = depth * 40

        fields = ""
        fields += render_field("Requirement ID", req.get("requirementId"))
        fields += render_field("Cameo UUID", req.get("cameoUUID"))
        fields += render_field("Priority", priority)
        fields += render_field("Status", req.get("status"))
        fields += render_field("Parent Requirement", req.get("parentRequirementId"))

        # Render verification methods (1-to-many)
        vms = req.get("verificationMethods", [])
        if vms:
            vm_rows = ""
            for vm in vms:
                vm_id = escape(vm.get("verificationMethodId", ""))
                method = escape(vm.get("method", ""))
                criteria = escape(vm.get("criteria", ""))
                vm_rows += (
                    f'<tr><td><code>{vm_id}</code></td>'
                    f'<td>{method}</td>'
                    f'<td>{criteria}</td></tr>\n'
                )
            fields += (
                f'<div class="field"><span class="field-label">Verification Methods:</span>'
                f'<table style="margin-top:4px;font-size:0.88em;">'
                f'<tr><th>VM ID</th><th>Method</th><th>Criteria</th></tr>'
                f'{vm_rows}</table></div>'
            )

        fields += render_field("Satisfied By", req.get("satisfiedBy"))
        fields += render_field("Traces To", req.get("tracesTo"))

        description = req.get("description", "")
        desc_html = ""
        if description:
            desc_html = (
                f'<div class="description">'
                f"<span class=\"field-label\">Description:</span>"
                f"<p>{escape(description)}</p></div>"
            )

        heading_tag = f"h{min(2 + depth, 6)}"

        html_parts.append(
            f'<div class="requirement" id="req-{rid}" '
            f'style="margin-left:{indent}px; border-left: 4px solid {border_color}; '
            f'background: {bg_color};">'
            f"<{heading_tag}>{rid} &mdash; {title}</{heading_tag}>"
            f"{fields}"
            f"{desc_html}"
            f"</div>"
        )

        # Render children recursively
        html_parts.append(render_requirements(children, req.get("requirementId"), depth + 1))

    return "\n".join(html_parts)


def generate_html(data: dict, title: str) -> str:
    metadata = data.get("exportMetadata", {})
    project_name = escape(metadata.get("projectName", "Unknown Project"))
    model_version = escape(metadata.get("modelVersion", "N/A"))
    cameo_version = escape(metadata.get("cameoVersion", "N/A"))
    export_timestamp = escape(metadata.get("exportTimestamp", "N/A"))
    generation_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    requirements = data.get("requirements", [])
    children = build_hierarchy(requirements)

    stats_html = compute_statistics(requirements)
    toc_html = render_toc_entries(children, None, 0)
    body_html = render_requirements(children, None, 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6; color: #333; max-width: 1100px; margin: 0 auto; padding: 20px 30px;
    background: #fdfdfd;
  }}
  .header {{
    border-bottom: 3px solid #2c3e50; padding-bottom: 16px; margin-bottom: 24px;
  }}
  .header h1 {{ color: #2c3e50; font-size: 1.8em; margin-bottom: 8px; }}
  .header-meta {{ color: #666; font-size: 0.9em; }}
  .header-meta span {{ margin-right: 18px; }}
  .statistics {{
    background: #f7f9fc; border: 1px solid #dce1e8; border-radius: 6px;
    padding: 16px 20px; margin-bottom: 28px;
  }}
  .statistics h2 {{ font-size: 1.2em; color: #2c3e50; margin-bottom: 10px; }}
  .total {{ font-size: 1.05em; margin-bottom: 12px; }}
  .stat-grid {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .stat-block {{ flex: 1; min-width: 220px; }}
  .stat-block h3 {{ font-size: 0.95em; color: #555; margin-bottom: 4px; }}
  .stat-block table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
  .stat-block th, .stat-block td {{
    text-align: left; padding: 3px 8px; border-bottom: 1px solid #eee;
  }}
  .stat-block th {{ color: #777; }}
  .toc {{
    background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px;
    padding: 16px 20px; margin-bottom: 28px;
  }}
  .toc h2 {{ font-size: 1.2em; color: #2c3e50; margin-bottom: 8px; }}
  .toc ul {{ padding-left: 22px; }}
  .toc li {{ margin: 3px 0; font-size: 0.92em; }}
  .toc a {{ color: #2980b9; text-decoration: none; }}
  .toc a:hover {{ text-decoration: underline; }}
  .toc-priority {{ font-size: 0.85em; font-weight: 600; }}
  .requirement {{
    padding: 14px 18px; margin-bottom: 16px; border-radius: 4px;
  }}
  .requirement h2, .requirement h3, .requirement h4,
  .requirement h5, .requirement h6 {{
    color: #2c3e50; margin-bottom: 8px; font-size: 1.1em;
  }}
  .field {{ font-size: 0.9em; margin: 3px 0; }}
  .field-label {{ font-weight: 600; color: #555; }}
  .description {{ margin-top: 8px; }}
  .description p {{
    margin-top: 4px; background: rgba(255,255,255,0.6);
    padding: 8px 10px; border-radius: 3px; font-size: 0.92em;
  }}
  .footer {{
    margin-top: 36px; padding-top: 12px; border-top: 1px solid #ddd;
    color: #999; font-size: 0.8em; text-align: center;
  }}
</style>
</head>
<body>
<div class="header">
  <h1>{escape(title)}</h1>
  <div class="header-meta">
    <span><strong>Project:</strong> {project_name}</span>
    <span><strong>Model Version:</strong> {model_version}</span>
    <span><strong>Cameo Version:</strong> {cameo_version}</span>
    <span><strong>Exported:</strong> {export_timestamp}</span>
    <span><strong>Generated:</strong> {generation_time}</span>
  </div>
</div>

{stats_html}

<div class="toc">
  <h2>Table of Contents</h2>
  {toc_html}
</div>

{body_html}

<div class="footer">
  Generated from Cameo Systems Modeler export &middot; {generation_time}
</div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an HTML requirements document from a Cameo-exported requirements.json."
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        required=True,
        help="Path to the requirements.json file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the output HTML file",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Requirements Document",
        help="Document title (default: 'Requirements Document')",
    )
    args = parser.parse_args()

    req_path: Path = args.requirements
    out_path: Path = args.output

    if not req_path.is_file():
        print(f"Error: requirements file not found: {req_path}", file=sys.stderr)
        return 1

    try:
        data = load_requirements(req_path)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {req_path}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: cannot read {req_path}: {exc}", file=sys.stderr)
        return 1

    if "requirements" not in data:
        print(f"Error: 'requirements' key not found in {req_path}", file=sys.stderr)
        return 1

    html = generate_html(data, args.title)

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot write output file {out_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {out_path} ({len(data['requirements'])} requirements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
