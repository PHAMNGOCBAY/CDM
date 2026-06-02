"""§72 Task 7 — Helper vẽ biểu đồ ngay sau mỗi bảng.

Quy ước:
- DataFrame có cột số → bar chart hoặc heatmap
- DataFrame có cột depth/elev → profile chart (depth-Y, elev-Y)
- DataFrame so sánh phương án → grouped bar
- Pass kind="auto" để tự chọn.

Returns plotly Figure đã styled.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go


# Defaults
COLOR_PALETTE = [
    "#1565C0", "#D32F2F", "#2E7D32", "#F57F17",
    "#6A1B9A", "#00838F", "#AD1457", "#558B2F",
]
HEIGHT_DEFAULT = 380
FONT_BASE = dict(family="Inter, Segoe UI, sans-serif", size=12, color="#212121")
FONT_TITLE = dict(size=14, color="#0D47A1")


def _bar_categorical(df: pd.DataFrame, x_col: str, y_cols: list[str],
                       title: str = "") -> go.Figure:
    """Bar chart cho bảng có 1 cột text (x) + nhiều cột số (y)."""
    fig = go.Figure()
    for i, ycol in enumerate(y_cols):
        fig.add_trace(go.Bar(
            x=df[x_col], y=df[ycol],
            name=ycol, marker_color=COLOR_PALETTE[i % len(COLOR_PALETTE)],
            text=[f"{v:.1f}" if pd.notna(v) and isinstance(v, (int, float))
                  else "" for v in df[ycol]],
            textposition="outside", textfont=dict(size=10),
        ))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=FONT_TITLE),
        barmode="group", height=HEIGHT_DEFAULT, font=FONT_BASE,
        plot_bgcolor="white",
        xaxis=dict(title=x_col, tickangle=-30 if df.shape[0] > 6 else 0),
        yaxis=dict(title="Giá trị", showgrid=True, gridcolor="#EEEEEE"),
        margin=dict(l=60, r=30, t=60, b=80),
        legend=dict(orientation="h", y=-0.20),
    )
    return fig


def _heatmap(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Heatmap khi df đã pivot. df.index = hàng, df.columns = cột, values."""
    fig = go.Figure(data=go.Heatmap(
        z=df.values, x=df.columns.tolist(), y=df.index.tolist(),
        colorscale="RdYlGn_r",
        text=[[f"{v:.1f}" if pd.notna(v) else "" for v in row]
              for row in df.values],
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title="Giá trị"),
    ))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=FONT_TITLE),
        height=HEIGHT_DEFAULT, font=FONT_BASE,
        margin=dict(l=80, r=30, t=60, b=60),
    )
    return fig


def auto_chart_for(
    df: pd.DataFrame,
    *,
    kind: str = "auto",
    title: str = "",
    x_col: Optional[str] = None,
    y_cols: Optional[list[str]] = None,
) -> Optional[go.Figure]:
    """Tự chọn loại chart dựa theo cấu trúc dataframe.

    kind = "auto" | "bar" | "heatmap" | "scatter"
    Returns None nếu df trống.
    """
    if df is None or df.empty:
        return None

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return None

    if kind == "heatmap":
        return _heatmap(df, title)

    # Bar mặc định
    if x_col is None:
        # Cột text đầu tiên làm x
        text_cols = df.select_dtypes(exclude="number").columns.tolist()
        x_col = text_cols[0] if text_cols else df.index.name or "index"
        if x_col not in df.columns:
            df = df.reset_index()
            x_col = df.columns[0]
    y_cols = y_cols or num_cols[:3]  # max 3 cột để không quá rối
    return _bar_categorical(df, x_col, y_cols, title)


def render_chart_after(df: pd.DataFrame, *, st, **kwargs) -> None:
    """Tiện ích cho Streamlit: render chart NGAY sau bảng. st = streamlit module."""
    fig = auto_chart_for(df, **kwargs)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
