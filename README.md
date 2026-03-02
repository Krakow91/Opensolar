# openDTU Tagesstatistik

Dieses Tool holt täglich Daten von deiner openDTU (`/api/livedata/status`), speichert sie in SQLite und zeigt sie als Dashboard mit Grafiken.

Gespeicherte Kennzahlen:
- Gesamtertrag heute (`YieldDay`)
- Gesamtertrag gesamt (`YieldTotal`)
- AC-Leistung (`Power`)
- DC-Leistung (`Power DC`, aggregiert)
- Temperatur (Durchschnitt über Inverter)
- Wirkungsgrad (Durchschnitt über Inverter)
- pro DC-String (String 1-4): Leistung, Spannung, Strom, Tagesertrag, Gesamtertrag
- pro AC-Phase (Phase 1): Leistung, Spannung, Strom, Frequenz, Leistungsfaktor, Blindleistung
- zusätzlich pro Wechselrichter eigene Tages-/Gesamtwerte

## 1) Installation

```bash
cd "/pfad/zu/deinem/projekt"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Ersten Snapshot speichern

```bash
source .venv/bin/activate
python collect.py
```

Optional mit Login:

```bash
python collect.py \
  --base-url "http://192.168.178.73" \
  --username "dein-user" \
  --password "dein-passwort"
```

Die Daten landen standardmäßig in `data/opendtu_stats.db`.
Standardmäßig wird zuerst `http://192.168.178.73` genutzt und bei Bedarf automatisch auf
`http://OpenDTU-FAE538`, `http://OpenDTU-FAE538.local` und `http://192.168.4.1` (AP-Modus) gewechselt.

## 3) Dashboard starten

```bash
source .venv/bin/activate
streamlit run dashboard.py
```

Dann im Browser: `http://localhost:8501`

Optional Dashboard-Autostart nach Login/Neustart:

macOS (`launchd`):

```bash
./install_dashboard_launchd.sh
```

Status prüfen:

```bash
launchctl print "gui/$(id -u)/de.krakow.opendtu.dashboard" | head -n 40
```

Linux (`systemd --user`):

```bash
./install_dashboard_systemd.sh
```

Status prüfen:

```bash
systemctl --user status de.krakow.opendtu.dashboard.service --no-pager
```

Dashboard-Logs (beide Plattformen):

```bash
tail -f "./data/dashboard.log"
tail -f "./data/dashboard-error.log"
```

## 4) Täglich automatisch ausführen (Cron, macOS/Linux)

Beispiel: jeden Tag um **20:00**

```bash
crontab -e
```

Eintrag ergänzen:

```cron
0 20 * * * cd "/pfad/zu/deinem/projekt" && "/pfad/zu/deinem/projekt/.venv/bin/python" collect.py >> "/pfad/zu/deinem/projekt/data/collector.log" 2>&1
```

Wenn du Login brauchst, hänge `--username` und `--password` an.
Fallback-Adressen kannst du über `--fallback-urls` oder `OPENDTU_FALLBACK_URLS` anpassen.

## 5) Nachholen nach Neustart (macOS/Linux)

Zusätzlich ist ein Hintergrund-Job sinnvoll, damit ein verpasster/falscher Abruf nachgeholt wird.
Er startet beim Login/Neustart und prüft dann stündlich:
- nur wenn der letzte erfolgreiche Run aelter als 26 Stunden ist, wird neu abgefragt
- sonst wird sauber uebersprungen

macOS (`launchd`) einmalig installieren:

```bash
./install_catchup_launchd.sh
```

Status prüfen:

```bash
launchctl print "gui/$(id -u)/de.krakow.opendtu.catchup" | head -n 40
```

Linux (`systemd --user`) einmalig installieren:

```bash
./install_catchup_systemd.sh
```

Status prüfen:

```bash
systemctl --user status de.krakow.opendtu.catchup.timer --no-pager
systemctl --user list-timers de.krakow.opendtu.catchup.timer --no-pager
```

Logs (beide Plattformen):

```bash
tail -f "./data/catchup.log"
tail -f "./data/catchup-error.log"
```

Optional auf Linux, wenn Jobs auch ohne aktive Login-Session laufen sollen:

```bash
sudo loginctl enable-linger "$USER"
```

## 6) Tipps

- Wenn du mehrere Wechselrichter hast, zeigt das Dashboard pro Gerät eigene Werte.
- Für genauere Kurven (tagsüber), kannst du zusätzlich öfter sammeln (z. B. stündlich). Für dein Ziel „1x täglich“ reicht der Cron oben.
- Bei HTTPS mit self-signed Zertifikat kannst du `--no-verify-tls` nutzen.
