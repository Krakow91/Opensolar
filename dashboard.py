from __future__ import annotations

import html
import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from opendtu_stats.db import init_db


st.set_page_config(page_title="openDTU Statistik | KK91", page_icon="⚡", layout="wide")


KK91_COLORS = {
    "midnight": "#0C0B1E",
    "panes": "#1A172F",
    "tooltip": "#222037",
    "purple": "#6F4CFF",
    "blue": "#4C66FF",
    "turquoise": "#66D8FF",
    "white": "#FFFFFF",
    "text_dim": "#AFAEC2",
    "line": "#2E2A48",
    "rose": "#ED4A6D",
}


def inject_kk91_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

        :root {
            --kk-midnight: #0C0B1E;
            --kk-panes: #1A172F;
            --kk-tooltip: #222037;
            --kk-purple: #6F4CFF;
            --kk-blue: #4C66FF;
            --kk-turquoise: #66D8FF;
            --kk-white: #FFFFFF;
            --kk-dim: #AFAEC2;
            --kk-line: #2E2A48;
            --kk-rose: #ED4A6D;
        }

        html, body, [class*="css"] {
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
        }

        .stApp {
            background:
              radial-gradient(1200px 500px at -10% -10%, rgba(111, 76, 255, 0.20), transparent 60%),
              radial-gradient(900px 400px at 110% 0%, rgba(102, 216, 255, 0.14), transparent 60%),
              linear-gradient(165deg, #0B0A1A 0%, #0C0B1E 40%, #121029 100%);
            color: var(--kk-white);
        }

        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2.2rem;
            max-width: 1250px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(26,23,47,0.97), rgba(19,17,36,0.97));
            border-right: 1px solid var(--kk-line);
        }

        [data-testid="stSidebar"] * {
            color: var(--kk-white) !important;
        }

        [data-testid="stSidebar"] [data-testid="stTextInput"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: var(--kk-tooltip) !important;
            border: 1px solid var(--kk-line) !important;
            border-radius: 12px !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] svg {
            fill: var(--kk-turquoise);
        }

        .kk91-hero {
            background: linear-gradient(145deg, rgba(26,23,47,0.94), rgba(34,32,55,0.94));
            border: 1px solid var(--kk-line);
            border-radius: 18px;
            padding: 1.25rem 1.4rem 1.35rem 1.4rem;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.30);
            margin-bottom: 0.9rem;
        }

        .kk91-badge {
            display: inline-block;
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--kk-turquoise);
            background: rgba(76,102,255,0.20);
            border: 1px solid rgba(102,216,255,0.35);
            border-radius: 999px;
            padding: 0.28rem 0.62rem;
            margin-bottom: 0.7rem;
        }

        .kk91-hero h1 {
            margin: 0;
            color: var(--kk-white);
            font-size: clamp(1.55rem, 2.4vw, 2.1rem);
            font-weight: 700;
            letter-spacing: 0.01em;
        }

        .kk91-hero p {
            margin: 0.45rem 0 0 0;
            color: var(--kk-dim);
            font-size: 0.97rem;
            line-height: 1.45;
            max-width: 66ch;
        }

        .kk91-side-title {
            color: var(--kk-turquoise);
            font-size: 0.82rem;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            font-weight: 600;
            margin: 0.1rem 0 0.55rem 0;
        }

        .kk91-side-subtitle {
            color: var(--kk-dim);
            font-size: 0.82rem;
            margin-bottom: 0.9rem;
        }

        .kk91-metric {
            border: 1px solid var(--kk-line);
            background: linear-gradient(160deg, rgba(26,23,47,0.96), rgba(34,32,55,0.94));
            border-radius: 16px;
            padding: 0.78rem 0.95rem 0.84rem 0.95rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            min-height: 105px;
        }

        .kk91-metric__label {
            color: var(--kk-dim);
            font-size: 0.82rem;
            letter-spacing: 0.02em;
            margin-bottom: 0.36rem;
        }

        .kk91-metric__value {
            color: var(--kk-white);
            font-family: "JetBrains Mono", "Consolas", monospace;
            font-size: 1.18rem;
            font-weight: 600;
            line-height: 1.25;
            margin-bottom: 0.24rem;
            word-break: break-word;
        }

        .kk91-metric__meta {
            color: var(--kk-turquoise);
            font-size: 0.72rem;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            opacity: 0.92;
        }

        .kk91-status {
            margin: 0.75rem 0 0.55rem;
            border: 1px solid var(--kk-line);
            border-left: 4px solid var(--kk-blue);
            background: rgba(26,23,47,0.84);
            border-radius: 12px;
            padding: 0.6rem 0.82rem;
            color: var(--kk-dim);
            font-size: 0.88rem;
        }

        .kk91-status strong {
            color: var(--kk-white);
            font-weight: 600;
        }

        .kk91-section {
            margin: 1.2rem 0 0.42rem;
            border-left: 4px solid var(--kk-purple);
            padding-left: 0.58rem;
        }

        .kk91-section h3 {
            margin: 0;
            color: var(--kk-white);
            font-size: 1.05rem;
            letter-spacing: 0.01em;
        }

        .kk91-section p {
            margin: 0.14rem 0 0 0;
            color: var(--kk-dim);
            font-size: 0.82rem;
        }

        [data-testid="stPlotlyChart"],
        [data-testid="stDataFrame"] {
            background: linear-gradient(160deg, rgba(26,23,47,0.95), rgba(34,32,55,0.90));
            border: 1px solid var(--kk-line);
            border-radius: 14px;
            padding: 0.55rem;
        }

        .stAlert {
            border-radius: 12px !important;
            border: 1px solid var(--kk-line) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def section_heading(title: str, subtitle: str | None = None) -> str:
    subtitle_html = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    return f"""
    <div class="kk91-section">
      <h3>{html.escape(title)}</h3>
      {subtitle_html}
    </div>
    """


def metric_card(label: str, value: str, meta: str) -> str:
    return f"""
    <div class="kk91-metric">
      <div class="kk91-metric__label">{html.escape(label)}</div>
      <div class="kk91-metric__value">{html.escape(value)}</div>
      <div class="kk91-metric__meta">{html.escape(meta)}</div>
    </div>
    """


def style_plotly(fig, accent: str | None = None) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Space Grotesk, Segoe UI, sans-serif", "color": KK91_COLORS["white"], "size": 13},
        margin={"l": 8, "r": 8, "t": 42, "b": 8},
        legend={
            "bgcolor": "rgba(12,11,30,0.35)",
            "bordercolor": KK91_COLORS["line"],
            "borderwidth": 1,
            "font": {"color": KK91_COLORS["text_dim"]},
        },
        title={"font": {"size": 18, "color": KK91_COLORS["white"]}},
        colorway=[
            KK91_COLORS["turquoise"],
            KK91_COLORS["purple"],
            KK91_COLORS["blue"],
            KK91_COLORS["rose"],
        ],
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=KK91_COLORS["line"],
        linecolor=KK91_COLORS["line"],
        tickfont={"color": KK91_COLORS["text_dim"]},
        title_font={"color": KK91_COLORS["text_dim"]},
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=KK91_COLORS["line"],
        linecolor=KK91_COLORS["line"],
        tickfont={"color": KK91_COLORS["text_dim"]},
        title_font={"color": KK91_COLORS["text_dim"]},
        zeroline=False,
    )

    if accent:
        for trace in fig.data:
            if hasattr(trace, "line"):
                trace.line.color = accent
                trace.line.width = 3
            if hasattr(trace, "marker"):
                trace.marker.color = accent
                if hasattr(trace.marker, "line"):
                    trace.marker.line.color = KK91_COLORS["blue"]
                    trace.marker.line.width = 1


def main() -> None:
    inject_kk91_styles()

    st.markdown(
        """
        <div class="kk91-hero">
          <div class="kk91-badge">KK91 Energy Console</div>
          <h1>openDTU Tagesstatistik</h1>
          <p>Live-Leistung, Tagesertrag und Wechselrichter-Details in einer Oberfläche im KK91-Look.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_db = os.getenv("OPENDTU_DB_PATH", "data/opendtu_stats.db")
    with st.sidebar:
        st.markdown('<div class="kk91-side-title">Control Deck</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="kk91-side-subtitle">Filtere Host und Wechselrichter für die aktuelle Ansicht.</div>',
            unsafe_allow_html=True,
        )
        db_path = st.text_input("SQLite-Datei", value=default_db)
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
    inverter_map = {f"{row['name']} ({row['serial']})": row["serial"] for _, row in inverter_options_df.iterrows()}
    inverter_labels = ["Alle"] + list(inverter_map.keys())
    selected_inverter_label = st.sidebar.selectbox("Wechselrichter", inverter_labels, index=0)
    selected_serial = None if selected_inverter_label == "Alle" else inverter_map.get(selected_inverter_label)

    totals_df = query_daily_totals(conn, selected_host)
    inverter_df = query_daily_inverter_stats(conn, selected_host, selected_serial)
    dc_strings_df = query_latest_dc_strings(conn, selected_host, selected_serial)
    ac_phases_df = query_latest_ac_phases(conn, selected_host, selected_serial)

    if totals_df.empty:
        st.warning("Keine Daten in der Datenbank vorhanden.")
        return

    totals_df["day"] = pd.to_datetime(totals_df["day"])
    totals_df = totals_df.sort_values("day")
    if not inverter_df.empty:
        inverter_df["day"] = pd.to_datetime(inverter_df["day"])
        inverter_df = inverter_df.sort_values("day")

    latest = totals_df.iloc[-1]

    metric_data = [
        ("Tagesertrag", f"{_fmt(latest['total_yield_day_wh'], 1)} Wh", "YieldDay"),
        ("Gesamtertrag", f"{_fmt(latest['total_yield_total_kwh'], 3)} kWh", "YieldTotal"),
        ("DC-Leistung", f"{_fmt(latest['dc_power_w'], 1)} W", "DC Power"),
        ("Wirkungsgrad", f"{_fmt(latest['avg_efficiency_pct'], 2)} %", "Efficiency"),
    ]
    metric_cols = st.columns(4)
    for col, (label, value, meta) in zip(metric_cols, metric_data):
        with col:
            st.markdown(metric_card(label, value, meta), unsafe_allow_html=True)

    latest_collected = html.escape(str(latest["collected_at"]))
    latest_host = html.escape(str(latest["dtu_host"]))
    st.markdown(
        f'<div class="kk91-status">Letzter Snapshot: <strong>{latest_collected}</strong> | Host: <strong>{latest_host}</strong></div>',
        unsafe_allow_html=True,
    )

    fig_day = px.bar(
        totals_df,
        x="day",
        y="total_yield_day_wh",
        title="Tagesertrag pro Tag (Wh)",
        labels={"day": "Tag", "total_yield_day_wh": "Wh"},
    )
    style_plotly(fig_day)
    fig_day.update_traces(marker_color=KK91_COLORS["purple"])
    st.markdown(section_heading("Ertrag", "Tages- und Gesamtentwicklung"), unsafe_allow_html=True)
    st.plotly_chart(fig_day, use_container_width=True)

    fig_total = px.line(
        totals_df,
        x="day",
        y="total_yield_total_kwh",
        markers=True,
        title="Gesamtertrag Verlauf (kWh)",
        labels={"day": "Tag", "total_yield_total_kwh": "kWh"},
    )
    style_plotly(fig_total, accent=KK91_COLORS["turquoise"])
    st.plotly_chart(fig_total, use_container_width=True)

    st.markdown(section_heading("Temperatur und Wirkungsgrad"), unsafe_allow_html=True)
    temp_eff_cols = st.columns(2)
    fig_temp = px.line(
        totals_df,
        x="day",
        y="avg_temperature_c",
        markers=True,
        title="Durchschnittliche Temperatur (°C)",
        labels={"day": "Tag", "avg_temperature_c": "°C"},
    )
    style_plotly(fig_temp, accent=KK91_COLORS["rose"])
    temp_eff_cols[0].plotly_chart(fig_temp, use_container_width=True)

    fig_eff = px.line(
        totals_df,
        x="day",
        y="avg_efficiency_pct",
        markers=True,
        title="Durchschnittlicher Wirkungsgrad (%)",
        labels={"day": "Tag", "avg_efficiency_pct": "%"},
    )
    style_plotly(fig_eff, accent=KK91_COLORS["blue"])
    temp_eff_cols[1].plotly_chart(fig_eff, use_container_width=True)

    st.markdown(section_heading("Wechselrichter-Details"), unsafe_allow_html=True)
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
            style_plotly(fig_inv)
        else:
            fig_inv = px.line(
                inverter_df,
                x="day",
                y="yield_day_wh",
                markers=True,
                title="Tagesertrag des ausgewählten Wechselrichters (Wh)",
                labels={"day": "Tag", "yield_day_wh": "Wh"},
            )
            style_plotly(fig_inv, accent=KK91_COLORS["turquoise"])
        st.plotly_chart(fig_inv, use_container_width=True)

        preview = inverter_df.sort_values("day", ascending=False).copy()
        preview["day"] = preview["day"].dt.strftime("%Y-%m-%d")
        st.dataframe(preview, use_container_width=True)

    st.markdown(section_heading("String- und Phasenwerte (letzter Snapshot)"), unsafe_allow_html=True)

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
            style_plotly(fig_dc)
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
    st.markdown(section_heading("Gesamtdaten"), unsafe_allow_html=True)
    st.dataframe(table_df, use_container_width=True)


if __name__ == "__main__":
    main()
