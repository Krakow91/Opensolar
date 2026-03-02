#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Dieses Skript ist nur fuer macOS (launchd). Fuer Linux nutze ./install_catchup_systemd.sh"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
SCRIPT_PATH="$PROJECT_DIR/collect.py"
PLIST_PATH="$HOME/Library/LaunchAgents/de.krakow.opendtu.catchup.plist"
LABEL="de.krakow.opendtu.catchup"
UID_NUM="$(id -u)"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python nicht gefunden/executable: $PYTHON_BIN"
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Datei nicht gefunden: $SCRIPT_PATH"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/data"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>de.krakow.opendtu.catchup</string>

    <key>ProgramArguments</key>
    <array>
      <string>$PYTHON_BIN</string>
      <string>$SCRIPT_PATH</string>
      <string>--if-last-success-older-than-hours</string>
      <string>26</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>StartInterval</key>
    <integer>3600</integer>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/data/catchup.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/catchup-error.log</string>
  </dict>
</plist>
PLIST

plutil -lint "$PLIST_PATH"

launchctl bootout "gui/$UID_NUM" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST_PATH"
launchctl enable "gui/$UID_NUM/$LABEL"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

echo "Installiert: $PLIST_PATH"
launchctl print "gui/$UID_NUM/$LABEL" | sed -n '1,30p'
