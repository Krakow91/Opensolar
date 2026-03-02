from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from opendtu_stats.db import init_db


st.set_page_config(page_title="openDTU Statistik", layout="wide")


@st.cache_resource
def open_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_daily_totals(conn: sqlite3.Connection, host: str | None) -> pd.DataFrame:
    sql = """
    WITH ranked AS (
        SELECT
            id,
            dtu_host,
            collected_at,
            DATE(collected_at) AS day,
            total_power_w,
            total_yield_day_wh,
            total_yield_total_kwh,
            dc_power_w,
            avg_temperature_c,
            avg_efficiency_pct,
            ROW_NUMBER() OVER (
                PARTITION BY dtu_host, DATE(collected_at)
                ORDER BY collected_at DESC
            ) AS rn
        FROM runs
        WHERE (? IS NULL OR dtu_host = ?)
    )
    SELECT
        id,
        dtu_host,
        day,
        collected_at,
        total_power_w,
        total_yield_day_wh,
        total_yield_total_kwh,
        dc_power_w,
        avg_temperature_c,
        avg_efficiency_pct
    FROM ranked
    WHERE rn = 1
    ORDER BY day ASC;
    """
    return pd.read_sql_query(sql, conn, params=(host, host))


def query_inverter_options(conn: sqlite3.Connection, host: str | None) -> pd.DataFrame:
    sql = """
    SELECT DISTINCT i.serial, i.name
    FROM inverter_stats i
    JOIN runs r ON r.id = i.run_id
    WHERE (? IS NULL OR r.dtu_host = ?)
    ORDER BY i.name ASC, i.serial ASC;
    """
    return pd.read_sql_query(sql, conn, params=(host, host))


def query_daily_inverter_stats(conn: sqlite3.Connection, host: str | None, serial: str | None) -> pd.DataFrame:
    sql = """
    WITH ranked_runs AS (
        SELECT
            id,
            dtu_host,
            DATE(collected_at) AS day,
            ROW_NUMBER() OVER (
                PARTITION BY dtu_host, DATE(collected_at)
                ORDER BY collected_at DESC
            ) AS rn
        FROM runs
        WHERE (? IS NULL OR dtu_host = ?)
    )
    SELECT
        rr.day,
        i.serial,
        i.name,
        i.ac_power_w,
        i.dc_power_w,
        i.yield_day_wh,
        i.yield_total_kwh,
        i.temperature_c,
        i.efficiency_pct
    FROM ranked_runs rr
    JOIN inverter_stats i ON i.run_id = rr.id
    WHERE rr.rn = 1
      AND (? IS NULL OR i.serial = ?)
    ORDER BY rr.day ASC;
    """
    return pd.read_sql_query(sql, conn, params=(host, host, serial, serial))


def query_latest_dc_strings(conn: sqlite3.Connection, host: str | None, serial: str | None) -> pd.DataFrame:
    sql = """
    WITH latest_run AS (
        SELECT id
        FROM runs
        WHERE (? IS NULL OR dtu_host = ?)
        ORDER BY collected_at DESC
        LIMIT 1
    )
    SELECT
        r.collected_at,
        i.serial,
        i.name,
        d.channel_index,
        d.label,
        d.power_w,
        d.voltage_v,
        d.current_a,
        d.yield_day_wh,
        d.yield_total_kwh
    FROM latest_run lr
    JOIN runs r ON r.id = lr.id
    JOIN inverter_stats i ON i.run_id = r.id
    JOIN inverter_dc_strings d ON d.inverter_stat_id = i.id
    WHERE (? IS NULL OR i.serial = ?)
    ORDER BY i.name ASC, d.channel_index ASC, d.label ASC;
    """
    return pd.read_sql_query(sql, conn, params=(host, host, serial, serial))


def query_latest_ac_phases(conn: sqlite3.Connection, host: str | None, serial: str | None) -> pd.DataFrame:
    sql = """
    WITH latest_run AS (
        SELECT id
        FROM runs
        WHERE (? IS NULL OR dtu_host = ?)
        ORDER BY collected_at DESC
        LIMIT 1
    )
    SELECT
        r.collected_at,
        i.serial,
        i.name,
        a.phase_index,
        a.label,
        a.power_w,
        a.voltage_v,
        a.current_a,
        a.frequency_hz,
        a.power_factor,
        a.reactive_power_var
    FROM latest_run lr
    JOIN runs r ON r.id = lr.id
    JOIN inverter_stats i ON i.run_id = r.id
    JOIN inverter_ac_phases a ON a.inverter_stat_id = i.id
    WHERE (? IS NULL OR i.serial = ?)
    ORDER BY i.name ASC, a.phase_index ASC, a.label ASC;
    """
    return pd.read_sql_query(sql, conn, params=(host, host, serial, serial))


def _fmt(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}f}"


def main() -> None:
    st.title("openDTU Tagesstatistik")

    default_db = os.getenv("OPENDTU_DB_PATH", "data/opendtu_stats.db")
    db_path = st.sidebar.text_input("SQLite-Datei", value=default_db)
    db_file = Path(db_path)

    if not db_file.exists():
        st.error(f"DB nicht gefunden: {db_file.resolve()}")
        st.info("Starte zuerst den Collector, damit Daten erzeugt werden.")
        return

    # Migriert die DB bei neuen Tabellen automatisch.
    init_db(str(db_file))
    conn = open_connection(str(db_file))

    hosts_df = pd.read_sql_query("SELECT DISTINCT dtu_host FROM runs ORDER BY dtu_host", conn)
    host_options = ["Alle"] + hosts_df["dtu_host"].tolist()
    selected_host_text = st.sidebar.selectbox("openDTU Host", host_options, index=0)
    selected_host = None if selected_host_text == "Alle" else selected_host_text

    inverter_options_df = query_inverter_options(conn, selected_host)
    inverter_labels = ["Alle"] + [f"{row['name']} ({row['serial']})" for _, row in inverter_options_df.iterrows()]
    selected_inverter_label = st.sidebar.selectbox("Wechselrichter", inverter_labels, index=0)

    selected_serial = None
    if selected_inverter_label != "Alle":
        for _, row in inverter_options_df.iterrows():
            label = f"{row['name']} ({row['serial']})"
            if label == selected_inverter_label:
                selected_serial = row["serial"]
                break

    totals_df = query_daily_totals(conn, selected_host)
    inverter_df = query_daily_inverter_stats(conn, selected_host, selected_serial)
    dc_strings_df = query_latest_dc_strings(conn, selected_host, selected_serial)
    ac_phases_df = query_latest_ac_phases(conn, selected_host, selected_serial)

    if totals_df.empty:
        st.warning("Keine Daten in der Datenbank vorhanden.")
        return

    totals_df["day"] = pd.to_datetime(totals_df["day"])
    if not inverter_df.empty:
        inverter_df["day"] = pd.to_datetime(inverter_df["day"])

    latest = totals_df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tagesertrag", f"{_fmt(latest['total_yield_day_wh'], 1)} Wh")
    c2.metric("Gesamtertrag", f"{_fmt(latest['total_yield_total_kwh'], 3)} kWh")
    c3.metric("DC-Leistung", f"{_fmt(latest['dc_power_w'], 1)} W")
    c4.metric("Wirkungsgrad", f"{_fmt(latest['avg_efficiency_pct'], 2)} %")

    st.caption(f"Letzter Snapshot: {latest['collected_at']} | Host: {latest['dtu_host']}")

    fig_day = px.bar(
        totals_df,
        x="day",
        y="total_yield_day_wh",
        title="Tagesertrag pro Tag (Wh)",
        labels={"day": "Tag", "total_yield_day_wh": "Wh"},
    )
    st.plotly_chart(fig_day, use_container_width=True)

    fig_total = px.line(
        totals_df,
        x="day",
        y="total_yield_total_kwh",
        markers=True,
        title="Gesamtertrag Verlauf (kWh)",
        labels={"day": "Tag", "total_yield_total_kwh": "kWh"},
    )
    st.plotly_chart(fig_total, use_container_width=True)

    temp_eff_cols = st.columns(2)
    fig_temp = px.line(
        totals_df,
        x="day",
        y="avg_temperature_c",
        markers=True,
        title="Durchschnittliche Temperatur (°C)",
        labels={"day": "Tag", "avg_temperature_c": "°C"},
    )
    temp_eff_cols[0].plotly_chart(fig_temp, use_container_width=True)

    fig_eff = px.line(
        totals_df,
        x="day",
        y="avg_efficiency_pct",
        markers=True,
        title="Durchschnittlicher Wirkungsgrad (%)",
        labels={"day": "Tag", "avg_efficiency_pct": "%"},
    )
    temp_eff_cols[1].plotly_chart(fig_eff, use_container_width=True)

    st.subheader("Wechselrichter-Details")
    if inverter_df.empty:
        st.info("Keine Wechselrichter-Daten für den Filter gefunden.")
    else:
        if selected_serial is None:
            fig_inv = px.bar(
                inverter_df,
                x="day",
                y="yield_day_wh",
                color="name",
                barmode="group",
                title="Tagesertrag je Wechselrichter (Wh)",
                labels={"day": "Tag", "yield_day_wh": "Wh", "name": "Wechselrichter"},
            )
        else:
            fig_inv = px.line(
                inverter_df,
                x="day",
                y="yield_day_wh",
                markers=True,
                title="Tagesertrag des ausgewählten Wechselrichters (Wh)",
                labels={"day": "Tag", "yield_day_wh": "Wh"},
            )
        st.plotly_chart(fig_inv, use_container_width=True)

        preview = inverter_df.sort_values("day", ascending=False).copy()
        preview["day"] = preview["day"].dt.strftime("%Y-%m-%d")
        st.dataframe(preview, use_container_width=True)

    st.subheader("String- und Phasenwerte (letzter Snapshot)")

    if dc_strings_df.empty and ac_phases_df.empty:
        st.info("Noch keine DC-String/AC-Phasenwerte vorhanden. Führe einmal den Collector aus.")
    else:
        if not dc_strings_df.empty:
            dc_strings_df = dc_strings_df.copy()
            dc_strings_df["Wechselrichter"] = dc_strings_df["name"] + " (" + dc_strings_df["serial"] + ")"

            fig_dc = px.bar(
                dc_strings_df,
                x="label",
                y="power_w",
                color="Wechselrichter",
                barmode="group",
                title="DC String Leistung (W)",
                labels={"label": "String", "power_w": "W"},
            )
            st.plotly_chart(fig_dc, use_container_width=True)

            dc_view = dc_strings_df[
                [
                    "Wechselrichter",
                    "label",
                    "power_w",
                    "voltage_v",
                    "current_a",
                    "yield_day_wh",
                    "yield_total_kwh",
                ]
            ].rename(
                columns={
                    "label": "String",
                    "power_w": "Leistung (W)",
                    "voltage_v": "Spannung (V)",
                    "current_a": "Strom (A)",
                    "yield_day_wh": "Tagesertrag (Wh)",
                    "yield_total_kwh": "Gesamtertrag (kWh)",
                }
            )
            st.dataframe(dc_view, use_container_width=True)

        if not ac_phases_df.empty:
            ac_phases_df = ac_phases_df.copy()
            ac_phases_df["Wechselrichter"] = ac_phases_df["name"] + " (" + ac_phases_df["serial"] + ")"

            ac_view = ac_phases_df[
                [
                    "Wechselrichter",
                    "label",
                    "power_w",
                    "voltage_v",
                    "current_a",
                    "frequency_hz",
                    "power_factor",
                    "reactive_power_var",
                ]
            ].rename(
                columns={
                    "label": "Phase",
                    "power_w": "Leistung (W)",
                    "voltage_v": "Spannung (V)",
                    "current_a": "Strom (A)",
                    "frequency_hz": "Frequenz (Hz)",
                    "power_factor": "Leistungsfaktor",
                    "reactive_power_var": "Blindleistung (var)",
                }
            )
            st.dataframe(ac_view, use_container_width=True)

    table_df = totals_df.copy().sort_values("day", ascending=False)
    table_df["day"] = table_df["day"].dt.strftime("%Y-%m-%d")
    st.subheader("Gesamtdaten")
    st.dataframe(table_df, use_container_width=True)


if __name__ == "__main__":
    main()
