from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import requests

from .client import OpenDTUClient
from .db import init_db, insert_snapshot
from .models import Snapshot
from .parser import parse_status_payload


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _candidate_base_urls(base_url: str, fallback_urls: list[str] | None) -> list[str]:
    candidates = [base_url]
    for url in (fallback_urls or []):
        if url not in candidates:
            candidates.append(url)
    return candidates


def _latest_success_age_hours(db_path: str | Path) -> float | None:
    db_file = Path(db_path)
    if not db_file.exists():
        return None

    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute("SELECT collected_at FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()

    if not row or not row[0]:
        return None

    latest = datetime.fromisoformat(str(row[0]))
    now = datetime.now().astimezone()

    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=now.tzinfo)
    else:
        latest = latest.astimezone(now.tzinfo)

    age_hours = (now - latest).total_seconds() / 3600.0
    return max(age_hours, 0.0)


def collect_and_store(
    base_url: str,
    db_path: str | Path,
    username: str | None = None,
    password: str | None = None,
    verify_tls: bool = True,
    timeout_seconds: int = 15,
    fallback_urls: list[str] | None = None,
) -> tuple[Snapshot, int]:
    init_db(db_path)

    payload: dict | None = None
    used_base_url: str | None = None
    errors: list[str] = []

    for candidate in _candidate_base_urls(base_url, fallback_urls):
        client = OpenDTUClient(
            base_url=candidate,
            username=username,
            password=password,
            verify_tls=verify_tls,
            timeout_seconds=timeout_seconds,
        )
        try:
            payload = client.fetch_livedata_status_with_details()
            used_base_url = candidate
            break
        except requests.RequestException as exc:
            errors.append(f"{candidate}: {exc}")

    if payload is None or used_base_url is None:
        tried = ", ".join(_candidate_base_urls(base_url, fallback_urls))
        details = " | ".join(errors) if errors else "unbekannter Fehler"
        raise RuntimeError(f"openDTU nicht erreichbar. Geprüft: {tried}. Details: {details}")

    snapshot = parse_status_payload(payload, dtu_host=used_base_url)
    run_id = insert_snapshot(db_path, snapshot)

    return snapshot, run_id


def build_parser() -> argparse.ArgumentParser:
    default_base_url = os.getenv("OPENDTU_BASE_URL", "http://192.168.178.73")
    default_db = os.getenv("OPENDTU_DB_PATH", "data/opendtu_stats.db")
    default_fallback_urls = os.getenv(
        "OPENDTU_FALLBACK_URLS",
        "http://OpenDTU-FAE538,http://OpenDTU-FAE538.local,http://192.168.4.1",
    )

    parser = argparse.ArgumentParser(
        description="Greift openDTU-Daten ab und speichert sie in SQLite.",
    )
    parser.add_argument("--base-url", default=default_base_url, help="openDTU Basis-URL")
    parser.add_argument(
        "--fallback-urls",
        default=default_fallback_urls,
        help="Komma-getrennte Fallback-URLs bei Verbindungsproblemen",
    )
    parser.add_argument("--db-path", default=default_db, help="Pfad zur SQLite-Datei")
    parser.add_argument("--username", default=os.getenv("OPENDTU_USERNAME"), help="HTTP-Benutzername")
    parser.add_argument("--password", default=os.getenv("OPENDTU_PASSWORD"), help="HTTP-Passwort")
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        default=_env_bool("OPENDTU_VERIFY_TLS", True),
        help="TLS-Zertifikat prüfen (bei HTTPS)",
    )
    parser.add_argument(
        "--no-verify-tls",
        action="store_false",
        dest="verify_tls",
        help="TLS-Zertifikat nicht prüfen",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("OPENDTU_TIMEOUT", "15")),
        help="HTTP Timeout in Sekunden",
    )
    parser.add_argument(
        "--if-last-success-older-than-hours",
        type=float,
        default=None,
        help="Nur sammeln, wenn der letzte erfolgreiche Run aelter als dieser Wert ist",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.if_last_success_older_than_hours is not None:
        latest_age = _latest_success_age_hours(args.db_path)
        if latest_age is not None and latest_age < args.if_last_success_older_than_hours:
            print(
                "Skip: letzter erfolgreicher Run "
                f"{latest_age:.2f}h alt (< {args.if_last_success_older_than_hours:.2f}h)"
            )
            return 0

    snapshot, run_id = collect_and_store(
        base_url=args.base_url,
        fallback_urls=_split_csv(args.fallback_urls),
        db_path=args.db_path,
        username=args.username,
        password=args.password,
        verify_tls=args.verify_tls,
        timeout_seconds=args.timeout,
    )

    print(f"Run gespeichert: #{run_id}")
    print(f"Zeitpunkt: {snapshot.collected_at.isoformat()}")
    print(f"Quelle: {snapshot.dtu_host}")
    print(f"Power: {snapshot.total_power_w} W")
    print(f"Tagesertrag: {snapshot.total_yield_day_wh} Wh")
    print(f"Gesamtertrag: {snapshot.total_yield_total_kwh} kWh")
    print(f"DC-Leistung: {snapshot.dc_power_w} W")
    print(f"Temperatur (avg): {snapshot.avg_temperature_c} °C")
    print(f"Wirkungsgrad (avg): {snapshot.avg_efficiency_pct} %")
    print(f"Inverter gefunden: {len(snapshot.inverters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
