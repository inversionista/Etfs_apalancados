
import time
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# --- ensure repo root in sys.path ---
import os, sys
APP_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(APP_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# ------------------------------------

from core.pairs import PAIRS
from core.metrics import summarize_pair
from core.hedge import hedge_shares
from core.hedge_adv import (
    returns, rolling_beta, beta_ols, beta_robust_theilsen, beta_wls,
    hedge_ratio_cointegration, simulate_hedge_pnl, hedge_effectiveness
)

st.set_page_config(page_title="Pairs Lab — v6 (Spread)", page_icon="🌙", layout="wide")
st.title("Leveraged Pairs Lab — v6")

with st.sidebar:
    st.header("⚙️ Parámetros")
    lookback = st.selectbox("Ventana", ["1M","3M","6M","YTD","1Y","3Y","MAX"], index=3)
    start_date = st.date_input("Inicio (override)", value=None)
    end_date = st.date_input("Fin (override)", value=None)
    emisores = sorted({p["emisor"] for p in PAIRS})
    emisores_sel = st.multiselect("Filtrar por emisor", emisores, default=emisores)
    base_unique = sorted({p["base"] for p in PAIRS})
    bases_sel = st.multiselect("Bases", base_unique, default=base_unique)
    dark = st.toggle("Tema oscuro", value=True)
    run_btn = st.button("🔄 Actualizar datos")

template = "plotly_dark" if dark else "plotly"

def get_default_start(lookback: str) -> pd.Timestamp:
    today = pd.Timestamp.today().normalize()
    if lookback == "1M": return today - pd.DateOffset(months=1)
    if lookback == "3M": return today - pd.DateOffset(months=3)
    if lookback == "6M": return today - pd.DateOffset(months=6)
    if lookback == "YTD": return pd.Timestamp(f"{today.year}-01-01")
    if lookback == "1Y": return today - pd.DateOffset(years=1)
    if lookback == "3Y": return today - pd.DateOffset(years=3)
    return pd.Timestamp("2005-01-01")

def resolve_window():
    s = pd.to_datetime(start_date) if start_date else get_default_start(lookback)
    e = pd.to_datetime(end_date) if end_date else pd.Timestamp.today().normalize()
    return s, e

def download_data(tickers, start, end):
    data = yf.download(
        tickers=tickers, start=start, end=end + pd.Timedelta(days=1),
        auto_adjust=True, progress=False, group_by="ticker", threads=True, interval="1d"
    )
    return data

def extract_series(data, ticker, field):
    try:
        if isinstance(data.columns, pd.MultiIndex):
            return data[ticker][field].rename(ticker)
        else:
            return data[field].rename(ticker)
    except Exception:
        return pd.Series(dtype=float, name=ticker)

pairs = [p for p in PAIRS if p["emisor"] in emisores_sel and p["base"] in bases_sel]

if run_btn or "last_run" not in st.session_state:
    st.session_state["last_run"] = time.time()
    start, end = resolve_window()
    st.info(f"Descargando datos {start.date()} → {end.date()}...")
    tickers = sorted({x for p in pairs for x in (p["base"], p["alt"])})
    data = download_data(tickers, start, end)

    close = {}; vol = {}
    for t in tickers:
        close[t] = extract_series(data, t, "Close")
        vol[t]   = extract_series(data, t, "Volume")

    rows = []
    for p in pairs:
        m = summarize_pair(close[p["base"]], close[p["alt"]], vol[p["base"]], vol[p["alt"]],
                           target_ratio=p.get("target_ratio"), start=str(start.date()), end=str(end.date()))
        rows.append(m.__dict__)
    df = pd.DataFrame(rows)

    st.session_state["metrics_df"] = df
    st.session_state["close_dict"] = close
    st.session_state["start_end"] = (start, end)

df = st.session_state.get("metrics_df")
close_dict = st.session_state.get("close_dict")
start, end = st.session_state.get("start_end", resolve_window())

if df is None or df.empty:
    st.warning("No hay resultados. Ajusta filtros y pulsa **Actualizar datos**.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumen","📈 Gráficos","🛡️ Cobertura","🧠 Avanzado", "ℹ️ Acerca de / Autor"])

with tab1:
    st.subheader("Tabla de métricas")
    st.dataframe(df, use_container_width=True, height=450)

    d = df.copy(); d["pair"] = d["base"] + "→" + d["alt"]
    d["deviation"] = d["beta_alt_on_base"] - d["target_ratio"]
    d = d.sort_values(by="deviation", key=lambda s: s.abs(), ascending=False)
    fig_dev = px.bar(d, x="pair", y="deviation", color="deviation", color_continuous_scale="Turbo",
                     hover_data={"beta_alt_on_base":":.2f","target_ratio":":.2f","corr":":.2f","r2":":.2f"},
                     template=template, title="Desviación (β efectivo - target)")
    fig_dev.update_layout(xaxis_tickangle=-45, yaxis_title="Desviación")
    st.plotly_chart(fig_dev, use_container_width=True, key="deviation_chart")

with tab2:
    st.subheader("Lollipop β vs Target")
    l = df.copy(); l["pair"] = l["base"] + "→" + l["alt"]
    fig_l = go.Figure()
    fig_l.add_trace(go.Scatter(x=l["pair"], y=l["beta_alt_on_base"], mode="markers", name="β efectivo", marker=dict(size=10)))
    fig_l.add_trace(go.Scatter(x=l["pair"], y=l["target_ratio"], mode="markers", name="Target", marker=dict(symbol="diamond", size=10)))
    for i, row in l.iterrows():
        fig_l.add_shape(type="line", x0=i, x1=i, y0=row["target_ratio"], y1=row["beta_alt_on_base"], line=dict(width=2))
    fig_l.update_layout(template=template, xaxis_tickangle=-45, yaxis_title="Ratio")
    st.plotly_chart(fig_l, use_container_width=True, key="lollipop_chart")

    st.subheader("Riesgo–Retorno (ALT, burbujas ~ vol. 30d)")
    bub = df.copy(); bub["pair"] = bub["base"] + "→" + bub["alt"]
    bub = bub[["pair","ret_alt","vol_alt","avg_vol_alt"]].rename(columns={"ret_alt":"ret","vol_alt":"vol","avg_vol_alt":"volume"})
    fig_bub = px.scatter(bub, x="vol", y="ret", size="volume", hover_name="pair", size_max=40, template=template,
                         labels={"vol":"Vol anualizada","ret":"Retorno período"})
    st.plotly_chart(fig_bub, use_container_width=True, key="bubble_chart")

    st.subheader("β rodante")
    pair_labels = [f'{p["base"]}→{p["alt"]}' for p in pairs]
    if pair_labels:
        choice = st.selectbox("Par", pair_labels, index=0, key="rb_choice")
        sel = pairs[pair_labels.index(choice)]
        base, alt = sel["base"], sel["alt"]
        b_close = close_dict[base].loc[str(start.date()):str(end.date())].dropna()
        a_close = close_dict[alt].loc[str(start.date()):str(end.date())].dropna()
        x_ret = returns(b_close); y_ret = returns(a_close)
        window = st.slider("Ventana (días)", 20, 200, 60, step=5, key="rb_win")
        rb = rolling_beta(x_ret, y_ret, window)
        if rb is not None and not rb.empty:
            fig_rb = px.line(x=rb.index, y=rb.values, template=template, labels={"x":"Fecha","y":"β"})
            fig_rb.update_layout(title=f"β rodante {base}→{alt}")
            st.plotly_chart(fig_rb, use_container_width=True, key="rb_chart_tab2")
        else:
            st.info("No hay suficientes datos para β rodante.")

    st.subheader("Retornos acumulados (ALT normalizado)")
    loaded_pairs = [f'{p["base"]}→{p["alt"]}' for p in pairs if p["base"] in close_dict and p["alt"] in close_dict]
    sel_pairs = st.multiselect("Pares (ALT)", loaded_pairs, default=loaded_pairs[:4], key="cr_alt_sel")
    if sel_pairs:
        fig_cr = go.Figure()
        for label in sel_pairs:
            base, alt = label.split("→")
            s = close_dict[alt].loc[str(start.date()):str(end.date())].dropna()
            if s.empty: continue
            cum = (s / s.iloc[0]) * 100.0
            fig_cr.add_trace(go.Scatter(x=cum.index, y=cum.values, mode="lines", name=f"{label} ALT"))
        fig_cr.update_layout(template=template, yaxis_title="Índice 100 = inicio", title="Retornos acumulados — ALT")
        st.plotly_chart(fig_cr, use_container_width=True, key="cum_alt_chart")

    st.subheader("Retornos acumulados **BASE vs ALT** (multi-par)")
    sel_pairs_dual = st.multiselect("Pares (BASE y ALT)", loaded_pairs, default=loaded_pairs[:3], key="cr_dual_sel")
    if sel_pairs_dual:
        fig_dual = go.Figure()
        for label in sel_pairs_dual:
            base, alt = label.split("→")
            sb = close_dict[base].loc[str(start.date()):str(end.date())].dropna()
            sa = close_dict[alt].loc[str(start.date()):str(end.date())].dropna()
            if sb.empty or sa.empty: continue
            cb = (sb / sb.iloc[0]) * 100.0
            ca = (sa / sa.iloc[0]) * 100.0
            fig_dual.add_trace(go.Scatter(x=cb.index, y=cb.values, mode="lines", name=f"{base} (BASE) — {label}", line=dict(dash="dash")))
            fig_dual.add_trace(go.Scatter(x=ca.index, y=ca.values, mode="lines", name=f"{alt} (ALT) — {label}", line=dict(dash="solid")))
        fig_dual.update_layout(template=template, yaxis_title="Índice 100 = inicio", title="Retornos acumulados — BASE vs ALT")
        st.plotly_chart(fig_dual, use_container_width=True, key="cum_dual_chart")

with tab3:
    st.subheader("Calculadora de cobertura (beta & precios spot)")
    pair_labels = [f'{p["base"]}→{p["alt"]}' for p in pairs]
    if pair_labels:
        pair_choice_cov = st.selectbox("Par (BASE→ALT)", pair_labels, index=0, key="cov_choice")
        sel_cov = pairs[pair_labels.index(pair_choice_cov)]
        qty_alt = st.number_input("Cantidad ALT a cubrir", min_value=1.0, value=1000.0, step=100.0, key="cov_qty")
        df_row = df[(df['base']==sel_cov['base']) & (df['alt']==sel_cov['alt'])]
        if df_row.empty or pd.isna(df_row['beta_alt_on_base'].iloc[0]):
            st.warning("No hay beta disponible para este par/ventana.")
        else:
            beta_val = float(df_row['beta_alt_on_base'].iloc[0])
            b_last = yf.Ticker(sel_cov['base']).history(period="5d")['Close'].dropna().iloc[-1]
            a_last = yf.Ticker(sel_cov['alt']).history(period="5d")['Close'].dropna().iloc[-1]
            res = hedge_shares(qty_alt=float(qty_alt), price_alt=float(a_last), price_base=float(b_last), beta_alt_on_base=beta_val)
            c1,c2,c3 = st.columns(3)
            with c1:
                st.metric("Precio ALT", f"${a_last:,.2f}")
                st.metric("Precio BASE", f"${b_last:,.2f}")
            with c2:
                st.metric("β (ALT/BASE)", f"{beta_val:.4f}")
                st.metric("Factor (BASE/1 ALT)", f"{res['factor_shares_per_alt']:.4f}")
            with c3:
                st.metric(f"Acciones BASE para {int(qty_alt):,} ALT", f"{res['shares_base_for_qty_alt']:,.0f}")
                st.caption("Signo sugerido: BASE corta si ALT es largo (β>0).")
            st.info("Fórmula: acciones_BASE ≈ β × (Precio_ALT / Precio_BASE) × cantidad_ALT")

with tab4:
    st.subheader("Cobertura avanzada")
    pair_labels = [f'{p["base"]}→{p["alt"]}' for p in pairs]
    if pair_labels:
        choice = st.selectbox("Par (BASE→ALT)", pair_labels, index=0, key="adv_choice")
        sel = pairs[pair_labels.index(choice)]
        base, alt = sel["base"], sel["alt"]
        b_close = close_dict[base].loc[str(start.date()):str(end.date())].dropna()
        a_close = close_dict[alt].loc[str(start.date()):str(end.date())].dropna()
        x_ret = returns(b_close); y_ret = returns(a_close)

        method = st.selectbox("Método", ["OLS","ROBUST","WLS","COINT"], index=0, key="adv_method")
        roll_win = st.slider("Ventana β rodante", 20, 200, 60, step=5, key="adv_roll")
        qty_alt_adv = st.number_input("Cantidad ALT (simulación)", min_value=1.0, value=1000.0, step=100.0, key="adv_qty")

        # Hedge ratio
        hr = None; coint_info = None
        if method=="OLS":
            hr = beta_ols(x_ret, y_ret)
        elif method=="ROBUST":
            hr = beta_robust_theilsen(x_ret, y_ret)
        elif method=="WLS":
            hr = beta_wls(x_ret, y_ret)
        else:
            coint_info = hedge_ratio_cointegration(b_close, a_close)
            hr = coint_info["beta"]

        st.write(f"**Hedge ratio (β)**: {hr:.4f}" if hr is not None else "β no disponible.")
        if coint_info:
            st.caption(f"ADF={coint_info['adf_stat']:.3f}, p={coint_info['pvalue']:.3f} (p<0.05 sugiere cointegración).")

        # Rolling beta
        rb = None
        try:
            rb = rolling_beta(x_ret, y_ret, window=int(roll_win))
        except Exception:
            rb = None
        if rb is not None and not rb.empty:
            fig_rb = px.line(x=rb.index, y=rb.values, template=template, labels={"x":"Fecha","y":"β"})
            fig_rb.update_layout(title=f"β rodante {base}→{alt}")
            st.plotly_chart(fig_rb, use_container_width=True, key="rb_chart_adv")

        # --- Spread (ALT − β·BASE), ambos normalizados a 100 ---
        if hr is not None and not np.isnan(hr):
            cb = (b_close / b_close.iloc[0]) * 100.0
            ca = (a_close / a_close.iloc[0]) * 100.0
            spread = ca - hr * cb
            win = int(max(20, min(60, len(spread)//6)))  # 20–60 según tamaño
            ma = spread.rolling(win).mean()
            sd = spread.rolling(win).std()
            upper = ma + 2*sd
            lower = ma - 2*sd

            fig_spread = go.Figure()
            fig_spread.add_trace(go.Scatter(x=spread.index, y=spread.values, mode="lines", name="Spread (ALT − β·BASE)"))
            fig_spread.add_trace(go.Scatter(x=ma.index, y=ma.values, mode="lines", name=f"Media {win}", line=dict(dash="dash")))
            fig_spread.add_trace(go.Scatter(x=upper.index, y=upper.values, mode="lines", name="+2σ", line=dict(dash="dot")))
            fig_spread.add_trace(go.Scatter(x=lower.index, y=lower.values, mode="lines", name="-2σ", line=dict(dash="dot")))
            fig_spread.update_layout(template=template, title="Spread con bandas de Bollinger", yaxis_title="Índice (normalizado)")
            st.plotly_chart(fig_spread, use_container_width=True, key="spread_chart_adv")
            st.caption("Si el spread es estacionario, tiende a oscilar alrededor de la media. Excursiones > ±2σ suelen revertir (no garantizado).")

        # PnL simulado
        if hr is not None and not np.isnan(hr) and len(b_close)>1 and len(a_close)>1:
            factor_last = float((hr * (a_close / b_close)).dropna().iloc[-1])
            qty_base_adv = - factor_last * qty_alt_adv
            pnl_df = simulate_hedge_pnl(qty_alt=qty_alt_adv, qty_base=qty_base_adv, alt_price=a_close, base_price=b_close)
            unhedged_ret = a_close.pct_change().dropna()
            hedged_val = (qty_alt_adv * a_close) + (qty_base_adv * b_close)
            hedged_ret = hedged_val.pct_change().dropna()
            heff = hedge_effectiveness(unhedged_ret, hedged_ret)

            c1,c2 = st.columns(2)
            with c1:
                fig_pnl = px.line(x=pnl_df.index, y=pnl_df["cum_pnl"], template=template, labels={"x":"Fecha","y":"PnL acumulado"})
                st.plotly_chart(fig_pnl, use_container_width=True, key="pnl_chart_adv")
            with c2:
                vols = pd.Series({"ALT solo": np.sqrt(252)*unhedged_ret.std(), "Cubierta": np.sqrt(252)*hedged_ret.std()})
                fig_vol = px.bar(x=vols.index, y=vols.values, template=template, labels={"x":"","y":"Vol anualizada"})
                st.plotly_chart(fig_vol, use_container_width=True, key="vol_chart_adv")

            st.metric("Hedge Effectiveness", f"{heff*100:.2f}%")
        else:
            st.info("No se pudo simular PnL de cobertura (faltan datos o β).")

with tab5:
    st.subheader("ℹ️ Acerca de — Edwin Londoño - Trading Room en Vivo")
    st.markdown("""
    **Autor:** Edwin Londoño  
    Co-Fundador y anfitrión de *Trading Room en Vivo* — comunidad hispana dedicada al
    trading cuantitativo, educativo y profesional.

    **Propósito del proyecto:**  
    Demostrar el análisis empírico de ETFs apalancados y su relación beta con los subyacentes,
    integrando conceptos de riesgo, correlación y cobertura dinámica.

    **Contacto:**  
    - 📧 [contacto@tradingroomenvivo.com](mailto:contacto@tradingroomenvivo.com)  
    - 📺 [YouTube: Trading Room en Vivo](https://www.youtube.com/@tradingRoomenVivo)  
    - 🌐 [www.tradingroomenvivo.com](http://www.tradingroomenvivo.com)
    """)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Descargar métricas (CSV)", data=csv, file_name="leveraged_pairs_metrics.csv", mime="text/csv")
