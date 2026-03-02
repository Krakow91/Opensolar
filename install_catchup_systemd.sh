#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Dieses Skript ist nur fuer Linux (systemd --user). Fuer macOS nutze ./install_catchup_launchd.sh"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl nicht gefunden. Bitte systemd installieren oder Cron nutzen."
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
SCRIPT_PATH="$PROJECT_DIR/collect.py"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_NAME="de.krakow.opendtu.catchup.service"
TIMER_NAME="de.krakow.opendtu.catchup.timer"
SERVICE_PATH="$UNIT_DIR/$SERVICE_NAME"
TIMER_PATH="$UNIT_DIR/$TIMER_NAME"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python nicht gefunden/executable: $PYTHON_BIN"
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Datei nicht gefunden: $SCRIPT_PATH"
  exit 1
fi

mkdir -p "$UNIT_DIR" "$PROJECT_DIR/data"

cat > "$SERVICE_PATH" <<UNIT
[Unit]
Description=openDTU Catch-up Collector
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN $SCRIPT_PATH --if-last-success-older-than-hours 26
StandardOutput=append:$PROJECT_DIR/data/catchup.log
StandardError=append:$PROJECT_DIR/data/catchup-error.log
UNIT

cat > "$TIMER_PATH" <<UNIT
[Unit]
Description=Run openDTU catch-up hourly

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h
Persistent=true
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now "$TIMER_NAME"
systemctl --user start "$SERVICE_NAME"

echo "Installiert: $SERVICE_PATH"
echo "Installiert: $TIMER_PATH"
systemctl --user status "$TIMER_NAME" --no-pager --lines=30 || true
systemctl --user list-timers "$TIMER_NAME" --no-pager || true

if command -v loginctl >/dev/null 2>&1; then
  echo ""
  echo "Optional fuer Start ohne aktive Login-Session:"
  echo "  sudo loginctl enable-linger $USER"
fi
