"""
Performance vs. Beta — Streamlit Dashboard
===========================================
Run:  streamlit run dashboard/streamlit_app.py

Changes in this version:
  - Removed "0%" zero-line annotation from perf charts
  - Removed date-range slider (period selectbox now controls window)
  - Added "Custom" period option with from/to date pickers
  - Info (ℹ) tooltip above each chart explains the methodology
  - Pre-caches S&P 500 / S&P 1000 / QQQ + all indices; daily 4:15 PM refresh
  - Data source note at bottom
  - Drag on any chart measures change (price $±% or pp) instead of zooming
  - Snap-to-point drag: snaps to nearest data points, draws dashed vertical
    lines, shows centered tooltip with delta + date range (Google Finance style)
  - Copy button now includes header metrics strip (company name, ticker/dates,
    price/beta/perf cards) above the 4 charts
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data import (load_data, get_company_name, INDEX_MAP,
                  normalize_ticker, search_ticker, YFINANCE_SUFFIX_INDEX_MAP)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Perf vs Beta",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
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

  /* ── Metric cards ── */
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
    border-radius: 10px !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important; transition: box-shadow 0.2s ease !important;
  }
  [data-testid="stPlotlyChart"] > div:hover {
    box-shadow: 0 4px 8px rgba(15,23,42,0.08) !important;
  }
  /* Allow delta-label overlay to escape the chart card */
  [data-testid="stPlotlyChart"] { position: relative; overflow: visible !important; }

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

  /* ── Color-coded metric cards ── */
  .color-metric {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 14px 18px; min-height: 78px;
    display: flex; flex-direction: column; justify-content: center;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04); transition: box-shadow 0.2s;
  }
  .color-metric:hover { box-shadow: 0 4px 8px rgba(15,23,42,0.08); }
  .cm-label {
    color: #64748b; font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.07em;
    font-family: 'Inter', sans-serif; margin-bottom: 4px;
  }
  .cm-value {
    font-size: 20px; font-weight: 700; letter-spacing: -0.02em;
    font-family: 'Inter', sans-serif;
  }

  /* ── Mobile: single-column stack ── */
  @media (max-width: 768px) {
    [data-testid="column"] {
      width: 100% !important; flex: 0 0 100% !important;
      min-width: 100% !important;
    }
  }

  /* ── Chart info tooltips ── */
  .chart-info-row {
    display: flex; justify-content: flex-end;
    margin-bottom: -2px; position: relative; z-index: 200;
  }
  .tip-wrap { position: relative; display: inline-block; }
  .tip-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 16px; height: 16px; border-radius: 50%;
    background: #e2e8f0; color: #475569;
    font-size: 10px; font-weight: 800; font-style: italic;
    font-family: Georgia, 'Times New Roman', serif;
    cursor: help; user-select: none; line-height: 1;
    transition: background 0.15s;
  }
  .tip-icon:hover { background: #cbd5e1; }
  .tip-box {
    visibility: hidden; opacity: 0;
    position: absolute; right: 0; top: 22px;
    background: #1e293b; color: #e2e8f0;
    font-size: 11px; line-height: 1.65; font-weight: 400;
    font-family: 'Inter', sans-serif;
    padding: 10px 14px; border-radius: 8px;
    width: 270px; z-index: 9999;
    box-shadow: 0 4px 20px rgba(0,0,0,0.35);
    transition: opacity 0.15s;
    pointer-events: none; white-space: normal; text-align: left;
  }
  .tip-wrap:hover .tip-box { visibility: visible; opacity: 1; }
  /* Allow tooltip to overflow Streamlit block containers */
  [data-testid="stMarkdown"], .element-container,
  [data-testid="column"], [data-testid="stVerticalBlock"] { overflow: visible !important; }

  /* ── Source note ── */
  .source-note {
    font-size: 10px; color: #94a3b8; text-align: right;
    padding: 4px 8px 0 0; font-family: 'Inter', sans-serif;
  }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
  <h1>📈 Performance vs. Beta</h1>
  <span class="badge">Live</span>
</div>
""", unsafe_allow_html=True)

# ── Pre-cache scheduler (local only — disabled on Streamlit Cloud) ────────────
import os as _os
_ON_CLOUD = bool(
    _os.getenv("STREAMLIT_SHARING_MODE")        # set by Streamlit Community Cloud
    or "/mount/src" in _os.path.abspath(__file__)  # Cloud path convention
)

@st.cache_resource
def _init_scheduler():
    if _ON_CLOUD:
        return False   # skip scheduler on Cloud to avoid cache corruption
    try:
        from pre_cache import start_scheduler
        start_scheduler()
    except Exception:
        pass
    return True

_init_scheduler()

# ── Cached data helpers ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _search(q: str):
    return search_ticker(q)

@st.cache_data(ttl=3600)
def _load(ticker, index_key, period, custom_start=None, custom_end=None):
    df, error = load_data(ticker, index_key=index_key, period=period,
                          start_date=custom_start, end_date=custom_end)
    if error or df.empty:
        # Raise so st.cache_data does NOT cache failures (only successes)
        raise RuntimeError(error or "empty response")
    return df, ""

@st.cache_data(ttl=86400)
def _company(ticker):
    return get_company_name(ticker)

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

# ── Controls ──────────────────────────────────────────────────────────────────
col_tick, col_idx, col_per, col_btn, col_copy, col_spacer = st.columns([2, 1.5, 1.5, 1, 1, 3])
with col_tick:
    raw = st.text_input("Ticker", value="EXPE", label_visibility="visible").upper().strip()

# Clear override when user types a new raw input
if raw != st.session_state.last_raw:
    st.session_state.ticker_override = None
    st.session_state.last_raw = raw

# Determine effective ticker and auto-switch index
if st.session_state.ticker_override:
    ticker    = st.session_state.ticker_override
    exch_code = None
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
            st.session_state.suggested_index = "SPX"
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
    period = st.selectbox("Period", ["YTD", "1y", "2y", "3y", "5y", "Custom"], index=3)
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
    const doc=window.parent.document;
    const all=[...doc.querySelectorAll('.js-plotly-plot')];
    if(all.length<4){btn.disabled=false;btn.textContent='Copy';return;}
    const cw=780,ch=445,sc=1.5,pad=8;
    const rw=Math.round(cw*sc),rh=Math.round(ch*sc),rp=Math.round(pad*sc);
    const imgs=await Promise.all(all.slice(0,4).map(d=>P.toImage(d,{format:'png',width:cw,height:ch,scale:sc})));

    // ── Read header data from DOM ──────────────────────────────────────────────
    const nameText = (doc.querySelector('.company-name')||{}).innerText||'';
    const subText  = (doc.querySelector('.ticker-sub')||{}).innerText||'';
    const cards    = [...doc.querySelectorAll('.color-metric')];

    // ── Header geometry ────────────────────────────────────────────────────────
    const hPad   = Math.round(14*sc);
    const nameFs = Math.round(16*sc);
    const subFs  = Math.round(11*sc);
    const cardH  = Math.round(64*sc);
    const gap    = Math.round(6*sc);
    const headerH= hPad + nameFs + gap + subFs + gap*2 + cardH + hPad;

    const totalW = rw*2+rp*3;
    const cv=document.createElement('canvas');
    cv.width=totalW; cv.height=headerH+rp+rh*2+rp*3;
    const ctx=cv.getContext('2d');
    ctx.fillStyle='#f1f5f9'; ctx.fillRect(0,0,cv.width,cv.height);

    // ── Draw company name ──────────────────────────────────────────────────────
    let y=hPad+nameFs;
    ctx.fillStyle='#0f172a';
    ctx.font=`700 ${nameFs}px Inter,-apple-system,sans-serif`;
    ctx.fillText(nameText, hPad, y);

    // ── Draw ticker / date sub-line ────────────────────────────────────────────
    y+=gap+subFs;
    ctx.fillStyle='#94a3b8';
    ctx.font=`400 ${subFs}px Inter,-apple-system,sans-serif`;
    ctx.fillText(subText, hPad, y);

    // ── Draw metric cards ──────────────────────────────────────────────────────
    if(cards.length){
      const cardGap = Math.round(8*sc);
      const cardW   = Math.round((totalW - hPad*2 - cardGap*(cards.length-1)) / cards.length);
      const cardY   = y + gap*2;
      const labelFs = Math.round(9*sc);
      const valFs   = Math.round(17*sc);
      const r6      = Math.round(6*sc);
      cards.forEach((card,i)=>{
        const lbl = (card.querySelector('.cm-label')||{}).innerText||'';
        const valEl= card.querySelector('.cm-value');
        const val  = valEl ? valEl.innerText||'' : '';
        const col  = valEl ? (valEl.style.color||'#0f172a') : '#0f172a';
        const cx   = hPad + i*(cardW+cardGap);
        // card background + border
        ctx.fillStyle='#ffffff'; ctx.strokeStyle='#e2e8f0'; ctx.lineWidth=Math.round(1*sc);
        ctx.beginPath();
        if(ctx.roundRect) ctx.roundRect(cx,cardY,cardW,cardH,r6);
        else ctx.rect(cx,cardY,cardW,cardH);
        ctx.fill(); ctx.stroke();
        // label
        ctx.fillStyle='#64748b';
        ctx.font=`600 ${labelFs}px Inter,-apple-system,sans-serif`;
        ctx.fillText(lbl, cx+Math.round(10*sc), cardY+Math.round(18*sc));
        // value
        ctx.fillStyle=col;
        ctx.font=`700 ${valFs}px Inter,-apple-system,sans-serif`;
        ctx.fillText(val, cx+Math.round(10*sc), cardY+Math.round(42*sc));
      });
    }

    // ── Draw charts below header ───────────────────────────────────────────────
    const chartOffY=headerH+rp*2;
    const slots=[[imgs[0],rp,chartOffY],[imgs[2],rw+rp*2,chartOffY],[imgs[1],rp,chartOffY+rh+rp],[imgs[3],rw+rp*2,chartOffY+rh+rp]];
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

# ── Custom / YTD date pickers ─────────────────────────────────────────────────
custom_start = custom_end = None
if period == "YTD":
    import datetime as _dt
    custom_start = _dt.date((_dt.date.today()).year, 1, 1)
    custom_end   = _dt.date.today()
elif period == "Custom":
    import datetime as _dt
    cd1, cd2, _ = st.columns([1.5, 1.5, 7])
    with cd1:
        custom_start = st.date_input(
            "From",
            value=_dt.date.today() - _dt.timedelta(days=365),
            max_value=_dt.date.today(),
        )
    with cd2:
        custom_end = st.date_input(
            "To",
            value=_dt.date.today(),
            min_value=custom_start if custom_start else None,
            max_value=_dt.date.today(),
        )

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
    with st.spinner(f"Loading {ticker}…"):
        try:
            df, error = _load(ticker, index_key, period, custom_start, custom_end)
        except RuntimeError as _e:
            df, error = pd.DataFrame(), str(_e)
        company_name = _company(ticker)

    if error or df.empty:
        st.error(f"Could not load data for **{ticker}**: {error or 'empty response'}")
        st.stop()

    # Trim burn-in rows; detect if beta metrics are computable
    df_plot = df.dropna(subset=["perf_vs_beta_12W", "perf_vs_beta_4W", "perf_vs_beta_2W"]).copy()
    beta_ok = not df_plot.empty
    if not beta_ok:
        # Not enough history for beta — fall back to raw price data only
        df_plot = df.dropna(subset=["stock_price"]).copy()
        if df_plot.empty:
            st.error(f"No price data available for **{ticker}**.")
            st.stop()

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

    # ── Metric cards (color-coded) ────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    latest = df.iloc[-1]
    _G, _R, _N = "#10b981", "#ef4444", "#0f172a"

    def _card(col, label, val_str, color=None):
        col.markdown(
            f'<div class="color-metric">'
            f'<div class="cm-label">{label}</div>'
            f'<div class="cm-value" style="color:{color or _N}">{val_str}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def _pcolor(v):
        return _G if v > 0 else (_R if v < 0 else _N)

    pvb_2w  = latest.get("perf_vs_beta_2W",  0) or 0
    pvb_4w  = latest.get("perf_vs_beta_4W",  0) or 0
    pvb_12w = latest.get("perf_vs_beta_12W", 0) or 0

    _card(m1, "Price",            f"${latest.get('stock_price', 0):,.2f}")
    _card(m2, "Beta (6M)",        f"{latest.get('beta', 0):.2f}")
    _card(m3, "Perf vs Beta 2W",  f"{pvb_2w*100:+.1f}%",  _pcolor(pvb_2w))
    _card(m4, "Perf vs Beta 4W",  f"{pvb_4w*100:+.1f}%",  _pcolor(pvb_4w))
    _card(m5, "Perf vs Beta 12W", f"{pvb_12w*100:+.1f}%", _pcolor(pvb_12w))

    # ── Shared axis / layout helpers ──────────────────────────────────────────
    CHART_H = 285
    x_start = df_plot["date"].iloc[0]
    x_end   = df_plot["date"].iloc[-1]

    _ax = dict(
        gridcolor=GRID, zerolinecolor=GRID, zerolinewidth=1,
        tickfont=dict(color=MUTED, size=9, family="Inter, sans-serif"),
        showgrid=True, linecolor=GRID, linewidth=1, showline=True,
        ticks="outside", tickcolor=GRID, ticklen=3,
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikedash="solid", spikecolor="#94a3b8", spikethickness=1,
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
            dragmode=False,
        )

    dates = df_plot["date"]

    # ── Methodology tooltip helper ────────────────────────────────────────────
    _BETA_METHOD = (
        "Rolling beta = Cov(stock daily returns, index daily returns) "
        "/ Var(index daily returns) over 126 trading days (~6 months)."
    )

    def _chart_tip(html: str):
        st.markdown(
            f'<div class="chart-info-row">'
            f'<span class="tip-wrap"><span class="tip-icon">i</span>'
            f'<span class="tip-box">{html}</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    PRICE_TIP = (
        "<b>Price Chart</b><br>"
        "Adjusted closing price history.<br><br>"
        "Source: Yahoo Finance via yfinance."
    )

    def _perf_tip(label: str) -> str:
        return (
            f"<b>Perf vs. Beta — {label}</b><br><br>"
            f"How much the stock outperformed (or underperformed) "
            f"what its beta-adjusted market exposure would predict.<br><br>"
            f"<b>Formula:</b><br>"
            f"Actual {label} Return<br>"
            f"&minus; (Rolling 6M Beta &times; {label} Index Return)<br><br>"
            f"{_BETA_METHOD}<br><br>"
            f"<span style='color:#6ee7b7'>Positive</span> = outperformed "
            f"on a risk-adjusted basis."
        )

    # ── Price chart ───────────────────────────────────────────────────────────
    _px      = df_plot["stock_price"]
    _px_pad  = (_px.max() - _px.min()) * 0.05
    _px_base = _px.min() - _px_pad

    fig_price = go.Figure()
    # Invisible baseline so fill stays above the data minimum (not zero)
    fig_price.add_trace(go.Scatter(
        x=dates, y=[_px_base] * len(dates),
        line=dict(width=0), hoverinfo="skip", showlegend=False,
    ))
    fig_price.add_trace(go.Scatter(
        x=dates, y=_px,
        fill="tonexty", fillcolor="rgba(16,185,129,0.08)",
        line=dict(color=GREEN, width=1.8),
        hovertemplate="%{x|%b %d, %Y}<br><b>$%{y:,.2f}</b><extra></extra>",
    ))
    fig_price.add_trace(go.Scatter(
        x=[dates.iloc[-1]], y=[_px.iloc[-1]],
        mode="markers",
        marker=dict(color=GREEN, size=7, symbol="circle",
                    line=dict(color="white", width=1.5)),
        hoverinfo="skip",
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
        fig.add_trace(go.Scatter(
            x=[dates.iloc[-1]], y=[y.iloc[-1]],
            mode="markers",
            marker=dict(color=color, size=7, symbol="circle",
                        line=dict(color="white", width=1.5)),
            hoverinfo="skip",
        ))
        fig.update_layout(**_base_layout(f"Perf vs. Beta — {label}  ({ticker} vs {index_key})"))
        fig.update_xaxes(range=[x_start, x_end], **_ax)
        fig.update_yaxes(tickformat=".1%", **_ax)
        return fig

    if beta_ok:
        fig_12w = make_perf_fig("perf_vs_beta_12W", ACCENT, "12 Week")
        fig_4w  = make_perf_fig("perf_vs_beta_4W",  PURPLE, "4 Week")
        fig_2w  = make_perf_fig("perf_vs_beta_2W",  AMBER,  "2 Week")
    else:
        def _no_beta_fig(label):
            _f = go.Figure()
            _f.add_annotation(
                text="Not enough history to compute beta metrics<br>"
                     "<span style='font-size:11px;opacity:.7'>"
                     "Requires ~6 months of price data</span>",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=13, color="#94a3b8", family="Inter, sans-serif"),
                align="center",
            )
            _f.update_layout(**_base_layout(
                f"Perf vs. Beta — {label}  ({ticker} vs {index_key})"
            ))
            _f.update_layout(paper_bgcolor="#f1f5f9", plot_bgcolor="#f1f5f9")
            return _f
        fig_12w = _no_beta_fig("12 Week")
        fig_4w  = _no_beta_fig("4 Week")
        fig_2w  = _no_beta_fig("2 Week")

    # ── 2×2 grid: TL=Price, TR=12W, BL=4W, BR=2W ─────────────────────────────
    col_left, col_right = st.columns(2, gap="small")

    _cfg = {"displayModeBar": False}

    with col_left:
        _chart_tip(PRICE_TIP)
        st.plotly_chart(fig_price, use_container_width=True, config=_cfg)
        _chart_tip(_perf_tip("4 Week"))
        st.plotly_chart(fig_4w,   use_container_width=True, config=_cfg)

    with col_right:
        _chart_tip(_perf_tip("12 Week"))
        st.plotly_chart(fig_12w,  use_container_width=True, config=_cfg)
        _chart_tip(_perf_tip("2 Week"))
        st.plotly_chart(fig_2w,   use_container_width=True, config=_cfg)

    # ── Source note ───────────────────────────────────────────────────────────
    st.markdown(
        '<p class="source-note">'
        'Data: Yahoo Finance via yfinance &nbsp;·&nbsp; '
        'Beta window: 126 trading days (~6 months)'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Crosshair sync + price-chart drag-to-measure ─────────────────────────
    st.components.v1.html("""<script>
(function(){
  var attached  =new WeakSet();
  var dragStart =new WeakMap(); // chart → {clientX, snapPt}
  var overlayMap=new WeakMap(); // chart → {lineA,lineB,shade,tip}

  function parseT(v){
    if(typeof v==='number') return v;
    return new Date(String(v).substring(0,10)+'T00:00:00Z').getTime();
  }
  function pixelToDate(src,clientX){
    try{
      var xa=src._fullLayout.xaxis;
      var drag=src.querySelector('.nsewdrag'); if(!drag) return null;
      var bb=drag.getBoundingClientRect();
      var frac=Math.max(0,Math.min(1,(clientX-bb.left)/bb.width));
      var t0=parseT(xa.range[0]),t1=parseT(xa.range[1]);
      return new Date(t0+frac*(t1-t0)).toISOString().substring(0,10);
    }catch(e){return null;}
  }
  function dateToClientX(src,dateStr){
    try{
      var xa=src._fullLayout.xaxis;
      var drag=src.querySelector('.nsewdrag'); if(!drag) return null;
      var bb=drag.getBoundingClientRect();
      var t0=parseT(xa.range[0]),t1=parseT(xa.range[1]);
      var tD=new Date(dateStr+'T00:00:00Z').getTime();
      return bb.left+((tD-t0)/(t1-t0))*bb.width;
    }catch(e){return null;}
  }
  function snapNearest(src,dateStr){
    try{
      var td=new Date(dateStr+'T00:00:00Z').getTime();
      var best=null,bestDiff=Infinity;
      (src.data||[]).forEach(function(tr){
        if(!tr.x||tr.x.length<=1) return;
        if(tr.mode==='markers') return;
        if(tr.line&&Number(tr.line.width)===0) return;
        for(var j=0;j<tr.x.length;j++){
          var yv=parseFloat(tr.y[j]); if(!Number.isFinite(yv)) continue;
          var xd=String(tr.x[j]).substring(0,10);
          var diff=Math.abs(new Date(xd+'T00:00:00Z').getTime()-td);
          if(diff<bestDiff){bestDiff=diff;best={x:xd,y:yv};}
        }
      });
      return best;
    }catch(e){return null;}
  }
  function fmtDate(s){
    return new Date(s+'T00:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
  }

  function charts(){return [...window.parent.document.querySelectorAll('.js-plotly-plot')];}
  function getOverlay(src){
    if(overlayMap.has(src)) return overlayMap.get(src);
    var B=window.parent.document.body;
    function mk(css){var d=window.parent.document.createElement('div');d.style.cssText=css+'display:none;';B.appendChild(d);return d;}
    var ov={
      lineA:mk('position:fixed;width:1px;pointer-events:none;z-index:9998;background:rgba(80,80,120,.5);'),
      lineB:mk('position:fixed;width:1px;pointer-events:none;z-index:9998;background:rgba(80,80,120,.5);'),
      shade:mk('position:fixed;pointer-events:none;z-index:9997;background:rgba(110,120,230,.07);'),
      tip:  mk('position:fixed;pointer-events:none;z-index:99999;padding:5px 14px;border-radius:8px;'
               +'font:bold 13px/1.5 Inter,sans-serif;white-space:nowrap;color:#fff;'
               +'box-shadow:0 2px 12px rgba(0,0,0,.35);transform:translateX(-50%);text-align:center;'),
    };
    overlayMap.set(src,ov); return ov;
  }
  function hideOverlay(src){
    if(!overlayMap.has(src)) return;
    var o=overlayMap.get(src);
    ['lineA','lineB','shade','tip'].forEach(function(k){o[k].style.display='none';});
  }
  function showOverlay(src,ptA,ptB){
    if(ptA.x===ptB.x) return;
    var ov=getOverlay(src);
    var drag=src.querySelector('.nsewdrag'); if(!drag) return;
    var bb=drag.getBoundingClientRect();
    var xA=dateToClientX(src,ptA.x),xB=dateToClientX(src,ptB.x);
    if(xA===null||xB===null) return;
    function posLine(el,x){el.style.left=x+'px';el.style.top=bb.top+'px';el.style.height=bb.height+'px';el.style.display='block';}
    posLine(ov.lineA,xA); posLine(ov.lineB,xB);
    var lo=Math.min(xA,xB),hi=Math.max(xA,xB);
    ov.shade.style.left=lo+'px'; ov.shade.style.top=bb.top+'px';
    ov.shade.style.width=(hi-lo)+'px'; ov.shade.style.height=bb.height+'px';
    ov.shade.style.display='block';
    var first=ptA.x<ptB.x?ptA:ptB, last=ptA.x<ptB.x?ptB:ptA;
    var dy=last.y-first.y, pct=((last.y/first.y)-1)*100;
    var up=dy>=0, color=up?'#10b981':'#ef4444', arrow=up?'▲':'▼';
    ov.tip.style.background=color;
    ov.tip.innerHTML='<span style="font-size:14px">'+(up?'+':'\u2212')+'$'+Math.abs(dy).toFixed(2)
      +' ('+(up?'+':'')+pct.toFixed(1)+'%) '+arrow+'</span>'
      +'<br><span style="font-weight:400;font-size:10px;opacity:.85">'
      +fmtDate(first.x)+' \u2192 '+fmtDate(last.x)+'</span>';
    ov.tip.style.left=((lo+hi)/2)+'px';
    ov.tip.style.top=(bb.top+8)+'px';
    ov.tip.style.display='block';
  }

  /* mousedown — CAPTURE PHASE on document so we fire before Plotly's
     stopPropagation on .nsewdrag (which blocks bubble-phase listeners on src) */
  window.parent.document.addEventListener('mousedown',function(e){
    if(e.button!==0) return;
    charts().forEach(function(src){
      var title=''; try{title=src.layout.title.text||'';}catch(ex){}
      if(!title.includes('Price Chart')||!src.contains(e.target)) return;
      var d=pixelToDate(src,e.clientX); if(!d) return;
      var pt=snapNearest(src,d); if(!pt) return;
      hideOverlay(src);
      dragStart.set(src,{clientX:e.clientX,snapPt:pt});
    });
  },true); // true = capture phase

  window.parent.document.addEventListener('dblclick',function(e){
    charts().forEach(function(src){
      var title=''; try{title=src.layout.title.text||'';}catch(ex){}
      if(!title.includes('Price Chart')||!src.contains(e.target)) return;
      dragStart.delete(src); hideOverlay(src);
    });
  },true);

  /* mousemove — update overlay in real time (throttled via rAF) */
  var raf=null,lastX=0;
  window.parent.document.addEventListener('mousemove',function(e){
    lastX=e.clientX;
    if(raf) return;
    raf=window.parent.requestAnimationFrame(function(){
      raf=null;
      charts().forEach(function(src){
        var s=dragStart.get(src); if(!s) return;
        var d=pixelToDate(src,lastX); if(!d) return;
        var pt=snapNearest(src,d);
        if(pt&&pt.x!==s.snapPt.x) showOverlay(src,s.snapPt,pt);
      });
    });
  });
  /* mouseup — keep overlay visible; clear on single click */
  window.parent.document.addEventListener('mouseup',function(e){
    if(e.button!==0) return;
    charts().forEach(function(src){
      var s=dragStart.get(src); if(!s) return;
      dragStart.delete(src);
      if(Math.abs(e.clientX-s.clientX)<5) hideOverlay(src);
    });
  });

  function setup(){
    var P=window.parent.Plotly; if(!P) return;
    charts().forEach(function(src){
      if(attached.has(src)) return;
      var title=''; try{title=src.layout.title.text||'';}catch(e){}
      if(!title) return; // not ready yet
      attached.add(src);
      /* crosshair sync for all charts */
      src.on('plotly_hover',function(d){
        if(!d.points||!d.points[0]) return;
        var xv=d.points[0].x;
        charts().forEach(function(dst){
          if(dst!==src) try{P.Fx.hover(dst,[{xval:xv}],'xy');}catch(ex){}
        });
      });
      src.on('plotly_unhover',function(){
        charts().forEach(function(dst){
          if(dst!==src) try{P.Fx.hover(dst,[],'xy');}catch(ex){}
        });
      });
    });
  }
  setInterval(setup,800);
})();
</script>""", height=0)
