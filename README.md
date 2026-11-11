# mdview

A small, fast Markdown **viewer** for the Linux desktop, built with GTK 3 and
WebKit. It's the default app for `.md` files: click one in Caja or any file
manager and it opens rendered. It's also in the menu as **Markdown Viewer**
(Accessories).

## Features

- GitHub-style rendering: tables, fenced code with syntax highlighting, task
  lists, footnotes, smart quotes, and heading anchors
- Follows the desktop theme: dark when the GTK theme is dark
- **Live reload** when the file changes, keeping your scroll position. It
  also works with editors that save by rename (xed, vim, VS Code)
- Relative images and links work. Links to other `.md` files open in the
  same window (Back goes back); web links open in your browser; other files
  open in their default app
- Find in page, zoom, drag and drop a file onto the window
- Safe for untrusted files: scripts inside documents don't run

## Keys

| key | action |
|---|---|
| Ctrl+O | open a file |
| Ctrl+E | edit the file in your default text editor |
| Ctrl+F | find (Enter next, Shift+Enter previous, Esc close) |
| Ctrl+R / F5 | reload |
| Ctrl+= / Ctrl+- / Ctrl+0 | zoom in / out / reset |
| Alt+Left | back |
| Ctrl+W / Ctrl+Q | close window / quit |

## Command line

```sh
mdview FILE.md [...]         # one window per file; reopening a file focuses its window
mdview --html FILE.md        # print the rendered HTML page
```

## Install / uninstall

```sh
./install.sh                 # ~/.local/bin/mdview, menu entry, icon, default for text/markdown
./install.sh --uninstall
```

It uses only packages already on Linux Mint 22: `python3-gi`,
`gir1.2-webkit2-4.1`, `python3-markdown` and `python3-pygments`.

## Files

| file | purpose |
|---|---|
| `mdview.py` | the app (GTK window, navigation, reload, find) |
| `mdrender.py` | Markdown → HTML page, with no GTK dependency |
| `test_mdview.py` | `python3 -m pytest -q` |
| `mdview.desktop`, `mdview.svg` | menu entry and icon |
| `SAMPLE.md` | a tour of what renders |

## License

MIT. See `LICENSE`.
