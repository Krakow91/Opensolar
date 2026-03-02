#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Dieses Skript ist nur fuer macOS (launchd). Fuer Linux nutze ./install_dashboard_systemd.sh"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
SCRIPT_PATH="$PROJECT_DIR/dashboard.py"
PLIST_PATH="$HOME/Library/LaunchAgents/de.krakow.opendtu.dashboard.plist"
LABEL="de.krakow.opendtu.dashboard"
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
    <string>de.krakow.opendtu.dashboard</string>

    <key>ProgramArguments</key>
    <array>
      <string>$PYTHON_BIN</string>
      <string>-m</string>
      <string>streamlit</string>
      <string>run</string>
      <string>$SCRIPT_PATH</string>
      <string>--server.headless</string>
      <string>true</string>
      <string>--server.address</string>
      <string>127.0.0.1</string>
      <string>--server.port</string>
      <string>8501</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/data/dashboard.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/dashboard-error.log</string>
  </dict>
</plist>
PLIST

plutil -lint "$PLIST_PATH"

# Alten manuellen Streamlit-Prozess beenden, damit der LaunchAgent den Port 8501 übernehmen kann.
pkill -f "streamlit run dashboard.py" >/dev/null 2>&1 || true

launchctl bootout "gui/$UID_NUM" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST_PATH"
launchctl enable "gui/$UID_NUM/$LABEL"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

echo "Installiert: $PLIST_PATH"
launchctl print "gui/$UID_NUM/$LABEL" | sed -n '1,40p'
