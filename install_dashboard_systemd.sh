#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Dieses Skript ist nur fuer Linux (systemd --user). Fuer macOS nutze ./install_dashboard_launchd.sh"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl nicht gefunden. Bitte systemd installieren oder Cron nutzen."
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
SCRIPT_PATH="$PROJECT_DIR/dashboard.py"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_NAME="de.krakow.opendtu.dashboard.service"
SERVICE_PATH="$UNIT_DIR/$SERVICE_NAME"

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
Description=openDTU Dashboard (Streamlit)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN -m streamlit run $SCRIPT_PATH --server.headless true --server.address 127.0.0.1 --server.port 8501
Restart=always
RestartSec=5
StandardOutput=append:$PROJECT_DIR/data/dashboard.log
StandardError=append:$PROJECT_DIR/data/dashboard-error.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

echo "Installiert: $SERVICE_PATH"
systemctl --user status "$SERVICE_NAME" --no-pager --lines=30 || true

if command -v loginctl >/dev/null 2>&1; then
  echo ""
  echo "Optional fuer Start ohne aktive Login-Session:"
  echo "  sudo loginctl enable-linger $USER"
fi
