from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
    return slug or "opensolar"


def _to_number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num.is_integer():
        return int(num)
    return round(num, 3)


def _read_latest_snapshot(db_path: str | Path) -> dict[str, Any] | None:
    db_file = Path(db_path)
    if not db_file.exists():
        return None

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute(
            """
            SELECT
                id,
                collected_at,
                dtu_host,
                total_power_w,
                total_yield_day_wh,
                total_yield_total_kwh,
                dc_power_w,
                avg_temperature_c,
                avg_efficiency_pct
            FROM runs
            ORDER BY collected_at DESC
            LIMIT 1
            """
        ).fetchone()

        if latest is None:
            return None

        run_id = int(latest["id"])
        inverters = conn.execute(
            """
            SELECT
                serial,
                name,
                ac_power_w,
                dc_power_w,
                yield_day_wh,
                yield_total_kwh,
                temperature_c,
                efficiency_pct,
                reachable,
                producing
            FROM inverter_stats
            WHERE run_id = ?
            ORDER BY name ASC, serial ASC
            """,
            (run_id,),
        ).fetchall()
    finally:
        conn.close()

    snapshot: dict[str, Any] = {
        "collected_at": latest["collected_at"],
        "dtu_host": latest["dtu_host"],
        "total_power_w": _to_number(latest["total_power_w"]),
        "total_yield_day_wh": _to_number(latest["total_yield_day_wh"]),
        "total_yield_total_kwh": _to_number(latest["total_yield_total_kwh"]),
        "dc_power_w": _to_number(latest["dc_power_w"]),
        "avg_temperature_c": _to_number(latest["avg_temperature_c"]),
        "avg_efficiency_pct": _to_number(latest["avg_efficiency_pct"]),
        "inverter_count": len(inverters),
    }

    inverter_payloads: list[dict[str, Any]] = []
    for row in inverters:
        inverter_payloads.append(
            {
                "serial": str(row["serial"]),
                "name": str(row["name"]),
                "ac_power_w": _to_number(row["ac_power_w"]),
                "dc_power_w": _to_number(row["dc_power_w"]),
                "yield_day_wh": _to_number(row["yield_day_wh"]),
                "yield_total_kwh": _to_number(row["yield_total_kwh"]),
                "temperature_c": _to_number(row["temperature_c"]),
                "efficiency_pct": _to_number(row["efficiency_pct"]),
                "reachable": bool(row["reachable"]) if row["reachable"] is not None else None,
                "producing": bool(row["producing"]) if row["producing"] is not None else None,
                "collected_at": latest["collected_at"],
                "dtu_host": latest["dtu_host"],
            }
        )

    return {"snapshot": snapshot, "inverters": inverter_payloads}


def _publish_sensor_discovery(
    client: mqtt.Client,
    *,
    discovery_prefix: str,
    state_topic: str,
    availability_topic: str,
    node_id: str,
    object_id: str,
    unique_id: str,
    name: str,
    value_key: str,
    device: dict[str, Any],
    unit: str | None = None,
    device_class: str | None = None,
    state_class: str | None = None,
    icon: str | None = None,
) -> None:
    topic = f"{discovery_prefix}/sensor/{node_id}_{object_id}/config"
    payload: dict[str, Any] = {
        "name": name,
        "unique_id": unique_id,
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "value_template": f"{{{{ value_json.{value_key} }}}}",
        "device": device,
    }
    if unit:
        payload["unit_of_measurement"] = unit
    if device_class:
        payload["device_class"] = device_class
    if state_class:
        payload["state_class"] = state_class
    if icon:
        payload["icon"] = icon

    client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)


def _publish_base_discovery(
    client: mqtt.Client,
    *,
    discovery_prefix: str,
    state_topic: str,
    availability_topic: str,
    node_id: str,
    device_name: str,
) -> None:
    device = {
        "identifiers": [f"{node_id}_device"],
        "name": device_name,
        "manufacturer": "KK91",
        "model": "OpenSolar openDTU",
    }
    sensor_defs = [
        ("total_power_w", "openDTU Gesamtleistung", "total_power_w", "W", "power", "measurement", "mdi:flash"),
        ("dc_power_w", "openDTU DC-Leistung", "dc_power_w", "W", "power", "measurement", "mdi:solar-power"),
        (
            "total_yield_day_wh",
            "openDTU Tagesertrag",
            "total_yield_day_wh",
            "Wh",
            "energy",
            "measurement",
            "mdi:solar-panel-large",
        ),
        (
            "total_yield_total_kwh",
            "openDTU Gesamtertrag",
            "total_yield_total_kwh",
            "kWh",
            "energy",
            "total_increasing",
            "mdi:chart-line",
        ),
        (
            "avg_temperature_c",
            "openDTU Temperatur Durchschnitt",
            "avg_temperature_c",
            "°C",
            "temperature",
            "measurement",
            "mdi:thermometer",
        ),
        (
            "avg_efficiency_pct",
            "openDTU Wirkungsgrad Durchschnitt",
            "avg_efficiency_pct",
            "%",
            None,
            "measurement",
            "mdi:speedometer",
        ),
        ("inverter_count", "openDTU Wechselrichter Anzahl", "inverter_count", None, None, None, "mdi:counter"),
    ]

    for object_id, name, value_key, unit, device_class, state_class, icon in sensor_defs:
        _publish_sensor_discovery(
            client,
            discovery_prefix=discovery_prefix,
            state_topic=state_topic,
            availability_topic=availability_topic,
            node_id=node_id,
            object_id=object_id,
            unique_id=f"{node_id}_{object_id}",
            name=name,
            value_key=value_key,
            device=device,
            unit=unit,
            device_class=device_class,
            state_class=state_class,
            icon=icon,
        )

    _publish_sensor_discovery(
        client,
        discovery_prefix=discovery_prefix,
        state_topic=state_topic,
        availability_topic=availability_topic,
        node_id=node_id,
        object_id="collected_at",
        unique_id=f"{node_id}_collected_at",
        name="openDTU Letzter Snapshot",
        value_key="collected_at",
        device=device,
        device_class="timestamp",
        icon="mdi:clock-outline",
    )


def _publish_inverter_discovery(
    client: mqtt.Client,
    *,
    discovery_prefix: str,
    availability_topic: str,
    base_topic: str,
    node_id: str,
    inverter: dict[str, Any],
) -> None:
    serial = str(inverter["serial"])
    serial_slug = _slug(serial)
    inv_topic = f"{base_topic}/inverter/{serial_slug}/state"
    inv_name = str(inverter["name"])

    device = {
        "identifiers": [f"{node_id}_inverter_{serial_slug}"],
        "name": f"{inv_name} ({serial})",
        "manufacturer": "openDTU",
        "model": "Inverter",
    }

    sensor_defs = [
        ("ac_power_w", "AC Leistung", "ac_power_w", "W", "power", "measurement", "mdi:flash-outline"),
        ("dc_power_w", "DC Leistung", "dc_power_w", "W", "power", "measurement", "mdi:solar-power"),
        ("yield_day_wh", "Tagesertrag", "yield_day_wh", "Wh", "energy", "measurement", "mdi:calendar-today"),
        (
            "yield_total_kwh",
            "Gesamtertrag",
            "yield_total_kwh",
            "kWh",
            "energy",
            "total_increasing",
            "mdi:chart-areaspline",
        ),
        (
            "temperature_c",
            "Temperatur",
            "temperature_c",
            "°C",
            "temperature",
            "measurement",
            "mdi:thermometer",
        ),
        ("efficiency_pct", "Wirkungsgrad", "efficiency_pct", "%", None, "measurement", "mdi:speedometer"),
    ]

    for key, name, value_key, unit, device_class, state_class, icon in sensor_defs:
        _publish_sensor_discovery(
            client,
            discovery_prefix=discovery_prefix,
            state_topic=inv_topic,
            availability_topic=availability_topic,
            node_id=node_id,
            object_id=f"{serial_slug}_{key}",
            unique_id=f"{node_id}_{serial_slug}_{key}",
            name=f"{inv_name} {name}",
            value_key=value_key,
            device=device,
            unit=unit,
            device_class=device_class,
            state_class=state_class,
            icon=icon,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MQTT Bridge fuer Home Assistant (openDTU SQLite -> MQTT).")
    parser.add_argument("--db-path", default=os.getenv("OPENDTU_DB_PATH", "data/opendtu_stats.db"))
    parser.add_argument("--mqtt-host", default=os.getenv("HA_MQTT_HOST", ""))
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("HA_MQTT_PORT", "1883")))
    parser.add_argument("--mqtt-username", default=os.getenv("HA_MQTT_USERNAME"))
    parser.add_argument("--mqtt-password", default=os.getenv("HA_MQTT_PASSWORD"))
    parser.add_argument("--mqtt-client-id", default=os.getenv("HA_MQTT_CLIENT_ID", "opensolar-ha-bridge"))
    parser.add_argument("--mqtt-base-topic", default=os.getenv("HA_MQTT_BASE_TOPIC", "opensolar/opendtu"))
    parser.add_argument(
        "--mqtt-discovery-prefix",
        default=os.getenv("HA_MQTT_DISCOVERY_PREFIX", "homeassistant"),
    )
    parser.add_argument("--device-name", default=os.getenv("HA_MQTT_DEVICE_NAME", "OpenSolar openDTU"))
    parser.add_argument(
        "--publish-interval-seconds",
        type=int,
        default=int(os.getenv("HA_PUBLISH_INTERVAL_SECONDS", "30")),
    )
    parser.add_argument(
        "--mqtt-use-tls",
        action="store_true",
        default=_env_bool("HA_MQTT_TLS", False),
        help="TLS fuer MQTT aktivieren",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.mqtt_host:
        print("Fehler: MQTT Host fehlt. Setze HA_MQTT_HOST oder --mqtt-host.")
        return 2

    availability_topic = f"{args.mqtt_base_topic}/availability"
    state_topic = f"{args.mqtt_base_topic}/state"
    node_id = _slug(args.device_name or "opensolar_opendtu")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.mqtt_client_id,
        protocol=mqtt.MQTTv311,
    )
    if args.mqtt_username:
        client.username_pw_set(args.mqtt_username, args.mqtt_password or None)
    if args.mqtt_use_tls:
        client.tls_set()

    client.will_set(availability_topic, payload="offline", qos=1, retain=True)
    try:
        client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    except Exception as exc:
        print(f"Fehler: MQTT-Verbindung fehlgeschlagen ({args.mqtt_host}:{args.mqtt_port}): {exc}")
        return 2
    client.loop_start()

    discovered_inverters: set[str] = set()
    discovery_sent = False

    try:
        client.publish(availability_topic, "online", qos=1, retain=True)
        print(f"[ha-bridge] Connected to MQTT broker {args.mqtt_host}:{args.mqtt_port}")

        while True:
            latest = _read_latest_snapshot(args.db_path)
            if latest is None:
                print("[ha-bridge] Keine Daten in DB gefunden, warte...")
                time.sleep(max(args.publish_interval_seconds, 5))
                continue

            snapshot = latest["snapshot"]
            inverters = latest["inverters"]

            if not discovery_sent:
                _publish_base_discovery(
                    client,
                    discovery_prefix=args.mqtt_discovery_prefix,
                    state_topic=state_topic,
                    availability_topic=availability_topic,
                    node_id=node_id,
                    device_name=args.device_name,
                )
                discovery_sent = True

            for inverter in inverters:
                serial = str(inverter["serial"])
                if serial in discovered_inverters:
                    continue
                _publish_inverter_discovery(
                    client,
                    discovery_prefix=args.mqtt_discovery_prefix,
                    availability_topic=availability_topic,
                    base_topic=args.mqtt_base_topic,
                    node_id=node_id,
                    inverter=inverter,
                )
                discovered_inverters.add(serial)

            client.publish(state_topic, json.dumps(snapshot, ensure_ascii=False), qos=1, retain=True)
            for inverter in inverters:
                serial_slug = _slug(str(inverter["serial"]))
                inv_topic = f"{args.mqtt_base_topic}/inverter/{serial_slug}/state"
                client.publish(inv_topic, json.dumps(inverter, ensure_ascii=False), qos=1, retain=True)

            print(
                f"[ha-bridge] Published snapshot from {snapshot.get('collected_at')} "
                f"(inverters={snapshot.get('inverter_count')})"
            )
            time.sleep(max(args.publish_interval_seconds, 5))
    except KeyboardInterrupt:
        print("[ha-bridge] Stop requested")
    finally:
        try:
            client.publish(availability_topic, "offline", qos=1, retain=True)
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
