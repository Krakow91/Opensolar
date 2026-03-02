from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class DCStringSnapshot:
    channel_index: int | None
    label: str
    power_w: float | None
    voltage_v: float | None
    current_a: float | None
    yield_day_wh: float | None
    yield_total_kwh: float | None
    raw_json: dict[str, Any]


@dataclass
class ACPhaseSnapshot:
    phase_index: int | None
    label: str
    power_w: float | None
    voltage_v: float | None
    current_a: float | None
    frequency_hz: float | None
    power_factor: float | None
    reactive_power_var: float | None
    raw_json: dict[str, Any]


@dataclass
class InverterSnapshot:
    serial: str
    name: str
    ac_power_w: float | None
    dc_power_w: float | None
    yield_day_wh: float | None
    yield_total_kwh: float | None
    temperature_c: float | None
    efficiency_pct: float | None
    reachable: bool | None
    producing: bool | None
    dc_strings: list[DCStringSnapshot]
    ac_phases: list[ACPhaseSnapshot]
    raw_json: dict[str, Any]


@dataclass
class Snapshot:
    collected_at: datetime
    dtu_host: str
    total_power_w: float | None
    total_yield_day_wh: float | None
    total_yield_total_kwh: float | None
    dc_power_w: float | None
    avg_temperature_c: float | None
    avg_efficiency_pct: float | None
    inverters: list[InverterSnapshot]
    raw_json: dict[str, Any]
