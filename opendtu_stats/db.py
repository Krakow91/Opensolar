from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Snapshot


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,
    date_key TEXT NOT NULL,
    dtu_host TEXT NOT NULL,
    total_power_w REAL,
    total_yield_day_wh REAL,
    total_yield_total_kwh REAL,
    dc_power_w REAL,
    avg_temperature_c REAL,
    avg_efficiency_pct REAL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_date_key ON runs(date_key);
CREATE INDEX IF NOT EXISTS idx_runs_host_date ON runs(dtu_host, date_key);

CREATE TABLE IF NOT EXISTS inverter_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    serial TEXT NOT NULL,
    name TEXT NOT NULL,
    ac_power_w REAL,
    dc_power_w REAL,
    yield_day_wh REAL,
    yield_total_kwh REAL,
    temperature_c REAL,
    efficiency_pct REAL,
    reachable INTEGER,
    producing INTEGER,
    raw_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inverter_run_id ON inverter_stats(run_id);
CREATE INDEX IF NOT EXISTS idx_inverter_serial ON inverter_stats(serial);

CREATE TABLE IF NOT EXISTS inverter_dc_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inverter_stat_id INTEGER NOT NULL,
    channel_index INTEGER,
    label TEXT NOT NULL,
    power_w REAL,
    voltage_v REAL,
    current_a REAL,
    yield_day_wh REAL,
    yield_total_kwh REAL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY(inverter_stat_id) REFERENCES inverter_stats(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dc_strings_inverter ON inverter_dc_strings(inverter_stat_id);
CREATE INDEX IF NOT EXISTS idx_dc_strings_channel ON inverter_dc_strings(channel_index);

CREATE TABLE IF NOT EXISTS inverter_ac_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inverter_stat_id INTEGER NOT NULL,
    phase_index INTEGER,
    label TEXT NOT NULL,
    power_w REAL,
    voltage_v REAL,
    current_a REAL,
    frequency_hz REAL,
    power_factor REAL,
    reactive_power_var REAL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY(inverter_stat_id) REFERENCES inverter_stats(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ac_phases_inverter ON inverter_ac_phases(inverter_stat_id);
CREATE INDEX IF NOT EXISTS idx_ac_phases_phase ON inverter_ac_phases(phase_index);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str | Path) -> None:
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    with _connect(db) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def insert_snapshot(db_path: str | Path, snapshot: Snapshot) -> int:
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    with _connect(db) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                collected_at,
                date_key,
                dtu_host,
                total_power_w,
                total_yield_day_wh,
                total_yield_total_kwh,
                dc_power_w,
                avg_temperature_c,
                avg_efficiency_pct,
                raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.collected_at.isoformat(),
                snapshot.collected_at.date().isoformat(),
                snapshot.dtu_host,
                snapshot.total_power_w,
                snapshot.total_yield_day_wh,
                snapshot.total_yield_total_kwh,
                snapshot.dc_power_w,
                snapshot.avg_temperature_c,
                snapshot.avg_efficiency_pct,
                json.dumps(snapshot.raw_json, ensure_ascii=False),
            ),
        )
        run_id = int(cur.lastrowid)

        for inv in snapshot.inverters:
            inv_cur = conn.execute(
                """
                INSERT INTO inverter_stats (
                    run_id,
                    serial,
                    name,
                    ac_power_w,
                    dc_power_w,
                    yield_day_wh,
                    yield_total_kwh,
                    temperature_c,
                    efficiency_pct,
                    reachable,
                    producing,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    inv.serial,
                    inv.name,
                    inv.ac_power_w,
                    inv.dc_power_w,
                    inv.yield_day_wh,
                    inv.yield_total_kwh,
                    inv.temperature_c,
                    inv.efficiency_pct,
                    1 if inv.reachable else 0 if inv.reachable is not None else None,
                    1 if inv.producing else 0 if inv.producing is not None else None,
                    json.dumps(inv.raw_json, ensure_ascii=False),
                ),
            )
            inverter_stat_id = int(inv_cur.lastrowid)

            dc_rows = [
                (
                    inverter_stat_id,
                    dc.channel_index,
                    dc.label,
                    dc.power_w,
                    dc.voltage_v,
                    dc.current_a,
                    dc.yield_day_wh,
                    dc.yield_total_kwh,
                    json.dumps(dc.raw_json, ensure_ascii=False),
                )
                for dc in inv.dc_strings
            ]
            if dc_rows:
                conn.executemany(
                    """
                    INSERT INTO inverter_dc_strings (
                        inverter_stat_id,
                        channel_index,
                        label,
                        power_w,
                        voltage_v,
                        current_a,
                        yield_day_wh,
                        yield_total_kwh,
                        raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    dc_rows,
                )

            ac_rows = [
                (
                    inverter_stat_id,
                    ac.phase_index,
                    ac.label,
                    ac.power_w,
                    ac.voltage_v,
                    ac.current_a,
                    ac.frequency_hz,
                    ac.power_factor,
                    ac.reactive_power_var,
                    json.dumps(ac.raw_json, ensure_ascii=False),
                )
                for ac in inv.ac_phases
            ]
            if ac_rows:
                conn.executemany(
                    """
                    INSERT INTO inverter_ac_phases (
                        inverter_stat_id,
                        phase_index,
                        label,
                        power_w,
                        voltage_v,
                        current_a,
                        frequency_hz,
                        power_factor,
                        reactive_power_var,
                        raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ac_rows,
                )

        conn.commit()

    return run_id
