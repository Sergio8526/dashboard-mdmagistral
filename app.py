"""
Dashboard de Comisiones — MD Magistral
Fuente: API Intelapp
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.request
import json
import ssl
from datetime import datetime

# ── Configuracion de la pagina ────────────────────────────────────────────────
st.set_page_config(
    page_title="Comisiones MD Magistral",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estilos CSS personalizados ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Fondo general */
    .main { background-color: #F5F7FA; }

    /* Tarjetas KPI */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 5px solid #1F4E79;
        margin-bottom: 8px;
    }
    .kpi-label {
        font-size: 13px;
        color: #666;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 800;
        color: #1F4E79;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 12px;
        color: #999;
        margin-top: 4px;
    }

    /* Header */
    .header-box {
        background: linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%);
        border-radius: 12px;
        padding: 20px 28px;
        color: white;
        margin-bottom: 24px;
    }
    .header-title {
        font-size: 22px;
        font-weight: 800;
        margin: 0;
    }
    .header-sub {
        font-size: 13px;
        opacity: 0.8;
        margin-top: 4px;
    }

    /* Badge de estado */
    .badge-completa  { background:#C6EFCE; color:#375623; padding:3px 10px; border-radius:20px; font-weight:700; font-size:12px; }
    .badge-parcial   { background:#FFEB9C; color:#7D6608; padding:3px 10px; border-radius:20px; font-weight:700; font-size:12px; }
    .badge-no-gana   { background:#FFC7CE; color:#9C0006; padding:3px 10px; border-radius:20px; font-weight:700; font-size:12px; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #1F4E79; }
    section[data-testid="stSidebar"] * { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ── Configuracion API ─────────────────────────────────────────────────────────
TOKEN      = st.secrets["TOKEN"]
BASE       = "https://intelnova-api.azurewebsites.net/api"
UMBRAL_MIN = 0.80
UMBRAL_MAX = 0.99

ctx = ssl.create_default_context()

# ── Funciones de API ──────────────────────────────────────────────────────────
def api_get(endpoint):
    req = urllib.request.Request(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())

def api_post(endpoint, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/{endpoint}", data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())

def calcular_comision(cob_med, cob_pdv, meta_md, meta_pdv):
    cob_comb = (cob_med + cob_pdv) / 2
    if cob_comb < UMBRAL_MIN:
        return 0, 0, 0, cob_comb, "NO GANA"
    if cob_comb >= UMBRAL_MAX:
        com_med = meta_md
        com_pdv = meta_pdv
        estado  = "COMPLETA"
    else:
        com_med = round(cob_med * meta_md)
        com_pdv = round(cob_pdv * meta_pdv)
        estado  = "PARCIAL"
    return com_med, com_pdv, com_med + com_pdv, cob_comb, estado

# ── Carga de ciclos disponibles ───────────────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_ciclos():
    ciclos = api_get("CyclesReport")
    return sorted(ciclos, key=lambda x: x["id"], reverse=True)  # mas reciente primero

# ── Carga de cobertura por ciclo ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_cobertura(ciclo_id):
    from collections import defaultdict

    # Medicos
    med_raw       = api_post("CoverageReport", {"VisitTargetType": 0, "IsFrequecy": True})
    med_registros = med_raw.get("answerQuery", [])

    reps_med = defaultdict(lambda: {"panel": 0, "visitados": 0, "frecuencia": 0, "region": ""})
    for reg in med_registros:
        nombre = f"{reg['userLastname']} {reg['userName']}"
        reps_med[nombre]["panel"] += 1
        reps_med[nombre]["region"] = reg.get("region") or ""
        ciclo_data = next((c for c in reg.get("cycles", []) if c["id"] == ciclo_id), None)
        if ciclo_data is not None:
            if ciclo_data["value"] > 0:
                reps_med[nombre]["visitados"] += 1
            reps_med[nombre]["frecuencia"] += ciclo_data["value"]
        else:
            if reg.get("contact") and reg["contact"] > 0:
                reps_med[nombre]["visitados"] += 1
            reps_med[nombre]["frecuencia"] += reg.get("frecuency") or 0

    # PDV
    pdv_raw       = api_post("CoverageReport", {"VisitTargetType": 1, "IsFrequecy": True})
    pdv_registros = pdv_raw.get("answerQuery", [])

    reps_pdv = defaultdict(lambda: {"panel": 0, "visitados": 0, "frecuencia": 0})
    for reg in pdv_registros:
        nombre = f"{reg['userLastname']} {reg['userName']}"
        reps_pdv[nombre]["panel"] += 1
        ciclo_data = next((c for c in reg.get("cycles", []) if c["id"] == ciclo_id), None)
        if ciclo_data is not None:
            if ciclo_data["value"] > 0:
                reps_pdv[nombre]["visitados"] += 1
            reps_pdv[nombre]["frecuencia"] += ciclo_data["value"]
        else:
            if reg.get("contact") and reg["contact"] > 0:
                reps_pdv[nombre]["visitados"] += 1
            reps_pdv[nombre]["frecuencia"] += reg.get("frecuency") or 0

    # Consolidar
    todos = sorted(set(list(reps_med.keys()) + list(reps_pdv.keys())))
    filas = []
    for rep in todos:
        m = reps_med.get(rep, {"panel": 0, "visitados": 0, "frecuencia": 0, "region": ""})
        p = reps_pdv.get(rep, {"panel": 0, "visitados": 0, "frecuencia": 0})

        cob_med  = m["visitados"] / m["panel"] if m["panel"] > 0 else 0
        cob_pdv  = p["visitados"] / p["panel"] if p["panel"] > 0 else 0
        prom_med = round(m["frecuencia"] / m["panel"], 2) if m["panel"] > 0 else 0
        prom_pdv = round(p["frecuencia"] / p["panel"], 2) if p["panel"] > 0 else 0

        filas.append({
            "Representante": rep,
            "Region":        m["region"],
            "Panel_Med":     m["panel"],
            "Visit_Med":     m["visitados"],
            "Cob_Med":       round(cob_med, 4),
            "Frec_Med":      m["frecuencia"],
            "Prom_Med":      prom_med,
            "Panel_PDV":     p["panel"],
            "Visit_PDV":     p["visitados"],
            "Cob_PDV":       round(cob_pdv, 4),
            "Frec_PDV":      p["frecuencia"],
            "Prom_PDV":      prom_pdv,
        })

    return pd.DataFrame(filas)

def agregar_comisiones(df, meta_md, meta_pdv):
    filas = []
    for _, row in df.iterrows():
        com_med, com_pdv, com_total, cob_comb, estado = calcular_comision(
            row["Cob_Med"], row["Cob_PDV"], meta_md, meta_pdv
        )
        filas.append({
            **row.to_dict(),
            "Pct_Cumplimiento": round(cob_comb, 4),
            "Comision_Med":     com_med,
            "Comision_PDV":     com_pdv,
            "Comision_Total":   com_total,
            "Estado":           estado,
            "Meta_Total":       meta_md + meta_pdv,
        })
    return pd.DataFrame(filas)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 MD Magistral")
    st.markdown("---")

    # Selector de ciclo
    st.markdown("**Ciclo**")
    try:
        ciclos_lista   = cargar_ciclos()
        nombres_ciclos = [c["name"] for c in ciclos_lista]
        ciclo_sel_nombre = st.selectbox("Ciclo", nombres_ciclos, label_visibility="collapsed")
        ciclo_sel_id   = next(c["id"] for c in ciclos_lista if c["name"] == ciclo_sel_nombre)
    except Exception:
        st.warning("No se pudieron cargar los ciclos")
        ciclo_sel_id     = None
        ciclo_sel_nombre = "Ciclo actual"

    st.markdown("---")

    # Metas de comision
    st.markdown("**Metas de Comisión**")
    META_MD = st.number_input("Meta Médicos ($)", value=200_000, step=10_000, min_value=0)
    META_PV = st.number_input("Meta PDV ($)",     value=200_000, step=10_000, min_value=0)

    st.markdown("---")

    # Navegacion
    pagina = st.radio(
        "Navegacion",
        ["Resumen Ejecutivo", "Detalle Representante"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Boton actualizar
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(f"<small>Ultima actualizacion:<br>{datetime.now().strftime('%d/%m/%Y %H:%M')}</small>",
                unsafe_allow_html=True)

# ── CARGA DE DATOS ────────────────────────────────────────────────────────────
with st.spinner("Cargando datos desde Intelapp..."):
    try:
        df_base   = cargar_cobertura(ciclo_sel_id)
        df        = agregar_comisiones(df_base, META_MD, META_PV)
        error_api = False
    except Exception as e:
        error_api = True
        error_msg = str(e)

if error_api:
    st.error(f"No se pudo conectar a la API de Intelapp: {error_msg}")
    st.info("Verifica que el token este vigente y que tengas conexion a internet.")
    st.stop()

df_filtrado = df

# ════════════════════════════════════════════════════════════════════════════════
# PAGINA 1 — RESUMEN EJECUTIVO
# ════════════════════════════════════════════════════════════════════════════════
if pagina == "Resumen Ejecutivo":

    # Header
    st.markdown(f"""
    <div class="header-box">
        <div class="header-title">Tablero de Comisiones — MD Magistral</div>
        <div class="header-sub">Resumen ejecutivo del equipo de ventas &nbsp;|&nbsp; {ciclo_sel_nombre}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_com    = df_filtrado["Comision_Total"].sum()
    reps_ganan   = (df_filtrado["Estado"] != "NO GANA").sum()
    total_reps   = len(df_filtrado)
    avg_cumpl    = df_filtrado["Pct_Cumplimiento"].mean()
    avg_cob_med  = df_filtrado["Cob_Med"].mean()
    avg_cob_pdv  = df_filtrado["Cob_PDV"].mean()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Comisiones</div>
            <div class="kpi-value">${total_com:,.0f}</div>
            <div class="kpi-sub">Meta maxima: ${total_reps * (META_MD+META_PV):,.0f}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#375623;">
            <div class="kpi-label">Reps que Comisionan</div>
            <div class="kpi-value" style="color:#375623;">{reps_ganan} / {total_reps}</div>
            <div class="kpi-sub">{reps_ganan/total_reps*100:.0f}% del equipo supera el 80%</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        color_cumpl = "#375623" if avg_cumpl >= 0.80 else ("#7D6608" if avg_cumpl >= 0.60 else "#9C0006")
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:{color_cumpl};">
            <div class="kpi-label">Avg Cumplimiento</div>
            <div class="kpi-value" style="color:{color_cumpl};">{avg_cumpl*100:.1f}%</div>
            <div class="kpi-sub">Meta: 80%</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#2E75B6;">
            <div class="kpi-label">Cob. Medicos / PDV</div>
            <div class="kpi-value" style="color:#2E75B6;">{avg_cob_med*100:.1f}% / {avg_cob_pdv*100:.1f}%</div>
            <div class="kpi-sub">Promedio del equipo</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Grafico de barras ─────────────────────────────────────────────────────
    col_graf, col_dist = st.columns([3, 2])

    with col_graf:
        st.markdown("#### Comision por Representante")
        df_graf = df_filtrado.sort_values("Comision_Total", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_graf["Representante"],
            x=df_graf["Comision_Med"],
            name="Comision Medicos",
            orientation="h",
            marker_color="#2E75B6",
            text=df_graf["Comision_Med"].apply(lambda x: f"${x:,.0f}" if x > 0 else ""),
            textposition="inside",
            textfont=dict(color="white", size=12, family="Arial Black"),
            hovertemplate="<b>%{y}</b><br>Comision Medicos: <b>$%{x:,.0f}</b><extra></extra>",
        ))
        fig.add_trace(go.Bar(
            y=df_graf["Representante"],
            x=df_graf["Comision_PDV"],
            name="Comision PDV",
            orientation="h",
            marker_color="#1F4E79",
            text=df_graf["Comision_PDV"].apply(lambda x: f"${x:,.0f}" if x > 0 else ""),
            textposition="inside",
            textfont=dict(color="white", size=12, family="Arial Black"),
            hovertemplate="<b>%{y}</b><br>Comision PDV: <b>$%{x:,.0f}</b><extra></extra>",
        ))
        fig.update_layout(
            barmode="stack",
            height=max(300, len(df_graf) * 52),
            margin=dict(l=180, r=30, t=10, b=40),
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(orientation="h", y=-0.08, font=dict(size=12)),
            xaxis=dict(tickformat="$,.0f", gridcolor="#EEE", tickfont=dict(size=11, color="#222")),
            yaxis=dict(
                gridcolor="#EEE",
                tickfont=dict(size=13, color="#222"),
                automargin=True,
            ),
            hoverlabel=dict(
                bgcolor="white",
                font_size=13,
                font_color="#1F4E79",
                bordercolor="#2E75B6",
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_dist:
        st.markdown("#### Distribucion por Estado")
        conteo = df_filtrado["Estado"].value_counts().reset_index()
        conteo.columns = ["Estado", "Cantidad"]

        # Orden fijo y colores harmonizados con la tabla
        orden   = ["COMPLETA", "PARCIAL", "NO GANA"]
        colores = {"COMPLETA": "#2E75B6", "PARCIAL": "#5BA3D9", "NO GANA": "#BDD7EE"}
        conteo["orden"] = conteo["Estado"].map({e: i for i, e in enumerate(orden)})
        conteo = conteo.sort_values("orden")

        fig2 = go.Figure()
        for _, fila in conteo.iterrows():
            fig2.add_trace(go.Bar(
                x=[fila["Cantidad"]],
                y=[fila["Estado"]],
                orientation="h",
                name=fila["Estado"],
                marker_color=colores.get(fila["Estado"], "#2E75B6"),
                text=f'{fila["Cantidad"]} rep{"s" if fila["Cantidad"] != 1 else ""}  ({fila["Cantidad"]/total_reps*100:.0f}%)',
                textposition="outside",
                textfont=dict(size=13, color="#1F4E79"),
            ))

        fig2.update_layout(
            showlegend=False,
            height=max(300, len(df_graf) * 52),
            margin=dict(l=20, r=60, t=10, b=40),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis=dict(
                showgrid=False,
                showticklabels=False,
                range=[0, total_reps * 1.35],
            ),
            yaxis=dict(
                tickfont=dict(size=13, color="#1F4E79"),
                automargin=True,
            ),
            bargap=0.35,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Tabla de detalle ──────────────────────────────────────────────────────
    st.markdown("#### Detalle por Representante")

    def color_estado(val):
        colores = {
            "COMPLETA": "background-color:#C6EFCE; color:#375623; font-weight:bold",
            "PARCIAL":  "background-color:#FFEB9C; color:#7D6608; font-weight:bold",
            "NO GANA":  "background-color:#FFC7CE; color:#9C0006; font-weight:bold",
        }
        return colores.get(val, "")

    df_tabla = df_filtrado[[
        "Representante", "Region",
        "Cob_Med", "Cob_PDV", "Pct_Cumplimiento",
        "Comision_Med", "Comision_PDV", "Comision_Total",
        "Estado"
    ]].copy()

    df_tabla.columns = [
        "Representante", "Region",
        "Cob. Medicos", "Cob. PDV", "% Cumplimiento",
        "Com. Medicos", "Com. PDV", "Com. Total",
        "Estado"
    ]

    styled = (
        df_tabla.style
        .format({
            "Cob. Medicos":   "{:.1%}",
            "Cob. PDV":       "{:.1%}",
            "% Cumplimiento": "{:.1%}",
            "Com. Medicos":   "${:,.0f}",
            "Com. PDV":       "${:,.0f}",
            "Com. Total":     "${:,.0f}",
        })
        .map(color_estado, subset=["Estado"])
        .set_properties(**{"text-align": "center"})
        .set_table_styles([
            {"selector": "th", "props": [
                ("background-color", "#1F4E79"),
                ("color", "white"),
                ("font-weight", "bold"),
                ("text-align", "center"),
                ("padding", "8px"),
            ]},
            {"selector": "td", "props": [("padding", "6px 10px")]},
            {"selector": "tr:nth-child(even)", "props": [("background-color", "#F0F5FB")]},
        ])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Fila de totales
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Total Com. Medicos",  f"${df_filtrado['Comision_Med'].sum():,.0f}")
    t2.metric("Total Com. PDV",      f"${df_filtrado['Comision_PDV'].sum():,.0f}")
    t3.metric("Total Comisiones",    f"${df_filtrado['Comision_Total'].sum():,.0f}")
    t4.metric("Meta Maxima Equipo",  f"${total_reps*(META_MD+META_PV):,.0f}")


# ════════════════════════════════════════════════════════════════════════════════
# PAGINA 2 — DETALLE POR REPRESENTANTE
# ════════════════════════════════════════════════════════════════════════════════
elif pagina == "Detalle Representante":

    st.markdown(f"""
    <div class="header-box">
        <div class="header-title">Detalle por Representante</div>
        <div class="header-sub">Selecciona un representante para ver sus indicadores &nbsp;|&nbsp; {ciclo_sel_nombre}</div>
    </div>
    """, unsafe_allow_html=True)

    # Selector de representante
    reps = df_filtrado["Representante"].tolist()
    rep_sel = st.selectbox("Selecciona un representante", reps)

    row = df_filtrado[df_filtrado["Representante"] == rep_sel].iloc[0]

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Fila superior: barra de progreso + estado + comision ──────────────────
    pct = row["Pct_Cumplimiento"]

    # Colores segun estado
    if pct >= 0.99:
        color_barra = "#2E75B6"
        color_bg    = "#D6E4F0"
        estado_color = "#1F4E79"
        estado_bg    = "#D6E4F0"
    elif pct >= 0.80:
        color_barra = "#F4C430"
        color_bg    = "#FFF9E6"
        estado_color = "#7D6608"
        estado_bg    = "#FFEB9C"
    else:
        color_barra = "#C00000"
        color_bg    = "#FFF0F0"
        estado_color = "#9C0006"
        estado_bg    = "#FFC7CE"

    diff_pct = (pct - 0.80) * 100
    diff_txt = f"+{diff_pct:.1f}%" if diff_pct >= 0 else f"{diff_pct:.1f}%"
    diff_color = "#2E75B6" if diff_pct >= 0 else "#C00000"

    col_prog, col_com_total = st.columns([3, 1])

    with col_prog:
        st.markdown(f"""
        <div style="background:white; border-radius:12px; padding:30px 32px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <span style="font-size:14px; color:#666; font-weight:600; text-transform:uppercase;">
                    % Cumplimiento Combinado
                </span>
                <span style="background:{estado_bg}; color:{estado_color};
                             padding:5px 16px; border-radius:20px; font-weight:700; font-size:14px;">
                    {row['Estado']}
                </span>
            </div>
            <div style="font-size:52px; font-weight:800; color:{color_barra}; line-height:1; margin-bottom:16px;">
                {pct*100:.1f}%
                <span style="font-size:17px; color:{diff_color}; font-weight:600; margin-left:10px;">
                    {diff_txt} vs meta 80%
                </span>
            </div>
            <div style="background:#EEE; border-radius:8px; height:14px; overflow:hidden;">
                <div style="background:{color_barra}; width:{min(pct*100, 100):.1f}%;
                            height:14px; border-radius:8px;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:6px;">
                <span style="font-size:12px; color:#AAA;">0%</span>
                <span style="font-size:12px; color:#1F4E79; font-weight:600;">Meta: 80%</span>
                <span style="font-size:12px; color:#AAA;">100%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_com_total:
        st.markdown(f"""
        <div style="background:{color_bg}; border-radius:12px; padding:30px 24px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08); text-align:center;">
            <div style="font-size:13px; color:#666; font-weight:600;
                        text-transform:uppercase; margin-bottom:10px;">Comision Total</div>
            <div style="font-size:32px; font-weight:800; color:{estado_color}; line-height:1.2;">
                ${row['Comision_Total']:,.0f}
            </div>
            <div style="font-size:12px; color:#999; margin-top:8px;">
                de ${row['Meta_Total']:,.0f} posibles
            </div>
            <div style="font-size:14px; color:{diff_color}; font-weight:700; margin-top:10px;">
                {row['Comision_Total']/row['Meta_Total']*100:.0f}% de la meta
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Bloque Medicos ────────────────────────────────────────────────────────
    st.markdown("#### 🩺 Medicos")
    cob_med_delta = (row['Cob_Med'] - 0.80) * 100
    m1, m2, m3, m4 = st.columns(4)
    for col, label, valor, sub in [
        (m1, "Panel Asignado",   str(row['Panel_Med']),              f"medicos en panel"),
        (m2, "Visitados",        str(row['Visit_Med']),              f"de {row['Panel_Med']} en panel"),
        (m3, "Cobertura",        f"{row['Cob_Med']*100:.1f}%",      f"{cob_med_delta:+.1f}% vs meta 80%"),
        (m4, "Comision Medicos", f"${row['Comision_Med']:,.0f}",    f"meta: ${META_MD:,.0f}"),
    ]:
        sub_color = "#2E75B6" if "+" in sub or "meta" in sub.lower() else "#C00000"
        col.markdown(f"""
        <div class="kpi-card" style="border-left-color:#2E75B6; min-height:100px;">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="font-size:22px;">{valor}</div>
            <div class="kpi-sub" style="color:{sub_color};">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Bloque PDV ────────────────────────────────────────────────────────────
    st.markdown("#### 🏪 PDV / Farmacias")
    cob_pdv_delta = (row['Cob_PDV'] - 0.80) * 100
    p1, p2, p3, p4 = st.columns(4)
    for col, label, valor, sub in [
        (p1, "Panel Asignado", str(row['Panel_PDV']),           f"PDV en panel"),
        (p2, "Visitados",      str(row['Visit_PDV']),           f"de {row['Panel_PDV']} en panel"),
        (p3, "Cobertura",      f"{row['Cob_PDV']*100:.1f}%",   f"{cob_pdv_delta:+.1f}% vs meta 80%"),
        (p4, "Comision PDV",   f"${row['Comision_PDV']:,.0f}", f"meta: ${META_PV:,.0f}"),
    ]:
        sub_color = "#2E75B6" if "+" in sub or "meta" in sub.lower() else "#C00000"
        col.markdown(f"""
        <div class="kpi-card" style="border-left-color:#1F4E79; min-height:100px;">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="font-size:22px;">{valor}</div>
            <div class="kpi-sub" style="color:{sub_color};">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Mini grafico de comparacion ───────────────────────────────────────────
    st.markdown("#### Comparacion vs Equipo")
    avg_med = df["Cob_Med"].mean()
    avg_pdv = df["Cob_PDV"].mean()

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        x=["Cobertura Medicos", "Cobertura PDV"],
        y=[avg_med * 100, avg_pdv * 100],
        name="Promedio Equipo",
        marker_color="#BDD7EE",
    ))
    fig_comp.add_trace(go.Bar(
        x=["Cobertura Medicos", "Cobertura PDV"],
        y=[row["Cob_Med"] * 100, row["Cob_PDV"] * 100],
        name=rep_sel.split()[0],
        marker_color="#1F4E79",
    ))
    fig_comp.add_hline(y=80, line_dash="dash", line_color="#C00000",
                       annotation_text="Meta 80%", annotation_position="top right")
    fig_comp.update_layout(
        barmode="group",
        height=280,
        yaxis=dict(
            range=[0, 110],
            ticksuffix="%",
            gridcolor="#EEE",
            tickfont=dict(color="#222", size=12),
            title_font=dict(color="#222"),
        ),
        xaxis=dict(
            tickfont=dict(color="#222", size=13),
            title_font=dict(color="#222"),
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", y=-0.15, font=dict(color="#222", size=12)),
    )
    st.plotly_chart(fig_comp, use_container_width=True)
