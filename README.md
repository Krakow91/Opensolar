# OpenSolar (openDTU Statistiktool)

Dieses Projekt holt Daten von deiner openDTU (`/api/livedata/status`), speichert sie in SQLite und zeigt sie in einem Streamlit-Dashboard.

Das Repository heißt `Opensolar`, der Inhalt ist ein openDTU-Statistiktool.

## Funktionen

- openDTU Live-Daten abrufen und als Snapshot speichern
- Historie in SQLite (`data/opendtu_stats.db`)
- Dashboard im KK91-Design mit klaren Bereichen:
  - Gesamtanlage
  - Wechselrichter (Alle)
  - Wechselrichter (Einzeln)
  - String/Phase Snapshot
  - Rohdaten
- Automatischer Start und Catch-up nach Neustart auf macOS und Linux
- ZimaOS Deployment per Docker Compose
- Home-Assistant-Verknüpfung per MQTT Auto-Discovery (optional)

Erfasste Kennzahlen:

- Gesamtertrag heute (`YieldDay`)
- Gesamtertrag gesamt (`YieldTotal`)
- AC-Leistung (`Power`)
- DC-Leistung (`Power DC`, aggregiert)
- Temperatur (Durchschnitt über Inverter)
- Wirkungsgrad (Durchschnitt über Inverter)
- Pro DC-String (String 1-4): Leistung, Spannung, Strom, Tagesertrag, Gesamtertrag
- Pro AC-Phase (Phase 1): Leistung, Spannung, Strom, Frequenz, Leistungsfaktor, Blindleistung

## Voraussetzungen

- Python 3.10+ (empfohlen)
- openDTU im Netzwerk erreichbar
- Betriebssystem: macOS, Linux oder ZimaOS (Docker-basiert)

## Schnellstart (5 Minuten)

1. Projekt klonen und Abhängigkeiten installieren:

```bash
git clone https://github.com/Krakow91/Opensolar.git
cd Opensolar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Optional Konfiguration anlegen:

```bash
cp .env.example .env
```

Danach `.env` bei Bedarf anpassen (Basis-URL, Login, TLS).

3. Erste Daten abholen:

```bash
source .venv/bin/activate
python collect.py
```

4. Dashboard starten:

```bash
source .venv/bin/activate
streamlit run dashboard.py
```

5. Im Browser öffnen: `http://localhost:8501`

## Installation auf ZimaOS (empfohlen)

ZimaOS läuft Docker-basiert. Für dieses Projekt ist der schnellste Weg: per SSH klonen und per Docker Compose starten.

1. SSH in dein ZimaOS-System:

```bash
ssh <user>@<zimaos-ip>
```

2. Repository klonen und in den Ordner wechseln:

```bash
git clone https://github.com/Krakow91/Opensolar.git
cd Opensolar
```

3. Konfiguration anlegen:

```bash
cp .env.example .env
```

4. `.env` bearbeiten (mindestens `OPENDTU_BASE_URL` anpassen):

```bash
nano .env
```

5. Container starten:

```bash
docker compose -f docker-compose.zimaos.yml up -d --build
```

6. Status prüfen:

```bash
docker compose -f docker-compose.zimaos.yml ps
docker compose -f docker-compose.zimaos.yml logs -f collector
docker compose -f docker-compose.zimaos.yml logs -f dashboard
```

7. Dashboard öffnen:

```text
http://<zimaos-ip>:8501
```

### Optional: Home Assistant Bridge direkt mitstarten

1. In `.env` MQTT-Daten eintragen (mindestens `HA_MQTT_HOST`).
2. Dann mit Home-Assistant-Profil starten:

```bash
docker compose -f docker-compose.zimaos.yml --profile homeassistant up -d --build
```

### Update auf ZimaOS

```bash
cd Opensolar
git pull
docker compose -f docker-compose.zimaos.yml up -d --build
```

## Home Assistant Verknüpfung (MQTT Auto-Discovery)

Die Bridge veröffentlicht den letzten openDTU-Stand automatisch als MQTT-Sensoren.
In Home Assistant erscheinen die Entitäten automatisch, wenn MQTT eingerichtet ist.

1. In Home Assistant die MQTT-Integration aktivieren.
2. In `Opensolar/.env` setzen:

```bash
HA_MQTT_HOST=<ip-oder-host-vom-mqtt-broker>
HA_MQTT_PORT=1883
HA_MQTT_USERNAME=<optional>
HA_MQTT_PASSWORD=<optional>
HA_MQTT_DISCOVERY_PREFIX=homeassistant
HA_MQTT_BASE_TOPIC=opensolar/opendtu
```

3. Bridge starten:

```bash
cd Opensolar
docker compose -f docker-compose.zimaos.yml --profile homeassistant up -d --build
```

4. Logs prüfen:

```bash
docker compose -f docker-compose.zimaos.yml logs -f homeassistant_bridge
```

Danach findest du in Home Assistant u. a.:
- Gesamtleistung
- DC-Leistung
- Tagesertrag
- Gesamtertrag
- Temperatur/Wirkungsgrad
- Wechselrichter-spezifische Sensoren

## Qualitätscheck lokal

```bash
cd Opensolar
python -m py_compile dashboard.py collect.py ha_bridge.py opendtu_stats/*.py
python -m unittest discover -s tests -v
```

## Manuelle Nutzung

Collector manuell ausführen:

```bash
python collect.py
```

Mit expliziten Parametern:

```bash
python collect.py \
  --base-url "http://192.168.178.73" \
  --username "dein-user" \
  --password "dein-passwort"
```

Hilfeseite:

```bash
python collect.py --help
```

## Konfiguration über Umgebungsvariablen

Du kannst `collect.py` über `.env`/Environment steuern:

- `OPENDTU_BASE_URL` (Default: `http://192.168.178.73`)
- `OPENDTU_FALLBACK_URLS` (CSV-Liste mit Fallback-Hosts)
- `OPENDTU_DB_PATH` (Default: `data/opendtu_stats.db`)
- `OPENDTU_USERNAME`
- `OPENDTU_PASSWORD`
- `OPENDTU_VERIFY_TLS` (`true`/`false`)
- `OPENDTU_TIMEOUT` (Sekunden)

## Automatischer Betrieb

### Dashboard beim Login starten

macOS:

```bash
./install_dashboard_launchd.sh
launchctl print "gui/$(id -u)/de.krakow.opendtu.dashboard" | head -n 40
```

Linux:

```bash
./install_dashboard_systemd.sh
systemctl --user status de.krakow.opendtu.dashboard.service --no-pager
```

### Tägliches Sammeln per Cron

Beispiel: täglich um 20:00 Uhr:

```bash
crontab -e
```

Cron-Eintrag:

```cron
0 20 * * * cd "/pfad/zu/Opensolar" && "/pfad/zu/Opensolar/.venv/bin/python" collect.py >> "/pfad/zu/Opensolar/data/collector.log" 2>&1
```

### Catch-up nach Neustart (verpasste Läufe nachholen)

Der Catch-up-Job läuft stündlich und sammelt nur, wenn der letzte erfolgreiche Lauf älter als 26 Stunden ist.

macOS:

```bash
./install_catchup_launchd.sh
launchctl print "gui/$(id -u)/de.krakow.opendtu.catchup" | head -n 40
```

Linux:

```bash
./install_catchup_systemd.sh
systemctl --user status de.krakow.opendtu.catchup.timer --no-pager
systemctl --user list-timers de.krakow.opendtu.catchup.timer --no-pager
```

Optional auf Linux (auch ohne aktive Login-Session laufen lassen):

```bash
sudo loginctl enable-linger "$USER"
```

## Logs

- Dashboard: `data/dashboard.log`, `data/dashboard-error.log`
- Catch-up: `data/catchup.log`, `data/catchup-error.log`
- Cron-Sammeln: `data/collector.log`
- Docker/ZimaOS: `docker compose -f docker-compose.zimaos.yml logs -f`

Live-Ansicht:

```bash
tail -f data/dashboard.log
tail -f data/catchup.log
```

## Häufige Probleme

- openDTU nicht erreichbar:
  - `--base-url` prüfen
  - Fallback-URLs prüfen (`OPENDTU_FALLBACK_URLS`)
  - Netzwerk/Firewall prüfen
- Dashboard startet nicht:
  - Virtuelle Umgebung aktivieren
  - `pip install -r requirements.txt` erneut ausführen
- Linux `systemctl --user` ohne Session:
  - `sudo loginctl enable-linger "$USER"` setzen
