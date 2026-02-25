"""
Performance vs. Beta — Dynamic Dashboard
=========================================
Run:  python dashboard/app.py
Open: http://localhost:8050

Type any US stock ticker (e.g. CRH, AAPL, MSFT) and click Load.
The four charts mirror the Excel model:
  1. Performance vs. Beta — 12W
  2. Performance vs. Beta — 4W
  3. Performance vs. Beta — 2W
  4. Price Chart
"""

import sys
import os

# Allow running from project root OR from dashboard/ folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from data import load_data, INDEX_MAP

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    title="Perf vs Beta Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

DARK_BG   = "#0d1117"
PANEL_BG  = "#161b22"
ACCENT    = "#58a6ff"
TEXT      = "#e6edf3"
BORDER    = "#30363d"
GREEN     = "#3fb950"
RED       = "#f85149"
CHART_BG  = "#161b22"

app.layout = html.Div(
    style={"backgroundColor": DARK_BG, "minHeight": "100vh",
           "fontFamily": "'Segoe UI', Arial, sans-serif", "color": TEXT},
    children=[

        # ── Header ──────────────────────────────────────────────────────────
        html.Div(
            style={"backgroundColor": PANEL_BG, "borderBottom": f"1px solid {BORDER}",
                   "padding": "16px 24px", "display": "flex",
                   "alignItems": "center", "gap": "24px", "flexWrap": "wrap"},
            children=[
                html.H1("Performance vs. Beta",
                        style={"margin": 0, "fontSize": "20px",
                               "fontWeight": 600, "color": TEXT}),

                # Ticker input
                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                    children=[
                        html.Label("Ticker:", style={"fontSize": "13px",
                                                     "color": "#8b949e",
                                                     "whiteSpace": "nowrap"}),
                        dcc.Input(
                            id="ticker-input",
                            type="text",
                            value="CRH",
                            debounce=False,
                            placeholder="e.g. CRH, AAPL",
                            style={
                                "backgroundColor": DARK_BG, "color": TEXT,
                                "border": f"1px solid {BORDER}", "borderRadius": "6px",
                                "padding": "6px 10px", "fontSize": "14px",
                                "width": "110px", "outline": "none",
                            },
                        ),
                    ],
                ),

                # Index selector
                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                    children=[
                        html.Label("vs. Index:", style={"fontSize": "13px",
                                                        "color": "#8b949e",
                                                        "whiteSpace": "nowrap"}),
                        dcc.Dropdown(
                            id="index-dropdown",
                            options=[{"label": k, "value": k} for k in INDEX_MAP],
                            value="SPX",
                            clearable=False,
                            style={
                                "backgroundColor": DARK_BG, "color": TEXT,
                                "border": f"1px solid {BORDER}", "borderRadius": "6px",
                                "width": "100px", "fontSize": "14px",
                            },
                        ),
                    ],
                ),

                # Period selector
                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                    children=[
                        html.Label("Period:", style={"fontSize": "13px",
                                                     "color": "#8b949e",
                                                     "whiteSpace": "nowrap"}),
                        dcc.Dropdown(
                            id="period-dropdown",
                            options=[
                                {"label": "1 Year",  "value": "1y"},
                                {"label": "2 Years", "value": "2y"},
                                {"label": "3 Years", "value": "3y"},
                                {"label": "5 Years", "value": "5y"},
                            ],
                            value="3y",
                            clearable=False,
                            style={
                                "backgroundColor": DARK_BG, "color": TEXT,
                                "border": f"1px solid {BORDER}", "borderRadius": "6px",
                                "width": "110px", "fontSize": "14px",
                            },
                        ),
                    ],
                ),

                # Load button
                html.Button(
                    "Load",
                    id="load-btn",
                    n_clicks=0,
                    style={
                        "backgroundColor": ACCENT, "color": "#0d1117",
                        "border": "none", "borderRadius": "6px",
                        "padding": "7px 18px", "fontSize": "14px",
                        "fontWeight": 600, "cursor": "pointer",
                    },
                ),

                # Status message
                html.Div(id="status-msg",
                         style={"fontSize": "12px", "color": "#8b949e",
                                "marginLeft": "auto"}),
            ],
        ),

        # ── Chart grid ──────────────────────────────────────────────────────
        html.Div(
            style={"padding": "16px"},
            children=[
                dcc.Loading(
                    id="loading",
                    type="circle",
                    color=ACCENT,
                    children=[
                        dcc.Graph(
                            id="main-charts",
                            config={"displayModeBar": True,
                                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                    "toImageButtonOptions": {"format": "png",
                                                             "scale": 2}},
                            style={"height": "85vh"},
                        )
                    ],
                )
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-charts", "figure"),
    Output("status-msg",  "children"),
    Output("status-msg",  "style"),
    Input("load-btn", "n_clicks"),
    State("ticker-input",   "value"),
    State("index-dropdown", "value"),
    State("period-dropdown","value"),
    prevent_initial_call=False,
)
def update_charts(n_clicks, ticker, index_key, period):
    ticker = (ticker or "CRH").upper().strip()
    df, error = load_data(ticker, index_key=index_key, period=period)

    if error or df.empty:
        msg = error or "No data returned."
        empty_fig = go.Figure()
        empty_fig.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=CHART_BG,
            font={"color": TEXT},
            annotations=[{"text": f"Error: {msg}", "showarrow": False,
                          "xref": "paper", "yref": "paper",
                          "x": 0.5, "y": 0.5,
                          "font": {"size": 16, "color": RED}}],
        )
        error_style = {"fontSize": "12px", "color": RED, "marginLeft": "auto"}
        return empty_fig, msg, error_style

    fig = build_figure(df, ticker, index_key)
    ok_style = {"fontSize": "12px", "color": GREEN, "marginLeft": "auto"}
    return fig, f"Loaded {len(df):,} trading days for {ticker}", ok_style


# ---------------------------------------------------------------------------
# Figure builder
# ---------------------------------------------------------------------------

def build_figure(df: pd.DataFrame, ticker: str, index_key: str) -> go.Figure:
    date_col = "date"
    if date_col not in df.columns:
        # Fallback for index named differently
        df = df.reset_index()
        date_col = df.columns[0]

    dates = df[date_col]

    # ── Subplot layout (2 × 2) ──────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            f"Performance vs. Beta — 12 Week  ({ticker} vs {index_key})",
            f"Performance vs. Beta — 4 Week   ({ticker} vs {index_key})",
            f"Performance vs. Beta — 2 Week   ({ticker} vs {index_key})",
            f"Price Chart — {ticker}",
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.06,
    )

    # Shared trace kwargs
    def line_trace(y, name, color, row, col, fill=False):
        kwargs = dict(
            x=dates, y=y, name=name,
            line=dict(color=color, width=1.5),
            showlegend=False,
        )
        if fill:
            kwargs.update(fill="tozeroy",
                          fillcolor=color.replace(")", ",0.10)").replace("rgb", "rgba"))
        fig.add_trace(go.Scatter(**kwargs), row=row, col=col)

    # ── Chart 1: Perf vs Beta 12W (top-left) ───────────────────────────────
    pvb_12w = df.get("perf_vs_beta_12W")
    if pvb_12w is not None:
        pos = pvb_12w.clip(lower=0)
        neg = pvb_12w.clip(upper=0)

        fig.add_trace(go.Scatter(
            x=dates, y=pvb_12w, name="Perf vs Beta 12W",
            line=dict(color=ACCENT, width=1.5), showlegend=False,
        ), row=1, col=1)

        # Zero line reference
        fig.add_hline(y=0, line_dash="dot", line_color=BORDER,
                      line_width=1, row=1, col=1)

    # ── Chart 2: Perf vs Beta 4W (top-right) ───────────────────────────────
    pvb_4w = df.get("perf_vs_beta_4W")
    if pvb_4w is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=pvb_4w, name="Perf vs Beta 4W",
            line=dict(color="#d2a8ff", width=1.5), showlegend=False,
        ), row=1, col=2)
        fig.add_hline(y=0, line_dash="dot", line_color=BORDER,
                      line_width=1, row=1, col=2)

    # ── Chart 3: Perf vs Beta 2W (bottom-left) ─────────────────────────────
    pvb_2w = df.get("perf_vs_beta_2W")
    if pvb_2w is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=pvb_2w, name="Perf vs Beta 2W",
            line=dict(color="#ffa657", width=1.5), showlegend=False,
        ), row=2, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color=BORDER,
                      line_width=1, row=2, col=1)

    # ── Chart 4: Price Chart (bottom-right) ────────────────────────────────
    stock_px = df.get("stock_price")
    if stock_px is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=stock_px, name=f"{ticker} Price",
            line=dict(color=GREEN, width=1.8), showlegend=False,
            fill="tozeroy",
            fillcolor="rgba(63,185,80,0.08)",
        ), row=2, col=2)

    # ── Global layout ───────────────────────────────────────────────────────
    axis_style = dict(
        gridcolor=BORDER, zerolinecolor=BORDER,
        tickfont=dict(color="#8b949e", size=10),
        showgrid=True,
    )

    fig.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=TEXT, family="'Segoe UI', Arial, sans-serif"),
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=PANEL_BG, bordercolor=BORDER,
                        font=dict(color=TEXT, size=12)),
    )

    # Apply axis styling to all subplots
    for i in range(1, 5):
        row, col = (1, 1) if i == 1 else (1, 2) if i == 2 else (2, 1) if i == 3 else (2, 2)
        fig.update_xaxes(axis_style, row=row, col=col)
        fig.update_yaxes(axis_style, row=row, col=col)

    # Y-axis: perf charts show as percentages, price shows absolute
    for row, col in [(1, 1), (1, 2), (2, 1)]:
        fig.update_yaxes(tickformat=".1%", row=row, col=col)

    # Format price axis with comma-separated thousands
    fig.update_yaxes(tickformat=",.2f", row=2, col=2)

    # Style subplot titles
    for ann in fig.layout.annotations:
        ann.font = dict(size=12, color="#8b949e")

    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting Performance vs. Beta Dashboard...")
    print("Open http://localhost:8050 in your browser\n")
    app.run(debug=False, host="0.0.0.0", port=8050)
