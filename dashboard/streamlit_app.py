"""
Performance vs. Beta — Streamlit Dashboard
===========================================
Run:  streamlit run dashboard/streamlit_app.py

Type any US ticker, hit Enter or click Load.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data import (load_data, get_company_name, INDEX_MAP,
                  normalize_ticker, search_ticker, YFINANCE_SUFFIX_INDEX_MAP)

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Perf vs Beta",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    -webkit-font-smoothing: antialiased;
  }
  .stApp { background: #f1f5f9 !important; overflow: hidden !important; height: 100vh !important; }
  .main, [data-testid="stAppViewContainer"] { overflow: hidden !important; }

  /* ── Kill Streamlit chrome ── */
  header[data-testid="stHeader"],
  footer,
  #MainMenu,
  .stDeployButton,
  [data-testid="stToolbar"],
  [data-testid="stStatusWidget"],
  [data-testid="stBottomBlockContainer"] { display: none !important; }

  /* ── Strip default padding ── */
  .block-container { padding-top: 0 !important; padding-bottom: 0.5rem !important;
                     padding-left: 0 !important; padding-right: 0 !important;
                     max-width: 100% !important; }

  /* ── Dark navy header ── */
  .dash-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    border-bottom: 1px solid rgba(59,130,246,0.2);
    padding: 14px 24px;
    display: flex; align-items: center; gap: 10px;
  }
  .dash-header h1 {
    background: linear-gradient(135deg, #ffffff 0%, #93c5fd 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.02em;
  }
  .dash-header .badge {
    background: rgba(59,130,246,0.2); color: #93c5fd;
    font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 20px;
    letter-spacing: 0.06em; text-transform: uppercase; border: 1px solid rgba(59,130,246,0.3);
  }

  /* ── Widget labels ── */
  [data-testid="stWidgetLabel"] p {
    color: #475569 !important; font-size: 11px !important;
    font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.07em !important;
  }

  /* ── Text input ── */
  [data-testid="stTextInput"] input {
    border-radius: 6px !important; border: 1px solid #e2e8f0 !important;
    font-size: 14px !important; font-weight: 500 !important;
    color: #0f172a !important; background: #ffffff !important;
  }
  [data-testid="stTextInput"] input:focus {
    border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
  }

  /* ── Selectbox ── */
  [data-testid="stSelectbox"] > div > div {
    border-radius: 6px !important; border-color: #e2e8f0 !important;
    background: #ffffff !important; color: #0f172a !important;
  }

  /* ── Primary button ── */
  button[kind="primary"] {
    background: #3b82f6 !important; color: white !important;
    border: none !important; border-radius: 6px !important;
    font-weight: 600 !important; font-size: 14px !important;
    box-shadow: 0 1px 3px rgba(59,130,246,0.3) !important; transition: all 0.15s !important;
  }
  button[kind="primary"]:hover {
    background: #2563eb !important; box-shadow: 0 4px 8px rgba(37,99,235,0.35) !important;
  }

  /* ── Metric cards — all equal height, no delta ── */
  div[data-testid="stMetric"],
  [data-testid="metric-container"] {
    background: #ffffff !important; border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important; padding: 14px 18px !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important;
    min-height: 78px !important;
    display: flex !important; flex-direction: column !important; justify-content: center !important;
  }
  div[data-testid="stMetric"]:hover,
  [data-testid="metric-container"]:hover {
    box-shadow: 0 4px 8px rgba(15,23,42,0.08) !important;
  }
  [data-testid="stMetricValue"] > div {
    color: #0f172a !important; font-size: 20px !important;
    font-weight: 700 !important; letter-spacing: -0.02em !important;
  }
  [data-testid="stMetricLabel"] {
    color: #64748b !important; font-size: 10px !important;
    font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.07em !important;
  }
  [data-testid="stMetricDelta"] { display: none !important; }

  /* ── Company name ── */
  .company-name { font-size: 16px; font-weight: 700; color: #0f172a;
                  margin: 0 0 2px 0; letter-spacing: -0.02em; line-height: 1.3; }
  .ticker-sub   { font-size: 11px; color: #94a3b8; font-weight: 400; margin: 0; }

  /* ── Divider ── */
  hr { border-color: #e2e8f0 !important; margin: 10px 0 !important; }

  /* ── Plotly chart cards ── */
  [data-testid="stPlotlyChart"] > div {
    background: #ffffff !important; border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important; overflow: hidden !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important; transition: box-shadow 0.2s ease !important;
  }
  [data-testid="stPlotlyChart"] > div:hover {
    box-shadow: 0 4px 8px rgba(15,23,42,0.08) !important;
  }

  /* ── Kill vertical gap between charts in each column ── */
  [data-testid="column"] [data-testid="stVerticalBlock"] { gap: 6px !important; }

  /* ── Column alignment ── */
  div[data-testid="stHorizontalBlock"] { align-items: flex-end !important; }

  /* ── Responsive: stack on narrow screens ── */
  @media (max-width: 900px) {
    [data-testid="column"] { width: 100% !important; flex: none !important; }
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
  <h1>📈 Performance vs. Beta</h1>
  <span class="badge">Live</span>
</div>
""", unsafe_allow_html=True)

# ── Search helper (cached 5 min) ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def _search(q: str):
    return search_ticker(q)

# ── Session state ─────────────────────────────────────────────────────────────
if "index_sel" not in st.session_state:
    st.session_state.index_sel = "SPX"
if "last_exch" not in st.session_state:
    st.session_state.last_exch = None
if "ticker_override" not in st.session_state:
    st.session_state.ticker_override = None
if "last_raw" not in st.session_state:
    st.session_state.last_raw = ""
if "pending_index_sel" not in st.session_state:
    st.session_state.pending_index_sel = None
if "suggested_index" not in st.session_state:
    st.session_state.suggested_index = None

# Apply any pending index switch BEFORE widgets are instantiated
if st.session_state.pending_index_sel is not None:
    st.session_state.index_sel = st.session_state.pending_index_sel
    st.session_state.pending_index_sel = None

# ── Controls ─────────────────────────────────────────────────────────────────
col_tick, col_idx, col_per, col_btn, col_copy, col_spacer = st.columns([2, 1.5, 1.5, 1, 1, 3])
with col_tick:
    raw = st.text_input("Ticker", value="AAPL", label_visibility="visible").upper().strip()

# Clear override when user types a new raw input
if raw != st.session_state.last_raw:
    st.session_state.ticker_override = None
    st.session_state.last_raw = raw

# Determine effective ticker and auto-switch index
if st.session_state.ticker_override:
    ticker    = st.session_state.ticker_override
    exch_code = None
    # Auto-detect index from yfinance suffix (e.g. "006400.KS" → KOSPI)
    if "." in ticker:
        suf = ticker.rsplit(".", 1)[-1]
        if suf in YFINANCE_SUFFIX_INDEX_MAP and suf != st.session_state.last_exch:
            st.session_state.index_sel      = YFINANCE_SUFFIX_INDEX_MAP[suf]
            st.session_state.suggested_index = YFINANCE_SUFFIX_INDEX_MAP[suf]
            st.session_state.last_exch      = suf
else:
    ticker, suggested_idx, exch_code = normalize_ticker(raw)
    if exch_code != st.session_state.last_exch:
        if suggested_idx:
            st.session_state.index_sel       = suggested_idx
            st.session_state.suggested_index = suggested_idx
        elif exch_code is None:
            st.session_state.index_sel       = "SPX"
            st.session_state.suggested_index = None
        st.session_state.last_exch = exch_code

if ticker != raw and raw:
    col_tick.caption(f"→ {ticker}")

def _fmt_idx(k):
    if k == st.session_state.suggested_index:
        return f"{k} (suggested)"
    return k

with col_idx:
    index_key = st.selectbox("vs. Index", list(INDEX_MAP.keys()), key="index_sel",
                              format_func=_fmt_idx)
with col_per:
    period = st.selectbox("Period", ["1y", "2y", "3y", "5y"], index=2)
with col_btn:
    st.button("Load", use_container_width=True, type="primary")
with col_copy:
    st.components.v1.html("""
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,-apple-system,sans-serif;background:transparent}
#btn{width:100%;height:36px;font-size:13px;font-weight:500;color:#0f172a;
     background:#fff;border:1px solid #e2e8f0;border-radius:6px;
     cursor:pointer;transition:all .15s}
#btn:hover{background:#f8fafc;border-color:#3b82f6}
#btn:disabled{opacity:.5;cursor:default}
</style>
<button id="btn" onclick="run()">Copy</button>
<script>
async function run(){
  const btn=document.getElementById('btn');
  btn.disabled=true; btn.textContent='…';
  try{
    const P=window.parent.Plotly;
    const all=[...window.parent.document.querySelectorAll('.js-plotly-plot')];
    if(all.length<4){btn.disabled=false;btn.textContent='Copy';return;}
    const cw=780,ch=445,sc=1.5,pad=8;
    const rw=Math.round(cw*sc),rh=Math.round(ch*sc),rp=Math.round(pad*sc);
    const imgs=await Promise.all(all.slice(0,4).map(d=>P.toImage(d,{format:'png',width:cw,height:ch,scale:sc})));
    const slots=[[imgs[0],rp,rp],[imgs[2],rw+rp*2,rp],[imgs[1],rp,rh+rp*2],[imgs[3],rw+rp*2,rh+rp*2]];
    const cv=document.createElement('canvas');
    cv.width=rw*2+rp*3; cv.height=rh*2+rp*3;
    const ctx=cv.getContext('2d');
    ctx.fillStyle='#f1f5f9'; ctx.fillRect(0,0,cv.width,cv.height);
    for(const[src,x,y]of slots){
      const im=new Image(); im.src=src;
      await new Promise(r=>im.onload=r);
      ctx.drawImage(im,x,y,rw,rh);
    }
    try{
      const blob=await new Promise(r=>cv.toBlob(r,'image/png'));
      await navigator.clipboard.write([new ClipboardItem({'image/png':blob})]);
      btn.textContent='✓';
    }catch(_){
      const a=document.createElement('a'); a.download='charts.png';
      a.href=cv.toDataURL(); a.click(); btn.textContent='✓';
    }
  }catch(e){btn.textContent='!';}
  finally{btn.disabled=false;setTimeout(()=>btn.textContent='Copy',2000);}
}
</script>
""", height=38)

# ── Ticker search suggestions ─────────────────────────────────────────────────
if raw and len(raw) >= 2 and not st.session_state.ticker_override and exch_code is None:
    results  = _search(raw)
    to_show  = [r for r in results if r["symbol"].upper() != raw.upper()][:5]
    if to_show:
        n      = len(to_show)
        s_cols = st.columns([1.7] * n + [max(0.1, 10 - 1.7 * n)])
        for i, r in enumerate(to_show):
            with s_cols[i]:
                label = f"{r['symbol']} — {r['name'][:22]}"
                if st.button(label, key=f"sug_{r['symbol']}", use_container_width=True):
                    suf = r["symbol"].rsplit(".", 1)[-1] if "." in r["symbol"] else None
                    if suf and suf in YFINANCE_SUFFIX_INDEX_MAP:
                        st.session_state.pending_index_sel = YFINANCE_SUFFIX_INDEX_MAP[suf]
                        st.session_state.suggested_index   = YFINANCE_SUFFIX_INDEX_MAP[suf]
                        st.session_state.last_exch         = suf
                    st.session_state.ticker_override = r["symbol"]
                    st.rerun()

st.divider()

# ── Load & render ─────────────────────────────────────────────────────────────
if ticker:
    with st.spinner(f"Fetching {ticker}..."):
        df, error    = load_data(ticker, index_key=index_key, period=period)
        company_name = get_company_name(ticker)

    if error or df.empty:
        st.error(f"Could not load data for **{ticker}**: {error or 'empty response'}")
        st.stop()

    # Trim burn-in rows (12W needs 60 days before first valid value)
    df_plot = df.dropna(subset=["perf_vs_beta_12W", "perf_vs_beta_4W", "perf_vs_beta_2W"]).copy()

    # ── Palette ───────────────────────────────────────────────────────────────
    ACCENT  = "#3b82f6"
    PURPLE  = "#8b5cf6"
    AMBER   = "#f59e0b"
    GREEN   = "#10b981"
    BG      = "#ffffff"
    PAPER   = "#f8fafc"
    GRID    = "#e2e8f0"
    ZERO    = "#cbd5e1"
    TEXT    = "#0f172a"
    SUBTEXT = "#475569"
    MUTED   = "#94a3b8"

    # ── Company name + date range ─────────────────────────────────────────────
    name_display = company_name if company_name != ticker else ticker
    _index_label = (f"{index_key} (suggested)"
                    if index_key == st.session_state.get("suggested_index") else index_key)
    st.markdown(
        f'<p class="company-name">{name_display}</p>'
        f'<p class="ticker-sub">{ticker} &nbsp;·&nbsp; {_index_label} &nbsp;·&nbsp; '
        f'{df_plot["date"].iloc[0].strftime("%m/%d/%y")} – {df_plot["date"].iloc[-1].strftime("%m/%d/%y")}'
        f'</p>',
        unsafe_allow_html=True,
    )

    # ── Metric cards ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    latest = df.iloc[-1]
    m1.metric("Price",            f"${latest.get('stock_price', 0):,.2f}")
    m2.metric("Beta (6M)",        f"{latest.get('beta', 0):.2f}")
    m3.metric("Perf vs Beta 2W",  f"{latest.get('perf_vs_beta_2W', 0)*100:+.1f}%")
    m4.metric("Perf vs Beta 4W",  f"{latest.get('perf_vs_beta_4W', 0)*100:+.1f}%")
    m5.metric("Perf vs Beta 12W", f"{latest.get('perf_vs_beta_12W', 0)*100:+.1f}%")

    # ── X-axis range ──────────────────────────────────────────────────────────
    x_end   = df_plot["date"].iloc[-1]
    x_start = max(
        df_plot["date"].iloc[0],
        x_end - pd.Timedelta(days={"1y": 365, "2y": 730, "3y": 1095, "5y": 1825}[period]),
    )

    # ── Shared axis / layout helpers ──────────────────────────────────────────
    # 1080p viewport (~940px) minus header+controls+divider+company+metrics+gaps ≈ 300px
    # leaves ~640px for two chart rows → 320px each, minus small buffer = 285px
    CHART_H = 285

    _ax = dict(
        gridcolor=GRID, zerolinecolor=GRID, zerolinewidth=1,
        tickfont=dict(color=MUTED, size=9, family="Inter, sans-serif"),
        showgrid=True, linecolor=GRID, linewidth=1, showline=True,
        ticks="outside", tickcolor=GRID, ticklen=3,
    )

    def _base_layout(title):
        return dict(
            title=dict(
                text=title,
                font=dict(size=11, color=SUBTEXT, family="Inter, sans-serif"),
                x=0.5, xanchor="center", y=0.99, yanchor="top",
            ),
            paper_bgcolor=PAPER, plot_bgcolor=BG,
            font=dict(color=TEXT, family="'Inter', 'Segoe UI', Arial, sans-serif"),
            margin=dict(l=10, r=10, t=32, b=6),
            height=CHART_H,
            hovermode="x",
            hoverlabel=dict(bgcolor=BG, bordercolor=GRID,
                            font=dict(color=TEXT, size=11, family="Inter, sans-serif")),
            showlegend=False,
        )

    dates = df_plot["date"]

    # ── Price chart (top-left) ────────────────────────────────────────────────
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=dates, y=df_plot["stock_price"],
        line=dict(color=GREEN, width=1.8),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
        hovertemplate="%{x|%b %d, %Y}<br><b>$%{y:,.2f}</b><extra></extra>",
    ))
    fig_price.update_layout(**_base_layout(f"Price Chart — {name_display}"))
    fig_price.update_xaxes(range=[x_start, x_end], **_ax)
    fig_price.update_yaxes(tickformat="$,.2f", **_ax)

    # ── Perf vs Beta chart builder ────────────────────────────────────────────
    def make_perf_fig(col_name, color, label):
        y = df_plot[col_name]
        c = color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=y.clip(lower=0),
            fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.10)",
            line=dict(width=0), hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=y.clip(upper=0),
            fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
            line=dict(width=0), hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=y,
            line=dict(color=color, width=1.8),
            hovertemplate="%{x|%b %d, %Y}<br><b>%{y:.2%}</b><extra></extra>",
        ))
        fig.add_hline(y=0, line_dash="solid", line_color=ZERO, line_width=1)
        fig.update_layout(**_base_layout(f"Perf vs. Beta — {label}  ({ticker} vs {index_key})"))
        fig.update_xaxes(range=[x_start, x_end], **_ax)
        fig.update_yaxes(tickformat=".1%", **_ax)
        return fig

    fig_12w = make_perf_fig("perf_vs_beta_12W", ACCENT, "12 Week")
    fig_4w  = make_perf_fig("perf_vs_beta_4W",  PURPLE, "4 Week")
    fig_2w  = make_perf_fig("perf_vs_beta_2W",  AMBER,  "2 Week")

    # ── 2×2 grid: TL=Price, TR=12W, BL=4W, BR=2W ─────────────────────────────
    # Single st.columns(2) — both charts per column stack without inter-row gap
    col_left, col_right = st.columns(2, gap="small")

    with col_left:
        st.plotly_chart(fig_price, use_container_width=True)   # top-left
        st.plotly_chart(fig_4w,   use_container_width=True)    # bottom-left

    with col_right:
        st.plotly_chart(fig_12w,  use_container_width=True)    # top-right
        st.plotly_chart(fig_2w,   use_container_width=True)    # bottom-right
