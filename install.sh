#!/usr/bin/env bash
# Install mdview for the current user: command, menu entry, icon, and make it
# the default app for Markdown files. Re-run safely; ./install.sh --uninstall removes it.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
bin=~/.local/bin/mdview
app=~/.local/share/applications/mdview.desktop
icon=~/.local/share/icons/hicolor/scalable/apps/mdview.svg

if [[ ${1:-} == --uninstall ]]; then
  rm -f "$bin" "$app" "$icon"
  sed -i '/^text\/\(x-\)\?markdown=mdview.desktop$/d' ~/.config/mimeapps.list 2>/dev/null || true
  update-desktop-database ~/.local/share/applications 2>/dev/null || true
  echo "mdview uninstalled"; exit 0
fi

mkdir -p ~/.local/bin "$(dirname "$app")" "$(dirname "$icon")"
ln -sf "$here/mdview.py" "$bin"
chmod +x "$here/mdview.py"
sed "s|^Exec=mdview |Exec=$bin |" "$here/mdview.desktop" > "$app" && chmod 644 "$app"
install -m 644 "$here/mdview.svg" "$icon"
update-desktop-database ~/.local/share/applications 2>/dev/null || true
gtk-update-icon-cache -q -t ~/.local/share/icons/hicolor 2>/dev/null || true
xdg-mime default mdview.desktop text/markdown
xdg-mime default mdview.desktop text/x-markdown
echo "installed: $bin, menu entry 'Markdown Viewer', default for .md = $(xdg-mime query default text/markdown)"
