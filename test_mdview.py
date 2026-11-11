"""Tests for mdview's renderer and URI helpers (no display needed)."""
from pathlib import Path

import mdrender
import mdview


def test_tables_and_fenced_code_highlighted():
    body = mdrender.render_body("| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\ndef f(): pass\n```\n")
    assert "<table>" in body and "<td>1</td>" in body
    assert 'class="hl"' in body and '<span class="k">def</span>' in body


def test_task_lists_become_disabled_checkboxes():
    body = mdrender.render_body("- [ ] todo\n- [x] done\n- plain\n")
    assert body.count('type="checkbox" disabled') == 2
    assert 'disabled checked> done' in body
    assert "<li>plain</li>" in body


def test_heading_ids_for_anchor_links():
    assert '<h2 id="the-fix">The fix</h2>' in mdrender.render_body("## The fix\n")


def test_footnotes_and_smart_quotes():
    body = mdrender.render_body('Say "hi"[^1].\n\n[^1]: note\n')
    assert "&ldquo;hi&rdquo;" in body and 'class="footnote"' in body


def test_page_dark_class_and_title_escaped():
    page = mdrender.render_page("x", title="<a&b>", dark=True)
    assert '<html class="dark">' in page and "<title>&lt;a&amp;b&gt;</title>" in page
    assert '<html>' in mdrender.render_page("x")


def test_render_file_tolerates_bad_utf8(tmp_path: Path):
    f = tmp_path / "bad.md"
    f.write_bytes(b"# ok \xff\xfe\n")
    assert "<h1" in mdrender.render_file(f)


def test_file_uri_path():
    assert mdview.file_uri_path("file:///tmp/a%20b.md#sec") == (Path("/tmp/a b.md"), "sec")
    assert mdview.file_uri_path("https://example.com/x.md") == (None, "")


def test_is_markdown():
    assert mdview.is_markdown(Path("README.MD")) and mdview.is_markdown(Path("x.markdown"))
    assert not mdview.is_markdown(Path("x.py"))


def test_cli_html(capsys, tmp_path: Path):
    f = tmp_path / "t.md"
    f.write_text("# Hello\n")
    assert mdview.main_cli(["mdview", "--html", str(f)]) == 0
    assert '<h1 id="hello">Hello</h1>' in capsys.readouterr().out
    assert mdview.main_cli(["mdview", str(f)]) is None
