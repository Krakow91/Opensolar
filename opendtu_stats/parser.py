from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import ACPhaseSnapshot, DCStringSnapshot, InverterSnapshot, Snapshot


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return None


def _parse_index(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _metric(metric_container: Any, *keys: str) -> float | None:
    if not isinstance(metric_container, dict):
        return None

    for key in keys:
        if key in metric_container:
            value = metric_container[key]
            if isinstance(value, dict) and "v" in value:
                return _to_float(value.get("v"))
            return _to_float(value)

    return None


def _first_inv(inv_block: Any) -> dict[str, Any]:
    if not isinstance(inv_block, dict) or not inv_block:
        return {}
    if "0" in inv_block and isinstance(inv_block["0"], dict):
        return inv_block["0"]
    for value in inv_block.values():
        if isinstance(value, dict):
            return value
    return {}


def _iter_channel_items(channel_block: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(channel_block, dict):
        return []

    items: list[tuple[str, dict[str, Any]]] = []
    for key, value in channel_block.items():
        if isinstance(value, dict):
            items.append((str(key), value))

    def _sort_key(item: tuple[str, dict[str, Any]]) -> tuple[int, str]:
        key = item[0]
        if key.isdigit():
            return (0, f"{int(key):03d}")
        return (1, key)

    items.sort(key=_sort_key)
    return items


def _sum_channel_metric(channel_block: Any, key: str) -> float | None:
    values: list[float] = []
    for _, channel in _iter_channel_items(channel_block):
        metric = _metric(channel, key)
        if metric is not None:
            values.append(metric)

    if not values:
        return None
    return float(sum(values))


def _avg(values: list[float | None]) -> float | None:
    real = [v for v in values if v is not None]
    if not real:
        return None
    return float(sum(real) / len(real))


def _parse_dc_strings(dc_block: Any) -> list[DCStringSnapshot]:
    dc_strings: list[DCStringSnapshot] = []

    for key, channel in _iter_channel_items(dc_block):
        idx = _parse_index(key)
        label_idx = (idx + 1) if idx is not None else None
        label = f"String {label_idx}" if label_idx is not None else f"String {key}"

        dc_strings.append(
            DCStringSnapshot(
                channel_index=label_idx,
                label=label,
                power_w=_metric(channel, "Power"),
                voltage_v=_metric(channel, "Voltage"),
                current_a=_metric(channel, "Current"),
                yield_day_wh=_metric(channel, "YieldDay"),
                yield_total_kwh=_metric(channel, "YieldTotal"),
                raw_json=channel,
            )
        )

    return dc_strings


def _parse_ac_phases(ac_block: Any) -> list[ACPhaseSnapshot]:
    ac_phases: list[ACPhaseSnapshot] = []

    for key, phase in _iter_channel_items(ac_block):
        idx = _parse_index(key)
        label_idx = (idx + 1) if idx is not None else None
        label = f"Phase {label_idx}" if label_idx is not None else f"Phase {key}"

        ac_phases.append(
            ACPhaseSnapshot(
                phase_index=label_idx,
                label=label,
                power_w=_metric(phase, "Power"),
                voltage_v=_metric(phase, "Voltage"),
                current_a=_metric(phase, "Current"),
                frequency_hz=_metric(phase, "Frequency"),
                power_factor=_metric(phase, "PowerFactor"),
                reactive_power_var=_metric(phase, "ReactivePower"),
                raw_json=phase,
            )
        )

    return ac_phases


def _parse_inverter(inverter: dict[str, Any]) -> InverterSnapshot:
    inv = _first_inv(inverter.get("INV"))
    dc_channels = inverter.get("DC")
    ac_channels = inverter.get("AC")

    dc_strings = _parse_dc_strings(dc_channels)
    ac_phases = _parse_ac_phases(ac_channels)

    dc_power = _metric(inv, "Power DC")
    if dc_power is None:
        dc_power = _sum_channel_metric(dc_channels, "Power")

    yield_day = _metric(inv, "YieldDay")
    if yield_day is None:
        yield_day = _sum_channel_metric(dc_channels, "YieldDay")

    yield_total_kwh = _metric(inv, "YieldTotal")
    if yield_total_kwh is None:
        yield_total_kwh = _sum_channel_metric(dc_channels, "YieldTotal")

    ac_first = _first_inv(ac_channels)
    ac_power = _metric(ac_first, "Power")

    temperature = _metric(inv, "Temperature")
    efficiency = _metric(inv, "Efficiency")

    return InverterSnapshot(
        serial=str(inverter.get("serial", "unknown")),
        name=str(inverter.get("name", "Unbekannt")),
        ac_power_w=ac_power,
        dc_power_w=dc_power,
        yield_day_wh=yield_day,
        yield_total_kwh=yield_total_kwh,
        temperature_c=temperature,
        efficiency_pct=efficiency,
        reachable=_to_bool(inverter.get("reachable")),
        producing=_to_bool(inverter.get("producing")),
        dc_strings=dc_strings,
        ac_phases=ac_phases,
        raw_json=inverter,
    )


def parse_status_payload(payload: dict[str, Any], dtu_host: str) -> Snapshot:
    now = datetime.now().astimezone()

    total = payload.get("total", {})
    inverters_raw = payload.get("inverters", [])
    inverters: list[InverterSnapshot] = []

    if isinstance(inverters_raw, list):
        for inverter in inverters_raw:
            if isinstance(inverter, dict):
                inverters.append(_parse_inverter(inverter))

    total_power = _metric(total, "Power")
    total_yield_day = _metric(total, "YieldDay")
    total_yield_kwh = _metric(total, "YieldTotal")

    dc_power_total = _metric(total, "Power DC")
    if dc_power_total is None:
        dc_power_total = _sum_channel_metric(payload.get("dc", {}), "Power")
    if dc_power_total is None:
        dc_power_total = sum(v.dc_power_w or 0.0 for v in inverters) if inverters else None

    avg_temperature = _avg([inv.temperature_c for inv in inverters])
    avg_efficiency = _avg([inv.efficiency_pct for inv in inverters])

    return Snapshot(
        collected_at=now,
        dtu_host=dtu_host,
        total_power_w=total_power,
        total_yield_day_wh=total_yield_day,
        total_yield_total_kwh=total_yield_kwh,
        dc_power_w=dc_power_total,
        avg_temperature_c=avg_temperature,
        avg_efficiency_pct=avg_efficiency,
        inverters=inverters,
        raw_json=payload,
    )
