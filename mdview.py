#!/usr/bin/env python3
"""mdview — a small, fast Markdown viewer for the desktop.

    mdview [FILE.md ...]      open files (each in its own window)
    mdview --html FILE.md     print the rendered HTML page to stdout

Keys: Ctrl+O open · Ctrl+E edit in text editor · Ctrl+R reload · Ctrl+F find
      Ctrl+= / Ctrl+- / Ctrl+0 zoom · Alt+Left back · Ctrl+W close · Ctrl+Q quit
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdrender  # noqa: E402

MD_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdwn", ".mdtext", ".text"}
APP_ID = "org.local.MdView"


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() in MD_SUFFIXES


def file_uri_path(uri: str) -> tuple[Path | None, str]:
    """(path, fragment) for a file:// URI, else (None, '')."""
    u = urlparse(uri)
    if u.scheme != "file":
        return None, ""
    return Path(unquote(u.path)), u.fragment


def main_cli(argv: list[str]) -> int | None:
    """Handle non-GUI invocations; return an exit code, or None to start the GUI."""
    if len(argv) >= 2 and argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if len(argv) == 3 and argv[1] == "--html":
        sys.stdout.write(mdrender.render_file(Path(argv[2])))
        return 0
    return None


# --------------------------------------------------------------------- GUI
def run_gui(argv: list[str]) -> int:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2

    GLib.set_prgname("mdview")          # WM_CLASS, matches StartupWMClass
    GLib.set_application_name("Markdown Viewer")

    def prefers_dark() -> bool:
        s = Gtk.Settings.get_default()
        return bool(s.props.gtk_application_prefer_dark_theme) or \
            "dark" in (s.props.gtk_theme_name or "").lower()

    class Viewer(Gtk.ApplicationWindow):
        def __init__(self, app: Gtk.Application, path: Path | None):
            super().__init__(application=app, title="mdview")
            self.set_default_size(960, 1000)
            self.set_icon_name("mdview")
            self.path: Path | None = None
            self.history: list[Path] = []
            self.monitor = None
            self._reload_src = 0
            self._restore_y: float | None = None
            self._pending_frag = ""

            # header bar
            hb = Gtk.HeaderBar(show_close_button=True)
            self.set_titlebar(hb)
            self.header = hb
            self.back_btn = self._button(hb, "go-previous-symbolic", "Back (Alt+Left)", self.go_back)
            self._button(hb, "document-open-symbolic", "Open… (Ctrl+O)", self.open_dialog)
            self._button(hb, "document-edit-symbolic", "Edit in text editor (Ctrl+E)",
                         self.edit, end=True)
            self._button(hb, "edit-find-symbolic", "Find (Ctrl+F)",
                         lambda *_: self.toggle_find(), end=True)

            # web view (page scripts disabled; API-side JS still works)
            settings = WebKit2.Settings(
                enable_javascript_markup=False,
                enable_developer_extras=False,
                allow_file_access_from_file_urls=True,
                enable_smooth_scrolling=True,
            )
            self.web = WebKit2.WebView(settings=settings)
            self.web.connect("decide-policy", self.on_policy)
            self.web.connect("load-changed", self.on_load_changed)
            self.web.connect("context-menu", lambda *_: False)
            self.find = self.web.get_find_controller()

            # find bar
            self.search_bar = Gtk.SearchBar()
            self.entry = Gtk.SearchEntry(width_chars=40)
            self.entry.connect("search-changed", lambda e: self.search())
            self.entry.connect("activate", lambda e: self.find.search_next())
            self.entry.connect("stop-search", lambda e: self.toggle_find(False))
            self.entry.connect("key-press-event", self.on_entry_key)
            self.search_bar.add(self.entry)
            self.search_bar.connect_entry(self.entry)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.pack_start(self.search_bar, False, False, 0)
            box.pack_start(self.web, True, True, 0)
            self.add(box)

            self.connect("key-press-event", self.on_key)
            Gtk.Settings.get_default().connect("notify::gtk-theme-name", lambda *_: self.reload())
            Gtk.Settings.get_default().connect(
                "notify::gtk-application-prefer-dark-theme", lambda *_: self.reload())

            # drag and drop .md files onto the window
            self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
            self.drag_dest_add_uri_targets()
            self.connect("drag-data-received", self.on_drop)

            self.show_all()
            self.search_bar.set_search_mode(False)
            if path:
                self.load(path)
            else:
                self.show_message("No file", "Open a Markdown file with Ctrl+O, or drop one here.")
            self._update_back()

        # ---- helpers
        def _button(self, hb, icon, tip, cb, end=False):
            b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda *_: cb())
            (hb.pack_end if end else hb.pack_start)(b)
            return b

        def _update_back(self):
            self.back_btn.set_sensitive(bool(self.history))

        def show_message(self, title, text):
            body = f"<h1>{GLib.markup_escape_text(title)}</h1><p>{GLib.markup_escape_text(text)}</p>"
            page = mdrender.render_page("", title=title, dark=prefers_dark()).replace(
                "<main></main>", f"<main>{body}</main>")
            self.web.load_html(page, "file:///")

        # ---- loading
        def load(self, path: Path, push: bool = False, fragment: str = ""):
            path = path.expanduser().resolve()
            if push and self.path and path != self.path:
                self.history.append(self.path)
            self.path = path
            self._restore_y = None
            self._watch(path)
            self.header.set_title(path.name)
            self.header.set_subtitle(str(path.parent).replace(str(Path.home()), "~", 1))
            self.set_title(f"{path.name} — mdview")
            self._render(fragment)
            self._update_back()

        def _render(self, fragment: str = ""):
            assert self.path
            try:
                page = mdrender.render_file(self.path, dark=prefers_dark())
            except FileNotFoundError:
                self.show_message("File not found", str(self.path))
                return
            except OSError as e:
                self.show_message("Can't read file", f"{self.path}: {e.strerror}")
                return
            self._pending_frag = fragment
            self.web.load_html(page, self.path.as_uri())

        def reload(self):
            if not self.path:
                return

            def got(web, res):
                try:
                    self._restore_y = web.evaluate_javascript_finish(res).to_double()
                except GLib.Error:
                    self._restore_y = None
                self._render()
            self.web.evaluate_javascript("window.scrollY", -1, None, None, None, got)

        def on_load_changed(self, web, event):
            if event != WebKit2.LoadEvent.FINISHED:
                return
            if self._pending_frag:
                frag, self._pending_frag = self._pending_frag, ""
                js = f"var e=document.getElementById({json.dumps(unquote(frag))}); if(e) e.scrollIntoView();"
                web.evaluate_javascript(js, -1, None, None, None, None)
            elif self._restore_y:
                y, self._restore_y = self._restore_y, None
                web.evaluate_javascript(f"window.scrollTo(0,{float(y)})", -1, None, None, None, None)

        def _watch(self, path: Path):
            if self.monitor:
                self.monitor.cancel()
            # Watch the directory: editors often save by rename, which a
            # file monitor on the old inode would miss.
            self.monitor = Gio.File.new_for_path(str(path.parent)).monitor_directory(
                Gio.FileMonitorFlags.WATCH_MOVES, None)
            self.monitor.connect("changed", self.on_fs_change)

        def on_fs_change(self, _mon, f, other, _event):
            names = {f.get_basename() if f else None, other.get_basename() if other else None}
            if self.path and self.path.name in names:
                if self._reload_src:
                    GLib.source_remove(self._reload_src)
                self._reload_src = GLib.timeout_add(150, self._debounced_reload)

        def _debounced_reload(self):
            self._reload_src = 0
            self.reload()
            return False

        # ---- navigation
        def on_policy(self, web, decision, kind):
            if kind != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
                return False
            action = decision.get_navigation_action()
            uri = action.get_request().get_uri()
            path, frag = file_uri_path(uri)
            if path is not None and (self.path is None or path == self.path or uri == "file:///"):
                return False                         # our own load / in-page anchor
            if action.get_navigation_type() == WebKit2.NavigationType.OTHER and path is None:
                return False
            decision.ignore()
            if path is not None and is_markdown(path):
                self.load(path, push=True, fragment=frag)
            else:
                try:
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except GLib.Error as e:
                    print(f"mdview: can't open {uri}: {e.message}", file=sys.stderr)
            return True

        def go_back(self):
            if self.history:
                self.load(self.history.pop())

        def on_drop(self, _w, _ctx, _x, _y, data, _info, _time):
            for uri in data.get_uris():
                path, _ = file_uri_path(uri)
                if path and path.is_file():
                    self.load(path, push=True)
                    break

        # ---- actions
        def open_dialog(self):
            dlg = Gtk.FileChooserNative.new("Open Markdown", self, Gtk.FileChooserAction.OPEN,
                                            "_Open", "_Cancel")
            flt = Gtk.FileFilter()
            flt.set_name("Markdown")
            flt.add_mime_type("text/markdown")
            for s in MD_SUFFIXES:
                flt.add_pattern(f"*{s}")
            dlg.add_filter(flt)
            allf = Gtk.FileFilter()
            allf.set_name("All files")
            allf.add_pattern("*")
            dlg.add_filter(allf)
            if self.path:
                dlg.set_current_folder(str(self.path.parent))
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                self.load(Path(dlg.get_filename()), push=True)
            dlg.destroy()

        def edit(self):
            if not self.path:
                return
            app = Gio.AppInfo.get_default_for_type("text/plain", False)
            gfile = Gio.File.new_for_path(str(self.path))
            if app:
                app.launch([gfile], None)
            else:
                Gio.AppInfo.launch_default_for_uri(gfile.get_uri(), None)

        def toggle_find(self, show: bool | None = None):
            show = not self.search_bar.get_search_mode() if show is None else show
            self.search_bar.set_search_mode(show)
            if show:
                self.entry.grab_focus()
            else:
                self.find.search_finish()
                self.web.grab_focus()

        def search(self):
            text = self.entry.get_text()
            if text:
                opts = WebKit2.FindOptions.CASE_INSENSITIVE | WebKit2.FindOptions.WRAP_AROUND
                self.find.search(text, opts, 10000)
            else:
                self.find.search_finish()

        def on_entry_key(self, _e, ev):
            if ev.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and ev.state & Gdk.ModifierType.SHIFT_MASK:
                self.find.search_previous()
                return True
            return False

        def zoom(self, step: float | None):
            self.web.set_zoom_level(1.0 if step is None else
                                    max(0.3, min(4.0, self.web.get_zoom_level() + step)))

        def on_key(self, _w, ev):
            ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
            alt = ev.state & Gdk.ModifierType.MOD1_MASK
            k = Gdk.keyval_to_lower(ev.keyval)
            if ctrl:
                actions = {
                    Gdk.KEY_o: self.open_dialog, Gdk.KEY_e: self.edit, Gdk.KEY_r: self.reload,
                    Gdk.KEY_f: lambda: self.toggle_find(True), Gdk.KEY_w: self.close,
                    Gdk.KEY_q: lambda: self.get_application().quit(),
                    Gdk.KEY_equal: lambda: self.zoom(0.1), Gdk.KEY_plus: lambda: self.zoom(0.1),
                    Gdk.KEY_KP_Add: lambda: self.zoom(0.1), Gdk.KEY_minus: lambda: self.zoom(-0.1),
                    Gdk.KEY_KP_Subtract: lambda: self.zoom(-0.1), Gdk.KEY_0: lambda: self.zoom(None),
                }
                if k in actions:
                    actions[k]()
                    return True
            if alt and k == Gdk.KEY_Left:
                self.go_back()
                return True
            if k == Gdk.KEY_F5:
                self.reload()
                return True
            if k == Gdk.KEY_Escape and self.search_bar.get_search_mode():
                self.toggle_find(False)
                return True
            return False

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

        def do_activate(self):
            Viewer(self, None).present()

        def do_open(self, files, _n, _hint):
            for f in files:
                p = Path(f.get_path()).resolve() if f.get_path() else None
                existing = next((w for w in self.get_windows()
                                 if isinstance(w, Viewer) and w.path == p), None)
                (existing or Viewer(self, p)).present()

    return App().run(argv)


def main() -> int:
    rc = main_cli(sys.argv)
    if rc is not None:
        return rc
    return run_gui(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
