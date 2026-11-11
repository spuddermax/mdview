"""Markdown → standalone HTML page for mdview.

Kept free of GTK so it can be unit-tested and reused (``mdview --html FILE``).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

EXTENSIONS = [
    "extra",          # tables, fenced code, footnotes, abbr, attr_list, def_list
    "codehilite",     # pygments highlighting for fenced code
    "toc",            # heading ids, so #anchor links work
    "sane_lists",
    "smarty",
]
EXTENSION_CONFIGS = {
    "codehilite": {"guess_lang": False, "css_class": "hl"},
    "toc": {"permalink": False},
}

_TASK_RE = re.compile(r"<li>(\s*<p>)?\s*\[([ xX])\]\s+")


def _task_lists(body: str) -> str:
    """GitHub-style ``- [ ] item`` / ``- [x] item`` → disabled checkboxes."""
    def sub(m: re.Match) -> str:
        checked = " checked" if m.group(2) in "xX" else ""
        return (f'<li class="task">{m.group(1) or ""}'
                f'<input type="checkbox" disabled{checked}> ')
    return _TASK_RE.sub(sub, body)


def render_body(text: str) -> str:
    md = markdown.Markdown(extensions=EXTENSIONS, extension_configs=EXTENSION_CONFIGS)
    return _task_lists(md.convert(text))


def pygments_css() -> str:
    light = HtmlFormatter(style="default").get_style_defs(".hl")
    dark = HtmlFormatter(style="monokai").get_style_defs(".dark .hl")
    return light + "\n" + dark


CSS = """
:root { color-scheme: light; --fg:#1f2328; --bg:#ffffff; --muted:#59636e;
  --border:#d1d9e0; --code-bg:#f6f8fa; --link:#0969da; --quote:#d1d9e0; }
.dark { color-scheme: dark; --fg:#e6edf3; --bg:#0d1117; --muted:#9198a1;
  --border:#3d444d; --code-bg:#151b23; --link:#4493f8; --quote:#3d444d; }
html { background: var(--bg); }
body { color: var(--fg); background: var(--bg); margin: 0;
  font: 16px/1.6 -apple-system, "Segoe UI", "Noto Sans", Ubuntu, Cantarell, sans-serif; }
main { max-width: 900px; margin: 0 auto; padding: 32px 40px 80px; }
a { color: var(--link); text-decoration: none; } a:hover { text-decoration: underline; }
h1, h2 { border-bottom: 1px solid var(--border); padding-bottom: .3em; }
h1, h2, h3, h4, h5, h6 { margin: 1.5em 0 .6em; line-height: 1.25; font-weight: 600; }
h1 { font-size: 2em; } h2 { font-size: 1.5em; } h3 { font-size: 1.25em; }
p, ul, ol, table, pre, blockquote, dl { margin: 0 0 1em; }
code, pre { font: 0.875em/1.5 "JetBrains Mono", "DejaVu Sans Mono", "Ubuntu Mono", monospace; }
:not(pre) > code { background: var(--code-bg); padding: .15em .4em; border-radius: 6px; }
pre, .hl { background: var(--code-bg) !important; border-radius: 6px; }
.hl pre, pre { padding: 14px 16px; overflow-x: auto; margin: 0 0 1em; }
.hl { margin: 0 0 1em; }
blockquote { color: var(--muted); border-left: .25em solid var(--quote); padding: 0 1em; margin-left: 0; }
table { border-collapse: collapse; display: block; overflow-x: auto; }
th, td { border: 1px solid var(--border); padding: 6px 13px; }
th { font-weight: 600; } tr:nth-child(2n) td { background: var(--code-bg); }
img { max-width: 100%; }
hr { border: 0; border-top: 1px solid var(--border); margin: 24px 0; }
li.task { list-style: none; } li.task input { margin: 0 .4em 0 -1.3em; }
.footnote { font-size: .875em; color: var(--muted); }
"""


def render_page(text: str, title: str = "", dark: bool = False) -> str:
    cls = ' class="dark"' if dark else ""
    return (
        "<!doctype html>\n"
        f'<html{cls}><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title>"
        f"<style>{CSS}\n{pygments_css()}</style></head>"
        f"<body><main>{render_body(text)}</main></body></html>"
    )


def render_file(path: Path, dark: bool = False) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return render_page(text, title=path.name, dark=dark)
