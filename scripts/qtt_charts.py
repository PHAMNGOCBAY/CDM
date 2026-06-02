"""
qtt_charts.py — Biểu đồ Plotly cho zone QTT.

Tất cả biểu đồ:
  - Font 12pt
  - Hiển thị giá trị trực tiếp trên điểm/cột (không bỏ sót)
  - Tiêu đề bảng/biểu đồ in đậm
  - Không emoji
  - Tiếng Việt có dấu

Hàm chính:
  cross_section_geo(zone_data)        — trắc dọc địa chất qua 6 HK (PCA chainage)
  cdm_tip_profile(zone_data, dS)      — trắc dọc đáy cọc CDM
  stress_chart_with_10pct(bh_data)    — σ'v0 + Δσ + ngưỡng 10%
  layer_params_chart(bh_layers_data)  — chỉ tiêu cơ lý per HK với tất cả số liệu lab
  smoothness_chart(pairs)             — pair-wise smoothness vs ngưỡng

Color map theo symbol TCVN.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
import plotly.graph_objects as go


FONT_BASE = dict(family="Arial", size=12, color="#111827")
FONT_TITLE = dict(family="Arial", size=14, color="#111827")

# Màu theo ký hiệu lớp TCVN
LAYER_COLORS = {
    "F":  "#9E9E9E",   # đất đắp / fill
    "1":  "#FFB74D",   # bùn sét chảy (rất yếu)
    "1b": "#FFA000",   # sét pha dẻo mềm (yếu)
    "2":  "#FF7043",   # sét pha vừa
    "2a": "#A1887F",   # cát pha
    "3":  "#8D6E63",   # sét pha dẻo cứng
    "4":  "#5D4037",   # sét/cát cứng
    "5":  "#90A4AE",   # cát
    "5a": "#B0BEC5",
    "6":  "#607D8B",   # cuội sỏi
    "7":  "#455A64",
    "?":  "#BDBDBD",
}

OK_COLOR = "#2E7D32"
FAIL_COLOR = "#C62828"
WARN_COLOR = "#F57C00"
PRIM_COLOR = "#1565C0"


# ════════ 1. PCA-SVD chainage ════════
def _pca_chainage(points_EN: list[tuple[float, float]]) -> list[float]:
    """Chiếu các điểm 2D (E, N) lên trục chính (PCA-SVD). Bắt đầu từ 0."""
    if not points_EN:
        return []
    arr = np.array(points_EN, dtype=float)
    centered = arr - arr.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    direction = vh[0]
    chain = centered @ direction
    chain = chain - chain.min()
    return chain.tolist()


# ════════ 2. Trắc dọc địa chất ════════
def cross_section_geo(
    boreholes: list[dict],
    layers_by_bh: dict[str, list[dict]],
    spt_by_bh: dict[str, list[dict]] | None = None,
    design_elev_by_bh: dict[str, float] | None = None,
) -> go.Figure:
    """Trắc dọc địa chất qua các HK.

    boreholes: [{name, N, E, elevation_m, depth_m, H_soft_m}, ...]
    layers_by_bh: {bh_name: [{symbol, depth_top_m, depth_bot_m, ...}, ...]}
    design_elev_by_bh: {bh_name: elev_thiết_kế_m} — nếu None thì không vẽ
    """
    # PCA chainage
    EN = [(b["E"], b["N"]) for b in boreholes]
    chainages = _pca_chainage(EN)
    # Sort HKs theo chainage
    order = sorted(range(len(boreholes)), key=lambda i: chainages[i])
    bhs_sorted = [boreholes[i] for i in order]
    chain_sorted = [chainages[i] for i in order]

    fig = go.Figure()

    # Width mỗi cột HK trên chart
    n = len(bhs_sorted)
    if n > 1:
        gaps = [chain_sorted[i + 1] - chain_sorted[i] for i in range(n - 1)]
        col_w = max(min(min(gaps), 30), 15) * 0.4
    else:
        col_w = 8

    # Vẽ cột địa tầng cho mỗi HK
    for bh, x_c in zip(bhs_sorted, chain_sorted):
        elev = bh["elevation_m"]
        layers = layers_by_bh.get(bh["name"], [])
        if not layers:
            continue
        for L in layers:
            sym = L["symbol"]
            color = LAYER_COLORS.get(sym, "#BDBDBD")
            top_z = elev - L["depth_top_m"]
            bot_z = elev - L["depth_bot_m"]
            # Vẽ rectangle qua add_shape
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=x_c - col_w / 2, x1=x_c + col_w / 2,
                y0=bot_z, y1=top_z,
                fillcolor=color, line=dict(color="black", width=0.5),
                layer="below",
            )
            # Label ký hiệu lớp ở giữa
            fig.add_annotation(
                x=x_c, y=(top_z + bot_z) / 2,
                text=f"<b>{sym}</b>",
                showarrow=False, font=dict(size=11, color="white"
                                            if sym in ("1", "1b", "F")
                                            else "black"),
            )
            # Label cao độ đáy lớp ở rìa phải (KHỚP trục Y), dưới là độ sâu
            fig.add_annotation(
                x=x_c + col_w / 2 + 0.5, y=bot_z,
                text=f"{bot_z:+.2f}m<br><span style='font-size:8pt;color:#666'>"
                     f"(sâu {L['depth_bot_m']:.1f}m)</span>",
                xanchor="left", showarrow=False,
                font=dict(size=9, color="#333"),
                align="left",
            )

        # Label tên HK + cao độ TN trên cùng
        fig.add_annotation(
            x=x_c, y=elev + 1.5,
            text=f"<b>{bh['name']}</b><br>+{elev:.2f}m",
            showarrow=False, font=dict(size=12, color="#111827"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#1565C0", borderwidth=1,
        )

        # Đường nối mặt đất TN
        # (sẽ vẽ sau khi có tất cả HK)

    # Đường nối cao độ thiết kế (nếu có)
    if design_elev_by_bh:
        des_vals = [design_elev_by_bh.get(b["name"]) for b in bhs_sorted]
        # Chỉ vẽ nếu có ít nhất 2 giá trị hợp lệ
        if sum(1 for v in des_vals if v is not None) >= 2:
            fig.add_trace(go.Scatter(
                x=chain_sorted, y=des_vals,
                mode="lines+markers+text",
                line=dict(color="#1565C0", width=2.5, dash="dashdot"),
                marker=dict(size=10, color="#1565C0", symbol="square",
                            line=dict(color="white", width=1)),
                text=[f"+{v:.2f}" if v is not None else "" for v in des_vals],
                textposition="top center",
                textfont=dict(size=11, color="#1565C0"),
                name="Cao độ thiết kế",
            ))

    # Đường nối mặt đất TN
    fig.add_trace(go.Scatter(
        x=chain_sorted,
        y=[b["elevation_m"] for b in bhs_sorted],
        mode="lines+markers+text",
        line=dict(color="#5D4037", width=2.5, dash="solid"),
        marker=dict(size=10, color="#5D4037"),
        text=[f"+{b['elevation_m']:.2f}" for b in bhs_sorted],
        textposition="top center", textfont=dict(size=11),
        name="Mặt đất tự nhiên",
    ))

    # Đường nối đáy HK
    fig.add_trace(go.Scatter(
        x=chain_sorted,
        y=[b["elevation_m"] - (b.get("depth_m") or 36) for b in bhs_sorted],
        mode="lines+markers",
        line=dict(color="black", width=1.5, dash="dot"),
        marker=dict(size=8, color="black"),
        name="Đáy HK",
    ))

    # Đường nối đáy lớp yếu (theo H_soft)
    soft_bots = []
    for b in bhs_sorted:
        h_soft = b.get("H_soft_m") or 0
        # Đáy lớp yếu = elev - clay_top - H_soft (giả định clay_top từ layer đầu tiên không F)
        layers = layers_by_bh.get(b["name"], [])
        clay_top = 0
        for L in layers:
            if L["symbol"] not in ("F",):
                clay_top = L["depth_top_m"]; break
        soft_bots.append(b["elevation_m"] - clay_top - h_soft)
    fig.add_trace(go.Scatter(
        x=chain_sorted, y=soft_bots,
        mode="lines+markers+text",
        line=dict(color=FAIL_COLOR, width=2, dash="dash"),
        marker=dict(size=10, color=FAIL_COLOR, symbol="triangle-down"),
        text=[f"{v:.1f}m" for v in soft_bots],
        textposition="bottom center", textfont=dict(size=10, color=FAIL_COLOR),
        name="Đáy lớp yếu (H_soft)",
    ))

    fig.update_layout(
        title=dict(
            text="<b>Trắc dọc địa chất qua các hố khoan QTT</b>",
            font=FONT_TITLE,
        ),
        xaxis=dict(title="Chainage (m, PCA)", showgrid=True),
        yaxis=dict(title="Cao độ (m)", showgrid=True),
        height=650,
        font=FONT_BASE,
        showlegend=True,
        plot_bgcolor="white",
    )
    return fig


# ════════ 3. Trắc dọc đáy cọc CDM ════════
def cdm_tip_profile(
    boreholes: list[dict],
    lc_data: list[dict],   # rows từ cdm_zone_design_results filter QTT
    dS_cm: float = 30.0,
    layers_by_bh: Optional[dict[str, list[dict]]] = None,
) -> go.Figure:
    """Trắc dọc đáy CDM cho 1 mức ΔS."""
    EN = [(b["E"], b["N"]) for b in boreholes]
    chains = _pca_chainage(EN)
    order = sorted(range(len(boreholes)), key=lambda i: chains[i])
    bhs_sorted = [boreholes[i] for i in order]
    chain_sorted = [chains[i] for i in order]

    # Map bh → Lc, tip_depth
    lc_by_bh = {r["bh_name"]: r for r in lc_data if r["delta_S_cm"] == dS_cm}

    fig = go.Figure()

    # Mặt đất TN — TÊN HK ở annotation phía trên, giá trị cao độ ở text
    elev_y = [b["elevation_m"] for b in bhs_sorted]
    fig.add_trace(go.Scatter(
        x=chain_sorted, y=elev_y,
        mode="lines+markers",
        line=dict(color="#5D4037", width=2),
        marker=dict(size=8),
        name="Mặt đất TN",
        hovertemplate="HK: %{customdata}<br>Cao độ TN: %{y:.2f} m<extra></extra>",
        customdata=[b["name"] for b in bhs_sorted],
    ))
    # Annotation tên HK + cao độ TN — đặt PHÍA TRÊN biểu đồ (1 vị trí cố định, không che)
    max_elev = max(elev_y) if elev_y else 5.0
    for i, b in enumerate(bhs_sorted):
        fig.add_annotation(
            x=chain_sorted[i], y=max_elev + 1.5,
            text=f"<b>{b['name']}</b><br>+{b['elevation_m']:.2f}",
            showarrow=False, font=dict(size=10, color="#5D4037"),
            xanchor="center", yanchor="bottom",
            bgcolor="rgba(255,248,225,0.85)", bordercolor="#8D6E63",
            borderwidth=0.6, borderpad=2,
        )

    # Đỉnh CDM (= elev - cdm_top_depth) — annotation textposition luân phiên
    cdm_tops = []
    for b in bhs_sorted:
        r = lc_by_bh.get(b["name"], {})
        top_e = r.get("cdm_top_elev_m")
        if top_e is None:
            top_e = 0.8
        cdm_tops.append(top_e)
    # textposition luân phiên: top right / top left để tránh chồng tên HK ở top center
    pos_alt = ["top right" if i % 2 == 0 else "top left"
                for i in range(len(bhs_sorted))]
    fig.add_trace(go.Scatter(
        x=chain_sorted, y=cdm_tops,
        mode="lines+markers+text",
        line=dict(color="#1565C0", width=2.5),
        marker=dict(size=10, symbol="square"),
        text=[f"+{v:.2f}" if v is not None else "—" for v in cdm_tops],
        textposition=pos_alt, textfont=dict(size=10, color="#1565C0"),
        name="Đỉnh CDM TK",
        hovertemplate="HK: %{customdata}<br>Đỉnh CDM: %{y:.2f} m<extra></extra>",
        customdata=[b["name"] for b in bhs_sorted],
    ))

    # Đáy cọc CDM (= elev - tip_depth)
    cdm_tips = []
    labels = []
    colors_tip = []
    for b in bhs_sorted:
        r = lc_by_bh.get(b["name"], {})
        tip = r.get("tip_depth_m")
        ok = r.get("ok")
        Lc = r.get("Lc_m")
        if tip is not None:
            cdm_tips.append(b["elevation_m"] - tip)
            tip_label = f"Lc={Lc:.1f}m" if Lc is not None else "KĐ"
            labels.append(tip_label)
            colors_tip.append(OK_COLOR if ok else FAIL_COLOR)
        else:
            cdm_tips.append(None)
            labels.append("KĐ")
            colors_tip.append(FAIL_COLOR)
    fig.add_trace(go.Scatter(
        x=chain_sorted, y=cdm_tips,
        mode="lines+markers+text",
        line=dict(color="#D32F2F", width=2.5),
        marker=dict(size=14, symbol="triangle-down",
                    color=colors_tip),
        text=labels,
        textposition="bottom center",
        textfont=dict(size=11, color="#D32F2F"),
        name="Đáy cọc CDM",
    ))

    # Đáy lớp yếu
    if layers_by_bh:
        soft_bots = []
        for b in bhs_sorted:
            layers = layers_by_bh.get(b["name"], [])
            clay_top = 0
            for L in layers:
                if L["symbol"] != "F":
                    clay_top = L["depth_top_m"]; break
            soft_bots.append(b["elevation_m"] - clay_top - (b.get("H_soft_m") or 0))
        fig.add_trace(go.Scatter(
            x=chain_sorted, y=soft_bots,
            mode="lines+markers+text",
            line=dict(color="#F57C00", width=2, dash="dash"),
            marker=dict(size=10, symbol="diamond"),
            text=[f"{v:.1f}" for v in soft_bots],
            textposition="bottom center", textfont=dict(size=10, color="#F57C00"),
            name="Đáy lớp yếu",
        ))

    # Cảnh báo cọc thả nổi (Lc tip > đáy yếu)
    annotations = []
    for i, b in enumerate(bhs_sorted):
        r = lc_by_bh.get(b["name"], {})
        if r.get("penetrates_full") == 0 and r.get("tip_depth_m"):
            tip_d = r["tip_depth_m"]
            H_soft = b.get("H_soft_m") or 0
            layers = (layers_by_bh or {}).get(b["name"], [])
            clay_top = 0
            for L in layers:
                if L["symbol"] != "F":
                    clay_top = L["depth_top_m"]; break
            p_pen = tip_d - clay_top
            ratio = p_pen / H_soft if H_soft > 0 else 0
            if ratio < 0.8 and ratio > 0:
                annotations.append(
                    dict(x=chain_sorted[i],
                          y=b["elevation_m"] - tip_d - 1.5,
                          text=f"<b>Thả nổi</b><br>p/H={ratio:.0%}",
                          showarrow=True, arrowhead=2,
                          font=dict(size=10, color=FAIL_COLOR),
                          bgcolor="rgba(255,235,238,0.9)",
                          bordercolor=FAIL_COLOR)
                )

    fig.update_layout(
        title=dict(
            text=f"<b>Trắc dọc đáy cọc CDM — ΔS = {dS_cm:.0f} cm</b>",
            font=FONT_TITLE,
        ),
        xaxis=dict(title="Chainage (m)", showgrid=True),
        yaxis=dict(title="Cao độ (m)", showgrid=True,
                    range=[min(cdm_tips) - 3 if cdm_tips and any(cdm_tips) else -35,
                           max_elev + 4.5]),
        height=580, font=FONT_BASE,
        annotations=annotations + list(fig.layout.annotations),
        plot_bgcolor="white",
        margin=dict(l=60, r=30, t=120, b=60),
    )
    return fig


# ════════ 4. Helpers: compute đáy vùng ảnh hưởng lún ════════
def compute_d_stop(
    bh_data: dict,
    q_cdm_kPa: float = 40.8,
    gwl_elev_m: float | None = 0.0,
    gamma_w: float = 9.81,
) -> dict:
    """Tính độ sâu d_stop tại đó σ'v0 = 10·q_cdm.

    Returns dict: {d_stop_m, elev_stop_m, sigma_eff_at_stop, max_d_hk}
    """
    layers = bh_data.get("layers", [])
    if not layers:
        return {"d_stop_m": None, "elev_stop_m": None,
                "sigma_eff_at_stop": None, "max_d_hk": None}
    elev = bh_data["elevation_m"]
    GAMMA_BY_SYMBOL = {"F": 18.0, "1": 14.6, "1b": 17.5, "2": 18.0,
                       "2a": 18.5, "3": 19.0, "5": 19.5, "6": 20.0,
                       "?": 17.5}
    max_d = layers[-1]["depth_bot_m"]
    last_gamma = GAMMA_BY_SYMBOL.get(layers[-1]["symbol"], 17.5)
    g_sub_last = max(1.0, last_gamma - gamma_w)
    target_eff = 10.0 * q_cdm_kPa
    gwl_d = (float("inf") if gwl_elev_m is None
              else max(0.0, elev - gwl_elev_m))

    # Step-wise integration tới khi đạt target hoặc max 200m
    import numpy as np
    step = 0.1
    cum_total = 0.0
    last_d = 0.0
    for d in np.arange(step, 200.0, step):
        if d <= max_d:
            # Lookup gamma layer
            g = None
            for L in layers:
                if L["depth_top_m"] <= d <= L["depth_bot_m"]:
                    g = GAMMA_BY_SYMBOL.get(L["symbol"], 17.5); break
            if g is None:
                g = last_gamma
        else:
            g = last_gamma
        cum_total += g * (d - last_d)
        u = gamma_w * max(0.0, d - gwl_d)
        sigma_eff = cum_total - u
        if sigma_eff >= target_eff:
            return {
                "d_stop_m": round(d, 2),
                "elev_stop_m": round(elev - d, 2),
                "sigma_eff_at_stop": round(sigma_eff, 1),
                "max_d_hk": max_d,
            }
        last_d = d
    return {"d_stop_m": None, "elev_stop_m": None,
            "sigma_eff_at_stop": None, "max_d_hk": max_d}


def compute_dsigma_boussinesq(
    z_below_tip: float,
    q_kPa: float = 40.8,
    B_eq_m: float = 1.8,
    method: str = "2:1",
) -> float:
    """§72 Task S — Δσ dưới mũi cọc CDM phân bố theo Boussinesq.

    Tải q áp tại đáy khối CDM (tip), phân bố sang đất nguyên dưới mũi theo
    Boussinesq cho diện chữ nhật B×B (B = khoảng cách cọc s, đại diện ô đơn vị).

    method:
        "2:1"        — phương pháp 2:1 (Boussinesq giản hoá Westergaard):
                        Δσ(z) = q·B²/(B+z)²
        "boussinesq" — closed-form Newmark cho ô vuông B×B tại tâm:
                        4·corner_factor (chính xác hơn)

    Tham chiếu:
    - Bowles (1996), Foundation Analysis and Design, §10.5
    - Das (2010), Principles of Geotechnical Engineering, §10.4
    """
    if z_below_tip < 0:
        return q_kPa
    if z_below_tip < 1e-6:
        return q_kPa

    if method == "boussinesq":
        # Newmark cho ô vuông tại tâm = 4 × corner-factor cho B/2 × B/2
        b = B_eq_m / 2.0
        z = z_below_tip
        m = b / z; n = b / z
        # Closed-form Boussinesq corner factor I_c
        import math
        R1 = math.sqrt(m * m + 1)
        R2 = math.sqrt(n * n + 1)
        R3 = math.sqrt(m * m + n * n + 1)
        try:
            I_c = (1.0 / (2.0 * math.pi)) * (
                (2 * m * n * R3) / (m * m + n * n + m * m * n * n + 1)
                * (m * m + n * n + 2) / (m * m + n * n + 1)
                + math.asin(
                    2 * m * n * R3 / max(1e-9,
                                          (R1 * R1 * R2 * R2 - m * m * n * n))
                )
            )
        except (ValueError, ZeroDivisionError):
            I_c = 0.0
        return q_kPa * 4.0 * I_c
    else:
        # 2:1 method — đơn giản, robust
        denom = (B_eq_m + z_below_tip) ** 2
        if denom <= 0:
            return 0.0
        return q_kPa * (B_eq_m ** 2) / denom


# ════════ 4b. Biểu đồ ứng suất + ngưỡng 10% + tải CDM ════════
def stress_chart_with_10pct(
    bh_name: str,
    bh_data: dict,
    q_cdm_kPa: float = 40.8,
    compact: bool = False,
    gwl_elev_m: float | None = 0.0,
    gamma_w: float = 9.81,
    show_boussinesq: bool = True,
    cdm_tip_depth_m: float | None = None,
    B_eq_m: float = 1.8,
) -> go.Figure:
    """Profile σ'v0 + Δσ + tải CDM (đường thẳng đứng) + ngưỡng 10%·σ'v0.

    compact=True → kích thước nhỏ phù hợp grid 3 cột × 2 hàng.

    Đường biểu diễn:
      σ'v0       — màu xanh, tự trọng
      σ'v0 + Δσ  — đỏ đứt, sau khi đắp đầy đủ
      10%·σ'v0   — cam chấm, ngưỡng dừng tính lún
      Δσ_CDM     — tím đứt dọc, tải trọng của phương án CDM
      Δσ < 10%   — vùng tô vàng dưới điểm cắt → bỏ qua lún

    Args:
        q_cdm_kPa: tải trọng phương án CDM (kPa), vẽ đường dọc + nhãn.
    """
    layers = bh_data.get("layers", [])
    if not layers:
        fig = go.Figure()
        fig.add_annotation(text=f"HK {bh_name}: không có địa tầng",
                            xref="paper", yref="paper", x=0.5, y=0.5,
                            showarrow=False, font=dict(size=12))
        fig.update_layout(height=320 if compact else 500,
                          font=FONT_BASE,
                          title=dict(text=f"<b>HK {bh_name}</b>",
                                      font=dict(size=12)))
        return fig

    elev = bh_data["elevation_m"]
    GAMMA_BY_SYMBOL = {"F": 18.0, "1": 14.6, "1b": 17.5, "2": 18.0,
                       "2a": 18.5, "3": 19.0, "5": 19.5, "6": 20.0,
                       "?": 17.5}

    max_d = layers[-1]["depth_bot_m"]
    last_symbol = layers[-1]["symbol"]
    last_gamma = GAMMA_BY_SYMBOL.get(last_symbol, 17.5)
    gamma_w_local = 9.81
    g_sub_last = max(1.0, last_gamma - gamma_w_local)  # γ' (đẩy nổi)

    # Tính σ'v0 tại max_d → ước lượng độ sâu cần extend để đạt target = 10·q
    target_eff = 10.0 * q_cdm_kPa
    if gwl_elev_m is None:
        gwl_d_tmp = float("inf")  # không có MNN
    else:
        gwl_d_tmp = max(0.0, elev - gwl_elev_m)
    # Tổng ứng suất tại max_d (chỉ qua các lớp đã có)
    tot_at_max = sum(L["thickness_m"] * GAMMA_BY_SYMBOL.get(L["symbol"], 17.5)
                     for L in layers)
    u_at_max = gamma_w_local * max(0.0, max_d - gwl_d_tmp)
    eff_at_max = tot_at_max - u_at_max
    # Phần thiếu để đạt target
    if eff_at_max >= target_eff:
        max_d_extended = max_d * 1.05  # đã đạt — extend ít
    else:
        extra = (target_eff - eff_at_max) / g_sub_last
        max_d_extended = (max_d + extra * 1.3) + 2.0  # +1.3× để có lề
    max_d_extended = max(max_d_extended, max_d + 5)
    depths = np.linspace(0, max_d_extended, 80 if compact else 120)
    sigma_v0 = []
    sigma_vf = []
    sigma_10 = []

    def gamma_at(d):
        for L in layers:
            if L["depth_top_m"] <= d <= L["depth_bot_m"]:
                return GAMMA_BY_SYMBOL.get(L["symbol"], 17.5)
        # Sâu hơn lớp cuối → giữ γ của lớp cuối (giả định lớp này vô hạn)
        if d > max_d:
            return last_gamma
        return 17.5

    # ─── Độ sâu MNN từ cao độ MNN ───
    if gwl_elev_m is not None:
        gwl_depth = max(0.0, elev - gwl_elev_m)  # = elev_TN − elev_MNN
    else:
        gwl_depth = float("inf")  # không có MNN → không có áp lực nước

    def pore_pressure(d: float) -> float:
        """u(z) = γ_w × max(0, z - z_gwl). Đơn vị kPa."""
        return gamma_w * max(0.0, d - gwl_depth)

    cumstress = 0.0  # ứng suất TỔNG σ_v0
    last_d = 0.0
    u_list = []
    sigma_vf_boussinesq = []  # §72 Task S — phương án Boussinesq
    # Default tip ở giữa lớp bùn nếu không truyền vào (đại diện vẽ cho 6 HK)
    if cdm_tip_depth_m is None:
        # Mặc định: tip ở 1/2 chiều sâu HK (ước lượng giữa khối gia cố)
        tip_d = max_d * 0.5
    else:
        tip_d = float(cdm_tip_depth_m)
    for d in depths:
        dd = d - last_d
        cumstress += gamma_at(d) * dd
        u = pore_pressure(d)
        sigma_eff = cumstress - u                # σ'v0 = σ_v0 − u
        sigma_v0.append(sigma_eff)
        sigma_vf.append(sigma_eff + q_cdm_kPa)
        sigma_10.append(0.1 * sigma_eff)
        u_list.append(u)
        # §72 Task S — Boussinesq decay dưới mũi cọc
        z_below = max(0.0, d - tip_d)
        dsigma_b = compute_dsigma_boussinesq(z_below, q_cdm_kPa, B_eq_m,
                                              method="2:1")
        sigma_vf_boussinesq.append(sigma_eff + dsigma_b)
        last_d = d

    # Y-axis = CAO ĐỘ tuyệt đối (so với mốc Quốc gia)
    elev_y = [elev - d for d in depths]

    # Tính ứng suất hữu hiệu tại độ sâu cụ thể (để annotate markers 2m)
    def stress_at_depth(d_target: float) -> tuple[float, float, float, float]:
        """Trả về (σ'v0, σ'vf, 10%·σ'v0, u) tại độ sâu d_target."""
        cs = 0.0; last = 0.0
        for L in layers:
            top, bot = L["depth_top_m"], L["depth_bot_m"]
            g = GAMMA_BY_SYMBOL.get(L["symbol"], 17.5)
            if d_target <= top:
                break
            if d_target >= bot:
                cs += g * (bot - top)
                last = bot
            else:
                cs += g * (d_target - max(top, last))
                last = d_target
                break
        u = pore_pressure(d_target)
        sig_eff = cs - u
        return sig_eff, sig_eff + q_cdm_kPa, 0.1 * sig_eff, u

    # Sample points cách nhau 2m để đặt markers + value labels
    sample_depths = [0.0] + list(np.arange(2.0, max_d + 0.01, 2.0))
    # Ensure max_d included
    if sample_depths[-1] < max_d - 0.5:
        sample_depths.append(max_d)
    sv0_2m = [stress_at_depth(d)[0] for d in sample_depths]
    svf_2m = [stress_at_depth(d)[1] for d in sample_depths]
    s10_2m = [stress_at_depth(d)[2] for d in sample_depths]
    sample_elevs = [elev - d for d in sample_depths]

    fig = go.Figure()
    # 1) σ'v0 — line theo cao độ
    fig.add_trace(go.Scatter(
        x=sigma_v0, y=elev_y, mode="lines",
        line=dict(color=PRIM_COLOR, width=2.2),
        name="σ'v0 (tự trọng)", showlegend=not compact,
    ))
    # Markers + value labels mỗi 2m
    fig.add_trace(go.Scatter(
        x=sv0_2m, y=sample_elevs,
        mode="markers+text",
        marker=dict(size=7, color=PRIM_COLOR, symbol="circle",
                    line=dict(color="white", width=1)),
        text=[f"{v:.0f}" for v in sv0_2m],
        textposition="middle left",
        textfont=dict(size=9, color=PRIM_COLOR),
        showlegend=False, hoverinfo="skip",
    ))

    # 2) σ'vf
    fig.add_trace(go.Scatter(
        x=sigma_vf, y=elev_y, mode="lines",
        line=dict(color=FAIL_COLOR, width=2, dash="dash"),
        name="σ'vf = σ'v0 + q_CDM", showlegend=not compact,
    ))
    fig.add_trace(go.Scatter(
        x=svf_2m, y=sample_elevs,
        mode="markers+text",
        marker=dict(size=7, color=FAIL_COLOR, symbol="diamond",
                    line=dict(color="white", width=1)),
        text=[f"{v:.0f}" for v in svf_2m],
        textposition="middle right",
        textfont=dict(size=9, color=FAIL_COLOR),
        showlegend=False, hoverinfo="skip",
    ))

    # 2b) §72 Task S — σ'vf Boussinesq (giảm theo độ sâu dưới mũi cọc)
    if show_boussinesq:
        elev_tip = elev - tip_d
        fig.add_trace(go.Scatter(
            x=sigma_vf_boussinesq, y=elev_y, mode="lines",
            line=dict(color="#00897B", width=2.2, dash="dot"),
            name=f"σ'vf Boussinesq (B={B_eq_m:.1f}m)",
            showlegend=not compact,
        ))
        # Marker mũi cọc
        fig.add_hline(
            y=elev_tip,
            line=dict(color="#00695C", width=1.2, dash="dashdot"),
            annotation_text=f"Mũi CDM (z={elev_tip:+.1f}m)",
            annotation_position="top left",
            annotation_font=dict(size=9, color="#00695C"),
        )
        # Markers Boussinesq tại sample depths dưới tip
        boussinesq_2m = []
        for ds_dep in sample_depths:
            if ds_dep < tip_d:
                boussinesq_2m.append(None)
            else:
                sv0_at = stress_at_depth(ds_dep)[0]
                dsig_b = compute_dsigma_boussinesq(
                    ds_dep - tip_d, q_cdm_kPa, B_eq_m, method="2:1")
                boussinesq_2m.append(sv0_at + dsig_b)
        fig.add_trace(go.Scatter(
            x=boussinesq_2m, y=sample_elevs,
            mode="markers+text",
            marker=dict(size=7, color="#00897B", symbol="triangle-down",
                        line=dict(color="white", width=1)),
            text=[f"{v:.0f}" if v is not None else "" for v in boussinesq_2m],
            textposition="middle right",
            textfont=dict(size=9, color="#00897B"),
            showlegend=False, hoverinfo="skip",
        ))

    # 3) 10% × σ'v0
    fig.add_trace(go.Scatter(
        x=sigma_10, y=elev_y, mode="lines",
        line=dict(color=WARN_COLOR, width=1.5, dash="dot"),
        name="10% × σ'v0 (ngưỡng dừng)", showlegend=not compact,
    ))
    fig.add_trace(go.Scatter(
        x=s10_2m, y=sample_elevs,
        mode="markers+text",
        marker=dict(size=5, color=WARN_COLOR, symbol="square",
                    line=dict(color="white", width=0.5)),
        text=[f"{v:.0f}" for v in s10_2m],
        textposition="bottom right",
        textfont=dict(size=8, color=WARN_COLOR),
        showlegend=False, hoverinfo="skip",
    ))
    # 4) ĐƯỜNG TẢI CDM Δσ — đường dọc tại x=q_cdm
    fig.add_vline(
        x=q_cdm_kPa,
        line=dict(color="#6A1B9A", width=2, dash="dashdot"),
        annotation_text=f"Δσ_CDM = {q_cdm_kPa:.1f} kPa",
        annotation_position="top",
        annotation_font=dict(size=10, color="#6A1B9A"),
    )

    # 5) ĐƯỜNG MNN — đường ngang tại cao độ MNN
    if gwl_elev_m is not None and gwl_depth >= 0 and gwl_depth <= max_d:
        fig.add_hline(
            y=gwl_elev_m,
            line=dict(color="#0277BD", width=1.5, dash="dot"),
            annotation_text=(f"MNN +{gwl_elev_m:.2f}m "
                              f"(sâu {gwl_depth:.2f}m)"),
            annotation_position="top right",
            annotation_font=dict(size=10, color="#0277BD"),
        )

    # Điểm giao σ'v0 = 10 × q_cdm → đáy vùng ảnh hưởng lún (1D)
    target_sigma = 10.0 * q_cdm_kPa
    d_stop = None
    for i in range(len(sigma_v0) - 1):
        if sigma_v0[i] <= target_sigma <= sigma_v0[i + 1]:
            frac = ((target_sigma - sigma_v0[i])
                    / max(sigma_v0[i + 1] - sigma_v0[i], 1e-6))
            d_stop = depths[i] + frac * (depths[i + 1] - depths[i])
            break

    # §72 Task S — d_stop Boussinesq: tại đó Δσ_B ≤ 10%·σ'v0
    d_stop_b = None
    if show_boussinesq:
        for i in range(len(depths)):
            if depths[i] <= tip_d:
                continue
            dsig_b = sigma_vf_boussinesq[i] - sigma_v0[i]
            if sigma_v0[i] > 0 and (dsig_b / sigma_v0[i]) < 0.10:
                d_stop_b = depths[i]
                break
    if d_stop is not None:
        elev_stop = elev - d_stop
        # ─── Vùng ảnh hưởng lún — tô shade từ mặt đất → đáy ảnh hưởng ───
        fig.add_shape(
            type="rect", xref="paper", yref="y",
            x0=0, x1=1,
            y0=elev_stop, y1=elev,
            fillcolor="rgba(46, 125, 50, 0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            layer="below",
        )
        # ─── Đường đáy ảnh hưởng ───
        fig.add_hline(
            y=elev_stop,
            line=dict(color="#2E7D32", width=2, dash="dash"),
            annotation_text=(f"<b>Đáy vùng ảnh hưởng lún (10%)</b><br>"
                              f"z = {elev_stop:+.2f} m  ·  sâu {d_stop:.1f} m"),
            annotation_position="bottom right",
            annotation_font=dict(size=10, color="#2E7D32"),
        )
        fig.add_trace(go.Scatter(
            x=[q_cdm_kPa], y=[elev_stop],
            mode="markers+text",
            marker=dict(size=16, color="#2E7D32", symbol="star",
                        line=dict(color="black", width=1.5)),
            text=[f"z={elev_stop:+.2f}m"],
            textposition="middle right",
            textfont=dict(size=10, color="#2E7D32"),
            showlegend=False,
        ))
        # Label phía trên vùng ảnh hưởng
        fig.add_annotation(
            x=q_cdm_kPa * 0.05, y=(elev + elev_stop) / 2,
            text="<b>VÙNG ẢNH HƯỞNG<br>LÚN (10%)</b>",
            showarrow=False,
            font=dict(size=10, color="#2E7D32"),
            xanchor="left",
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor="#2E7D32", borderwidth=1, borderpad=4,
        )

    # Vùng tô màu theo lớp đất phía bên phải — y theo cao độ
    sigma_max = max(max(sigma_vf), max(sigma_v0)) * 1.15
    for idx, L in enumerate(layers):
        color = LAYER_COLORS.get(L["symbol"], "#BDBDBD")
        z_top = elev - L["depth_top_m"]
        z_bot = elev - L["depth_bot_m"]
        # Lớp cuối: extend xuống dưới hết chart (mặc định vô tận)
        is_last = (idx == len(layers) - 1)
        if is_last:
            z_bot = elev - max(depths)  # tới đáy chart
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=sigma_max * 0.82, x1=sigma_max,
            y0=z_bot, y1=z_top,
            fillcolor=color, opacity=0.4,
            line=dict(color="black", width=0.5), layer="below",
        )
        # Label ở giữa phần CÓ DỮ LIỆU (không trải toàn lớp infinity)
        label_z_bot = elev - L["depth_bot_m"]
        label_text = f"<b>{L['symbol']}</b><br>{L['thickness_m']:.1f}m"
        if is_last:
            label_text += "<br><i>(∞)</i>"
        fig.add_annotation(
            x=sigma_max * 0.91, y=(z_top + label_z_bot) / 2,
            text=label_text,
            showarrow=False, font=dict(size=9),
        )
    # Đường ranh giới đáy HK (chấm) — phân biệt với phần vô hạn
    fig.add_hline(
        y=elev - max_d,
        line=dict(color="black", width=0.8, dash="dot"),
        annotation_text=f"Đáy HK ({max_d:.1f}m)",
        annotation_position="top left",
        annotation_font=dict(size=8, color="#666"),
    )

    # Annotate giá trị cuối σ'v0
    fig.add_annotation(
        x=sigma_v0[-1], y=elev_y[-1],
        text=f"σ'v0={sigma_v0[-1]:.0f}",
        showarrow=True, arrowhead=2,
        font=dict(size=9, color=PRIM_COLOR),
        ax=20, ay=-15,
    )
    # Annotate giá trị cuối σ'vf
    fig.add_annotation(
        x=sigma_vf[-1], y=elev_y[-1],
        text=f"σ'vf={sigma_vf[-1]:.0f}",
        showarrow=True, arrowhead=2,
        font=dict(size=9, color=FAIL_COLOR),
        ax=20, ay=15,
    )

    # §72 Task S — So sánh d_stop 1D vs Boussinesq
    if show_boussinesq:
        compare_lines = []
        if d_stop is not None:
            compare_lines.append(f"d_stop (1D) = {d_stop:.1f} m")
        if d_stop_b is not None:
            compare_lines.append(f"d_stop (Bouss.) = {d_stop_b:.1f} m")
            if d_stop is not None and d_stop_b is not None:
                delta = d_stop - d_stop_b
                compare_lines.append(f"Giảm {delta:+.1f} m ({delta / max(d_stop, 1) * 100:+.0f}%)")
        if compare_lines:
            fig.add_annotation(
                xref="paper", yref="paper",
                x=0.02, y=0.02,
                text="<br>".join(compare_lines),
                showarrow=False,
                font=dict(size=9, color="#00695C"),
                bgcolor="rgba(224,242,241,0.92)",
                bordercolor="#00897B", borderwidth=1, borderpad=4,
                xanchor="left", yanchor="bottom",
            )

    # Header với info bổ sung
    h_soft = bh_data.get("H_soft_m") or 0
    if compact:
        title_text = (f"<b>HK {bh_name}</b> · TN +{elev:.2f}m · "
                       f"q={q_cdm_kPa:.1f} kPa")
        height = 380
    else:
        title_text = (f"<b>Ứng suất + ngưỡng 10% — HK {bh_name}</b> · "
                       f"q_CDM = {q_cdm_kPa:.1f} kPa")
        height = 500

    fig.update_layout(
        title=dict(text=title_text, font=dict(size=12, color="#111827")),
        xaxis=dict(title="Ứng suất (kPa)", showgrid=True,
                    range=[0, sigma_max]),
        yaxis=dict(title="Cao độ (m)", showgrid=True,
                    range=[elev - max(depths) - 1, elev + 1]),
        height=height, font=FONT_BASE, plot_bgcolor="white",
        showlegend=not compact,
        legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
        margin=dict(l=50, r=20, t=50, b=40 if compact else 80),
    )
    return fig


# ════════ 5. Chỉ tiêu cơ lý per HK (verify SQLite/JSON) ════════
def layer_params_chart(
    bh_name: str,
    lab_rows: list[dict],
) -> go.Figure:
    """Hiển thị toàn bộ chỉ tiêu lab per mẫu, không bỏ sót.

    lab_rows: [{depth_from_m, depth_to_m, symbol_tcvn, w_pct, gamma_kNm3,
                 e0, wL_pct, wP_pct, Ip, Cc, Cu_UU_kPa, PC_kPa, ...}, ...]
    """
    if not lab_rows:
        fig = go.Figure()
        fig.add_annotation(text=f"HK {bh_name}: chưa có thí nghiệm phòng",
                            xref="paper", yref="paper", x=0.5, y=0.5,
                            showarrow=False, font=dict(size=14))
        return fig

    depths = [(r["depth_from_m"] + r["depth_to_m"]) / 2 for r in lab_rows]
    params = [
        ("w (%)", "w_pct", "#1565C0"),
        ("γ (kN/m³)", "gamma_kNm3", "#5D4037"),
        ("e₀", "e0", "#D32F2F"),
        ("Cc", "Cc", "#2E7D32"),
        ("Cu_UU (kPa)", "Cu_UU_kPa", "#6A1B9A"),
        ("PC (kPa)", "PC_kPa", "#F57C00"),
    ]

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=1, cols=len(params), shared_yaxes=True,
        horizontal_spacing=0.03,
        subplot_titles=[f"<b>{p[0]}</b>" for p in params],
    )
    for col_idx, (label, key, color) in enumerate(params, start=1):
        vals = [r.get(key) for r in lab_rows]
        # Lọc None để vẽ nhưng giữ text "—"
        x = [v if v is not None else None for v in vals]
        text = [f"{v:.2f}" if v is not None else "—" for v in vals]
        fig.add_trace(go.Scatter(
            x=x, y=depths, mode="lines+markers+text",
            marker=dict(size=10, color=color),
            line=dict(color=color, width=1.5),
            text=text, textposition="middle right",
            textfont=dict(size=10),
            name=label, showlegend=False,
        ), row=1, col=col_idx)
        # Highlight e₀ > 1 với vạch dọc
        if key == "e0":
            fig.add_vline(x=1.0, line=dict(color=FAIL_COLOR, dash="dash"),
                          row=1, col=col_idx)
            fig.add_annotation(
                x=1.05, y=depths[0] if depths else 0,
                text="<b>e₀=1<br>(ranh giới<br>sét yếu)</b>",
                xref=f"x{col_idx}", yref=f"y{col_idx}",
                showarrow=False, font=dict(size=9, color=FAIL_COLOR),
            )

    fig.update_yaxes(autorange="reversed", title_text="Độ sâu (m)",
                      row=1, col=1)
    fig.update_layout(
        title=dict(
            text=f"<b>Chỉ tiêu cơ lý HK {bh_name} — verify từ SQLite/JSON</b>",
            font=FONT_TITLE,
        ),
        height=620, font=FONT_BASE, plot_bgcolor="white",
    )
    return fig


# ════════ 6b. Panel tổng hợp 1 HK — layers + SPT + e₀ + GWL ════════
def bh_full_panel(
    bh: dict,
    layers: list[dict],
    spt: list[dict],
    lab_rows: list[dict] | None = None,
    gwl_depth_m: float | None = None,
    gwl_elev_m: float | None = None,
) -> go.Figure:
    """Biểu đồ tổng hợp 1 HK: cột địa tầng + SPT bar + e₀ overlay + GWL.

    Cấu trúc:
      x1 (trái) = cột địa tầng tô màu + ký hiệu + chiều dày
      x2 (trên) = chỉ số SPT N (bar ngang)
      x3 (trên cao hơn) = hệ số rỗng e₀ (marker)
      y = độ sâu (m, autorange reversed)
      Đường ngang xanh = mực nước ngầm

    Args:
        bh: {name, elevation_m, depth_m, H_soft_m}
        layers: [{symbol, depth_top_m, depth_bot_m, thickness_m, description}, ...]
        spt: [{depth_m, N}, ...]
        lab_rows: [{depth_from_m, depth_to_m, symbol_tcvn, e0, ...}, ...]
        gwl_depth_m: độ sâu MNN (m từ mặt đất). None = không vẽ.
    """
    from plotly.subplots import make_subplots
    elev = bh.get("elevation_m") or 0
    name = bh.get("name", "BH")

    # max depth — fallback từ layers nếu không có depth_m
    max_d = bh.get("depth_m") or (layers[-1]["depth_bot_m"] if layers else 30)

    # Lấy e₀ TB per layer từ lab
    e0_by_layer = {}
    if lab_rows:
        for L in layers:
            sym = L["symbol"]
            vals = [r["e0"] for r in lab_rows
                    if r.get("symbol_tcvn") == sym and r.get("e0") is not None]
            if vals:
                e0_by_layer[id(L)] = sum(vals) / len(vals)

    # 3 subplot ngang share Y axis: [địa tầng | SPT | e₀]
    fig = make_subplots(
        rows=1, cols=3, shared_yaxes=True,
        column_widths=[0.45, 0.30, 0.25],
        horizontal_spacing=0.02,
        subplot_titles=[
            "<b>Địa tầng</b>",
            "<b>SPT N</b>",
            "<b>e₀</b>",
        ],
    )

    # ─── Cột 1: Địa tầng ───
    for L in layers:
        sym = L["symbol"]
        color = LAYER_COLORS.get(sym, "#BDBDBD")
        fig.add_trace(go.Bar(
            x=[1], y=[L["thickness_m"]], base=L["depth_top_m"],
            marker=dict(color=color, line=dict(color="black", width=0.8)),
            orientation="v",
            text=(f"<b>({sym})</b> {L['thickness_m']:.1f}m<br>"
                   f"{L['depth_top_m']:.1f}-{L['depth_bot_m']:.1f}m"),
            textposition="inside",
            textfont=dict(size=10, color="black"),
            hovertext=L.get("description", ""),
            showlegend=False,
        ), row=1, col=1)

    # Cao độ đỉnh/đáy lớp (annotation bên trái)
    for L in layers:
        z_top = elev - L["depth_top_m"]
        z_bot = elev - L["depth_bot_m"]
        # Cao độ đỉnh — chỉ vẽ ô đầu (depth=0) hoặc nếu khác layer trên
        if L is layers[0]:
            fig.add_annotation(
                x=-0.5, y=L["depth_top_m"], xref="x1", yref="y",
                text=f"+{z_top:.2f}", showarrow=False,
                font=dict(size=9, color="#5D4037"),
                xanchor="right",
            )
        # Cao độ đáy lớp
        fig.add_annotation(
            x=-0.5, y=L["depth_bot_m"], xref="x1", yref="y",
            text=f"{z_bot:+.2f}", showarrow=False,
            font=dict(size=9, color="#5D4037"),
            xanchor="right",
        )

    # ─── Cột 2: SPT N ───
    if spt:
        spt_depths = [s["depth_m"] for s in spt]
        spt_N = [s["N"] for s in spt]
        fig.add_trace(go.Bar(
            x=spt_N, y=spt_depths,
            orientation="h",
            marker=dict(color=PRIM_COLOR,
                        line=dict(color="black", width=0.5)),
            text=[str(n) for n in spt_N],
            textposition="outside",
            textfont=dict(size=9),
            showlegend=False,
            width=1.2,
        ), row=1, col=2)

    # ─── Cột 3: e₀ markers ───
    if e0_by_layer:
        e_x = []; e_y = []; e_t = []; e_col = []
        for L in layers:
            ek = id(L)
            if ek in e0_by_layer:
                e0 = e0_by_layer[ek]
                e_x.append(e0)
                e_y.append((L["depth_top_m"] + L["depth_bot_m"]) / 2)
                e_t.append(f"{e0:.2f}")
                e_col.append(FAIL_COLOR if e0 > 1.0 else OK_COLOR)
        if e_x:
            fig.add_trace(go.Scatter(
                x=e_x, y=e_y, mode="markers+text",
                marker=dict(size=14, color=e_col, symbol="diamond",
                            line=dict(color="black", width=1)),
                text=e_t, textposition="middle right",
                textfont=dict(size=10, color="black"),
                showlegend=False,
            ), row=1, col=3)
            # Vạch dọc e₀=1
            fig.add_vline(x=1.0, line=dict(color=FAIL_COLOR, dash="dash",
                                            width=1.5),
                          row=1, col=3)

    # ─── MNN — đường ngang (ưu tiên gwl_elev_m: cao độ tuyệt đối) ───
    if gwl_elev_m is not None:
        # Quy đổi cao độ → độ sâu theo cao độ mặt đất HK này
        gwl_depth_m = (elev or 0) - gwl_elev_m

    if gwl_depth_m is not None and 0 <= gwl_depth_m <= max_d:
        # Label hiển thị cao độ tuyệt đối nếu được cung cấp, ngược lại độ sâu
        if gwl_elev_m is not None:
            ann_text = f"MNN +{gwl_elev_m:.2f}m (sâu {gwl_depth_m:.2f}m)"
        else:
            ann_text = f"MNN sâu {gwl_depth_m:.1f}m"
        # vẽ ở cả 3 cột
        for col in (1, 2, 3):
            fig.add_hline(
                y=gwl_depth_m,
                line=dict(color="#0277BD", width=1.5, dash="dot"),
                row=1, col=col,
                annotation_text=(ann_text if col == 1 else None),
                annotation_position="top right",
                annotation_font=dict(size=9, color="#0277BD"),
            )

    # Layout
    fig.update_yaxes(autorange="reversed", title_text="Độ sâu (m)",
                      row=1, col=1, range=[max_d + 1, -2])
    fig.update_yaxes(range=[max_d + 1, -2], row=1, col=2)
    fig.update_yaxes(range=[max_d + 1, -2], row=1, col=3)
    fig.update_xaxes(showticklabels=False, range=[-1.5, 1.5], row=1, col=1)
    fig.update_xaxes(title_text="N", row=1, col=2)
    fig.update_xaxes(title_text="e₀", range=[0, 3], row=1, col=3)

    # Title
    h_soft = bh.get("H_soft_m") or 0
    fig.update_layout(
        title=dict(
            text=(f"<b>HK {name}</b>  ·  Cao độ TN: +{elev:.2f}m  "
                   f"·  Tổng sâu: {max_d:.1f}m  ·  H_soft: {h_soft:.1f}m"),
            font=dict(size=12, color="#111827"),
            x=0, xanchor="left",
        ),
        height=520, font=FONT_BASE, plot_bgcolor="white",
        margin=dict(l=60, r=20, t=70, b=40),
    )
    return fig


# ════════ 7. Cảnh báo cọc thả nổi ════════
def floating_pile_warning_table(
    boreholes: list[dict],
    lc_data: list[dict],
    layers_by_bh: dict[str, list[dict]],
    dS_cm: float = 30.0,
    threshold: float = 0.8,
) -> list[dict]:
    """Trả về list dict cảnh báo cho HK có p/H_soft < threshold (cọc thả nổi nghiêm trọng)."""
    warns = []
    lc_by_bh = {r["bh_name"]: r for r in lc_data if r["delta_S_cm"] == dS_cm}
    for b in boreholes:
        r = lc_by_bh.get(b["name"])
        if not r or not r.get("tip_depth_m"):
            continue
        H_soft = b.get("H_soft_m") or 0
        if H_soft <= 0:
            continue
        layers = layers_by_bh.get(b["name"], [])
        clay_top = 0
        for L in layers:
            if L["symbol"] != "F":
                clay_top = L["depth_top_m"]; break
        p_pen = r["tip_depth_m"] - clay_top
        ratio = p_pen / H_soft if H_soft > 0 else 0
        if ratio < threshold:
            warns.append({
                "HK": b["name"],
                "H_soft (m)": round(H_soft, 2),
                "p (xuyên vào bùn) (m)": round(p_pen, 2),
                "p / H_soft": round(ratio, 3),
                "Lc (m)": r.get("Lc_m"),
                "S_total (cm)": round(r.get("S_total_cm") or 0, 2),
                "Đạt ΔS": "Có" if r.get("ok") else "Không",
                "Cảnh báo": "Cọc thả nổi nghiêm trọng (p/H_soft < 0.8)",
            })
    return warns
