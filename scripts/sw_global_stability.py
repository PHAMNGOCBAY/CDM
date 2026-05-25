"""
sw_global_stability.py — Ổn định tổng thể tường cừ SW + CDM (3 kiểm tra).

Scope (CLAUDE.md §20 + 49-ke-sw-global-stability.md):
  1. Trượt cung tròn tổng thể qua dưới chân cừ — Bishop / Spencer LE
  2. Lật quanh chân cừ — ΣM
  3. Xoay nhổ chân cừ — Free Earth Support, Mp ≥ Ma

Quy ước Front/Back (§20):
  Front = TRÁI = đắp + tải → Active (Ka) đẩy cừ về Back
  Back  = PHẢI = đào / nước hở → Passive (Kp) kháng dưới đáy đào

Composite CDM: TCVN 9403:2012 Phụ lục C — area-weighted (φ, c, γ).

Tích phân với wall_internal_force.py (cùng dataclass EarthLayer, WallGeometry).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Import dataclass từ wall_internal_force (đã có)
# ─────────────────────────────────────────────────────────────────────────────


try:
    from wall_internal_force import (
        WallGeometry, EarthLayer, PileProps,
        _Ka_rankine, _Kp_rankine, _eff_gamma, _layer_at_elev,
    )
except ImportError:
    # Fallback minimal definitions
    @dataclass
    class EarthLayer:
        tip_elev: float
        gamma: float
        gamma_sub: float
        phi: float
        c: float = 0.0

    @dataclass
    class WallGeometry:
        top_elev: float
        pile_length: float
        soil_level_front: float
        soil_level_back: float
        water_elev_front: float
        water_elev_back: float
        surcharge_front: float = 0.0
        gamma_w: float = 9.81

        @property
        def bot_elev(self) -> float:
            return self.top_elev - self.pile_length

    @dataclass
    class PileProps:
        name: str
        D_m: float
        EI_kNm2: float
        Mcr_kNm: float = 0.0
        Atd_m2: float = 0.0

    def _Ka_rankine(phi_deg: float) -> float:
        return math.tan(math.radians(45.0 - phi_deg / 2.0)) ** 2

    def _Kp_rankine(phi_deg: float) -> float:
        return math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2

    def _eff_gamma(lay, e_top, e_bot, water):
        dz = e_top - e_bot
        if dz <= 1e-9: return lay.gamma
        if water >= e_top: return lay.gamma
        if water <= e_bot: return lay.gamma_sub
        return (lay.gamma * (e_top - water) + lay.gamma_sub * (water - e_bot)) / dz

    def _layer_at_elev(elev, top, layers):
        cur = top
        for lay in layers:
            if lay.tip_elev <= elev <= cur:
                return lay
            cur = lay.tip_elev
        return layers[-1] if layers else None


# ─────────────────────────────────────────────────────────────────────────────
# Composite CDM (TCVN 9403:2012 Phụ lục C)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CDMBlock:
    """Khối CDM gia cố phía Front (đất+xi măng).

    Args:
        top_elev: cao độ đỉnh khối CDM (m, dương = cao)
        bot_elev: cao độ đáy khối CDM (m, < top_elev)
        area_ratio_a: tỷ lệ thay thế Ac/A_đơn_vị (0.15–0.30 điển hình)
        c_col_kPa: lực dính trụ CDM = q_u_field / 2 (50–100 kPa)
        phi_col_deg: góc ma sát trụ CDM (25–35°)
        gamma_col_kNm3: dung trọng trụ (18–20 kN/m³)
    """
    top_elev: float
    bot_elev: float
    area_ratio_a: float = 0.20
    c_col_kPa: float = 75.0
    phi_col_deg: float = 30.0
    gamma_col_kNm3: float = 19.0
    gamma_col_sub_kNm3: float = 9.0  # γ' đẩy nổi

    @property
    def thickness(self) -> float:
        return self.top_elev - self.bot_elev

    def composite(self, soil: EarthLayer) -> EarthLayer:
        """Trả EarthLayer composite tại vùng CDM theo TCVN 9403 Phụ lục C."""
        a = self.area_ratio_a
        c_comp = (1 - a) * soil.c + a * self.c_col_kPa
        tan_phi = ((1 - a) * math.tan(math.radians(soil.phi))
                  + a * math.tan(math.radians(self.phi_col_deg)))
        phi_comp = math.degrees(math.atan(tan_phi))
        gamma_comp = (1 - a) * soil.gamma + a * self.gamma_col_kNm3
        gamma_sub_comp = (1 - a) * soil.gamma_sub + a * self.gamma_col_sub_kNm3
        return EarthLayer(
            tip_elev=self.bot_elev,
            gamma=gamma_comp, gamma_sub=gamma_sub_comp,
            phi=phi_comp, c=c_comp,
        )

    def su_composite(self, su_soil_kPa: float) -> float:
        """su tổng hợp dùng cho undrained analysis (Bishop với su)."""
        a = self.area_ratio_a
        return (1 - a) * su_soil_kPa + a * self.c_col_kPa


# ─────────────────────────────────────────────────────────────────────────────
# Kết quả tổng hợp
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SWStabilityResult:
    """Kết quả 3 kiểm tra ổn định tổng thể."""
    # Trượt cung tròn
    Fs_global_slip: float = 0.0
    slip_xc: float = 0.0
    slip_yc: float = 0.0
    slip_R: float = 0.0
    slip_method: str = "bishop"
    # Lật quanh chân cừ
    Fs_overturning: float = 0.0
    M_giu_kNm: float = 0.0
    M_lat_kNm: float = 0.0
    # Toe kick-out
    Fs_toe_kickout: float = 0.0
    Ma_kNm: float = 0.0
    Mp_kNm: float = 0.0
    # Tổng quát
    warnings: list = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        def _ok(v, lim):
            return v is not None and v >= lim
        return (
            _ok(self.Fs_global_slip, 1.30) and
            _ok(self.Fs_overturning, 2.00) and
            _ok(self.Fs_toe_kickout, 1.50)
        )

    def summary(self) -> str:
        rows = [
            ("Trượt cung tròn",   self.Fs_global_slip, 1.30),
            ("Lật quanh chân cừ", self.Fs_overturning, 2.00),
            ("Xoay nhổ chân cừ",  self.Fs_toe_kickout, 1.50),
        ]
        lines = ["", "Kiểm tra ổn định tổng thể tường SW + CDM:"]
        lines.append(f"{'Mục':<22} {'Fs':>8} {'Fs_min':>8} {'Trạng thái':>12}")
        lines.append("─" * 56)
        for name, fs, fs_min in rows:
            if fs is None:
                status = "Không tính được"
                lines.append(f"{name:<22} {'N/A':>8} {fs_min:>8.2f} {status:>12}")
            else:
                status = "Đạt" if fs >= fs_min else "KHÔNG ĐẠT"
                lines.append(f"{name:<22} {fs:>8.2f} {fs_min:>8.2f} {status:>12}")
        if self.warnings:
            lines.append("")
            lines.append("Cảnh báo:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — áp lực Active / Passive tích phân quanh chân cừ
# ─────────────────────────────────────────────────────────────────────────────


def _integrate_active_back_to_tip(
    geom: WallGeometry,
    front_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    n_slices: int = 200,
) -> tuple[float, float]:
    """Tích phân Active phía Front (đắp) từ top_elev xuống pile_tip.

    Returns (P_a [kN/m], z_app [m]) — lực ngang tổng và cao độ điểm đặt
    (đo so với pile_tip).
    """
    # Build all_front (fill + CDM composite + soil)
    all_front = []
    if fill is not None and geom.top_elev > geom.soil_level_front:
        all_front.append(EarthLayer(geom.soil_level_front, fill.gamma,
                                     fill.gamma_sub, fill.phi, fill.c))
    if cdm is not None:
        # Tìm lớp đất gốc tại tâm CDM để composite
        mid_cdm = (cdm.top_elev + cdm.bot_elev) / 2
        soil_at_cdm = _layer_at_elev(mid_cdm, geom.soil_level_front, front_layers)
        if soil_at_cdm:
            comp_lay = cdm.composite(soil_at_cdm)
            # Add CDM block at correct position
            all_front.append(EarthLayer(cdm.bot_elev, comp_lay.gamma,
                                         comp_lay.gamma_sub, comp_lay.phi, comp_lay.c))
    all_front.extend(front_layers)

    # Tích phân từ top xuống pile_tip
    pile_tip = geom.bot_elev
    dz_total = geom.top_elev - pile_tip
    dz = dz_total / n_slices

    sv = geom.surcharge_front
    P_total = 0.0
    M_total = 0.0
    prev_e = geom.top_elev

    for i in range(n_slices):
        e_top = prev_e
        e_bot = prev_e - dz
        e_mid = (e_top + e_bot) / 2
        lay = _layer_at_elev(e_mid, geom.top_elev, all_front)
        if lay is None:
            prev_e = e_bot
            continue
        gam_eff = _eff_gamma(lay, e_top, e_bot, geom.water_elev_front)
        sv += gam_eff * dz
        Ka = _Ka_rankine(lay.phi)
        sh = max(0.0, Ka * sv - 2.0 * lay.c * math.sqrt(max(Ka, 0.0)))
        # Áp lực nước
        pw = max(0.0, (geom.water_elev_front - e_mid) * geom.gamma_w)
        force_slice = (sh + pw) * dz
        z_lever = e_mid - pile_tip  # tay đòn so với chân cừ (dương = phía trên)
        P_total += force_slice
        M_total += force_slice * z_lever
        prev_e = e_bot

    z_app = M_total / P_total if abs(P_total) > 1e-9 else 0.0
    return P_total, z_app


def _integrate_passive_back_below_dredge(
    geom: WallGeometry,
    back_layers: list,
    cdm: Optional[CDMBlock] = None,
    n_slices: int = 100,
) -> tuple[float, float]:
    """Tích phân Passive phía Back từ soil_level_back xuống pile_tip.

    Returns (P_p [kN/m], z_app [m]) so với pile_tip.
    """
    pile_tip = geom.bot_elev
    dredge = geom.soil_level_back
    if dredge <= pile_tip:
        return 0.0, 0.0

    # Layers phía Back có thể bị CDM composite ở vùng trùng CDM zone
    all_back = list(back_layers)

    dz_total = dredge - pile_tip
    dz = dz_total / n_slices
    sv = 0.0
    P_total = 0.0
    M_total = 0.0
    prev_e = dredge

    for i in range(n_slices):
        e_top = prev_e
        e_bot = prev_e - dz
        e_mid = (e_top + e_bot) / 2
        lay = _layer_at_elev(e_mid, dredge, all_back)
        # CDM enhancement nếu vùng nằm trong cdm zone (composite phía Back)
        if cdm is not None and cdm.bot_elev <= e_mid <= cdm.top_elev:
            soil_lay = lay or all_back[0]
            comp_lay = cdm.composite(soil_lay)
            lay = comp_lay
        if lay is None:
            prev_e = e_bot
            continue
        gam_eff = _eff_gamma(lay, e_top, e_bot, geom.water_elev_back)
        sv += gam_eff * dz
        Kp = _Kp_rankine(lay.phi)
        sh = Kp * sv + 2.0 * lay.c * math.sqrt(max(Kp, 0.0))
        # Áp lực nước
        pw = max(0.0, (geom.water_elev_back - e_mid) * geom.gamma_w)
        force_slice = (sh + pw) * dz
        z_lever = e_mid - pile_tip
        P_total += force_slice
        M_total += force_slice * z_lever
        prev_e = e_bot

    z_app = M_total / P_total if abs(P_total) > 1e-9 else 0.0
    return P_total, z_app


# ─────────────────────────────────────────────────────────────────────────────
# KIỂM TRA #1 — Trượt cung tròn tổng thể (Bishop Simplified)
# ─────────────────────────────────────────────────────────────────────────────


def check_global_slip(
    geom: WallGeometry,
    front_layers: list,
    back_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    method: str = "bishop",
    slope_ratio: float = 2.0,
    n_grid: int = 8,
    n_slices: int = 30,
) -> tuple[float, float, float, float]:
    """Trượt cung tròn tổng thể qua dưới chân cừ.

    Dùng `slope_stability.search_critical_surface` (geotech-staff-engineer 4.6.0)
    nếu có, fallback về phương pháp Bishop đơn giản inline.

    Returns: (Fs_critical, xc, yc, R)
    """
    try:
        from slope_stability import (
            SlopeGeometry, SlopeSoilLayer, analyze_slope,
        )
        _HAS_SLOPE = True
    except ImportError:
        _HAS_SLOPE = False

    if not _HAS_SLOPE:
        return _bishop_fallback(geom, front_layers, back_layers, fill, cdm,
                                 slope_ratio, n_grid, n_slices)

    # Build SlopeGeometry
    te = geom.top_elev
    sf = geom.soil_level_front
    sb = geom.soil_level_back
    L = geom.pile_length
    fill_h = max(0.0, te - sf)
    slope_x = -(fill_h * slope_ratio) if fill_h > 0.05 else 0.0
    reach = max(40.0, L * 2.0)
    if fill_h > 0.05:
        surface = [(-reach, sf), (slope_x, sf), (0.0, te), (reach, sb)]
    else:
        surface = [(-reach, sf), (0.0, te), (reach, sb)]

    # Build layer list cho slope_stability (chú ý: dùng top/bottom elevation)
    sl_layers = []
    # Fill (nếu có)
    if fill_h > 0:
        sl_layers.append(SlopeSoilLayer(
            name="Fill", top_elevation=te, bottom_elevation=sf,
            gamma=fill.gamma if fill else 18.0, phi=fill.phi if fill else 25.0,
            c_prime=fill.c if fill else 0.0, cu=0.0,
            analysis_mode="drained",
        ))
    # CDM block (composite)
    if cdm is not None and front_layers:
        mid = (cdm.top_elev + cdm.bot_elev) / 2
        soil_at = _layer_at_elev(mid, sf, front_layers)
        if soil_at:
            comp = cdm.composite(soil_at)
            sl_layers.append(SlopeSoilLayer(
                name="CDM_composite", top_elevation=cdm.top_elev,
                bottom_elevation=cdm.bot_elev,
                gamma=comp.gamma, phi=comp.phi, c_prime=comp.c, cu=0.0,
                analysis_mode="drained",
            ))
    # Front layers còn lại (bên dưới CDM)
    prev_top = cdm.bot_elev if cdm else sf
    for lay in front_layers:
        if lay.tip_elev < prev_top:
            sl_layers.append(SlopeSoilLayer(
                name=f"Layer_tip{lay.tip_elev:.1f}", top_elevation=prev_top,
                bottom_elevation=lay.tip_elev, gamma=lay.gamma,
                phi=lay.phi, c_prime=lay.c, cu=0.0,
                analysis_mode="drained",
            ))
            prev_top = lay.tip_elev

    geom_sl = SlopeGeometry(
        surface_points=surface, soil_layers=sl_layers,
        gwt_points=[(-reach, geom.water_elev_front),
                     (0.0, geom.water_elev_front),
                     (reach, geom.water_elev_back)],
        surcharge=geom.surcharge_front,
    )

    # ── CONSTRAINT: mỗi cung trượt PHẢI đi qua chân cừ ──────────────────────
    # Chân cừ tại (x=0, y=z_tip). Với mỗi tâm (xc, yc) trong lưới:
    #     R = √(xc² + (yc − z_tip)²)
    # → cung qua chân cừ + chỉ search 2 tham số (xc, yc), không search R.
    z_tip = te - L
    x_min = slope_x * 1.5 if slope_x else -L * 0.3
    x_max = L * 0.3
    y_min = te
    y_max = te + L

    import numpy as _np
    xc_vals = _np.linspace(x_min, x_max, int(n_grid))
    yc_vals = _np.linspace(y_min, y_max, int(n_grid))

    best_Fs = float("inf")
    best_xc = best_yc = best_R = 0.0
    for xc_i in xc_vals:
        for yc_i in yc_vals:
            R_i = math.sqrt(xc_i * xc_i + (yc_i - z_tip) ** 2)
            if R_i < 1.0:
                continue
            try:
                res_i = analyze_slope(
                    geom_sl, xc=float(xc_i), yc=float(yc_i), radius=R_i,
                    method=method, n_slices=int(n_slices),
                )
            except Exception:
                continue
            # FOS_<method> ưu tiên (Optional → có thể None); fallback FOS chung
            _fos_i = getattr(res_i, f"FOS_{method}", None)
            fos = _fos_i if _fos_i is not None else (res_i.FOS or None)
            if fos is None or fos <= 0:
                continue
            if fos < best_Fs:
                best_Fs = float(fos)
                best_xc, best_yc, best_R = float(xc_i), float(yc_i), float(R_i)

    if best_Fs == float("inf"):
        # Không có cung nào hợp lệ trong lưới → fallback Bishop inline (cũng constraint qua chân cừ)
        return _bishop_fallback(geom, front_layers, back_layers, fill, cdm,
                                 slope_ratio, n_grid, n_slices)
    return best_Fs, best_xc, best_yc, best_R


def _bishop_fallback(geom, front_layers, back_layers, fill, cdm,
                     slope_ratio, n_grid, n_slices) -> tuple[float, float, float, float]:
    """Bishop fallback đơn giản — grid search (xc,yc) qua chân cừ.

    Chỉ dùng khi `slope_stability` engine không có. Kết quả thường cao hơn
    engine chuẩn vì không tìm critical surface tối ưu.
    """
    pile_tip = geom.bot_elev
    te = geom.top_elev
    L = geom.pile_length
    sf = geom.soil_level_front
    fill_h = max(0.0, te - sf)
    slope_x = -(fill_h * slope_ratio) if fill_h > 0.05 else 0.0
    xc_min = slope_x * 1.5 if slope_x else -L * 0.3
    xc_max = L * 0.3
    yc_min, yc_max = te, te + L
    dx = (xc_max - xc_min) / max(n_grid - 1, 1)
    dy = (yc_max - yc_min) / max(n_grid - 1, 1)

    # Build all_front layers — bổ sung γ_sub để xử lý đúng dưới MNN
    all_layers = []
    if fill_h > 0 and fill:
        all_layers.append((te, sf, fill.gamma, fill.gamma_sub, fill.phi, fill.c))
    cdm_used = False
    if cdm and front_layers:
        mid = (cdm.top_elev + cdm.bot_elev) / 2
        soil_at = _layer_at_elev(mid, sf, front_layers)
        if soil_at:
            comp = cdm.composite(soil_at)
            all_layers.append((cdm.top_elev, cdm.bot_elev,
                                comp.gamma, comp.gamma_sub, comp.phi, comp.c))
            cdm_used = True
    prev_top = cdm.bot_elev if cdm_used else sf
    for lay in front_layers:
        if lay.tip_elev < prev_top:
            all_layers.append((prev_top, lay.tip_elev,
                                lay.gamma, lay.gamma_sub, lay.phi, lay.c))
            prev_top = lay.tip_elev

    def _lay_at(z, _water_e=None):
        """Trả (γ_eff, φ, c). γ_eff = γ_sub nếu z dưới MNN, ngược lại γ."""
        for top, bot, g, g_sub, phi, c in all_layers:
            if bot <= z <= top:
                if _water_e is not None and z < _water_e:
                    return g_sub, phi, c
                return g, phi, c
        # fallback last layer
        if all_layers:
            top, bot, g, g_sub, phi, c = all_layers[-1]
            if _water_e is not None and z < _water_e:
                return g_sub, phi, c
            return g, phi, c
        return (18.0, 25.0, 0.0)

    def _y_surf(x):
        if x <= slope_x: return te
        if x >= 0: return sf
        return te + (sf - te) * (x - slope_x) / (0 - slope_x or 1)

    def _bishop_FoS(xc, yc, R, n_sl=None):
        """Bishop simplified với effective stress + 1 lát/m.

        Đúng vật lý:
        - Driving (mẫu số): dùng W_total (trọng lượng đầy đủ, kể cả dưới nước)
        - Resisting (tử số): dùng W_total − u·b (effective normal force)
        - u (pore pressure tại đáy) = γ_w × max(0, MNN − y_cir)
        """
        x_left, x_right = xc - R, xc + R
        if x_right - x_left <= 0: return None
        # 1 lát / 1m (làm tròn lên)
        if n_sl is None:
            n_sl = max(30, int(math.ceil(x_right - x_left)))
        dxs = (x_right - x_left) / n_sl
        _gw = geom.gamma_w
        Fs = 1.5
        for _ in range(50):
            num = 0.0; den = 0.0
            for i in range(n_sl):
                x_i = x_left + (i + 0.5) * dxs
                y_top = _y_surf(x_i)
                arg = R * R - (x_i - xc) ** 2
                if arg <= 0: continue
                y_cir = yc - math.sqrt(arg)
                if y_cir >= y_top - 0.01: continue
                h = y_top - y_cir
                if h <= 0: continue
                # MNN tại x_i: Front (x<0) vs Back (x≥0)
                _water_x = (geom.water_elev_front if x_i < 0
                             else geom.water_elev_back)

                # Thuộc tính đất tại midpoint slice
                y_mid = (y_top + y_cir) / 2
                gam, phi, c = _lay_at(y_mid)

                # Trọng lượng TOTAL (cho driving force) — luôn dùng γ đầy đủ
                # (đất bão hoà cũng có khối lượng → tạo driving moment)
                W_total = gam * h * dxs

                # Tải khai thác q (surcharge) — chỉ áp dụng trên mặt Front (x<0)
                # khi slice nằm trên đất đắp Front (y_top ≥ Z_front).
                # q tạo thêm driving moment + tăng σ'v → tăng resisting (tan φ effect).
                _q_on_slice = 0.0
                if x_i < 0 and geom.surcharge_front > 0:
                    _q_on_slice = float(geom.surcharge_front) * dxs   # kN/m (per slice)

                # Pore pressure tại đáy slice (effective stress correction cho resisting)
                u_base = max(0.0, _water_x - y_cir) * _gw
                # Hiệu chỉnh resisting: W_eff = (W_total + q·b) − u·b (effective N')
                W_eff_resist = max(0.0, W_total + _q_on_slice - u_base * dxs)

                sin_a = -(x_i - xc) / R
                cos_a = math.sqrt(max(arg, 1e-9)) / R
                if cos_a <= 0: continue
                m_alpha = cos_a + sin_a * math.tan(math.radians(phi)) / Fs
                if m_alpha <= 1e-6: continue
                # Resisting: dùng W_eff (đã trừ buoyancy + cộng q)
                num += (c * dxs + W_eff_resist * math.tan(math.radians(phi))) / m_alpha
                # Driving: dùng W_total + q (tải khai thác kéo trượt)
                den += (W_total + _q_on_slice) * sin_a
            if abs(den) < 1e-6: return None
            new_Fs = num / den
            if abs(new_Fs - Fs) < 0.001: return new_Fs
            Fs = new_Fs
        return Fs

    best = (999.0, 0.0, te, L)
    for ix in range(n_grid):
        for iy in range(n_grid):
            xc = xc_min + ix * dx
            yc = yc_min + iy * dy
            R = math.sqrt(xc * xc + (yc - pile_tip) ** 2)
            # n_sl=None → tự tính 1 lát/m (max 30 lát tối thiểu)
            f = _bishop_FoS(xc, yc, R, None)
            if f is not None and 0 < f < best[0]:
                best = (f, xc, yc, R)
    return best


# ─────────────────────────────────────────────────────────────────────────────
# KIỂM TRA #2 — Lật quanh chân cừ
# ─────────────────────────────────────────────────────────────────────────────


def check_overturning(
    geom: WallGeometry,
    front_layers: list,
    back_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    pile: Optional[PileProps] = None,
    pile_weight_kNm: float = 7.32,
    n_slices: int = 200,
) -> tuple[float, float, float]:
    """Lật quanh chân cừ (pile_tip).

    M_lật  = Active Front × tay đòn + Boussinesq nếu có
    M_giữ  = trọng lượng tường + đất đắp + Passive Back × tay đòn

    Returns: (Fs, M_giu_kNm, M_lat_kNm)
    """
    # Active moment (lật)
    P_a, z_a = _integrate_active_back_to_tip(geom, front_layers, fill, cdm,
                                              n_slices=n_slices)
    M_lat = P_a * z_a   # kNm/m tường

    # Passive moment (giữ)
    P_p, z_p = _integrate_passive_back_below_dredge(geom, back_layers, cdm,
                                                     n_slices=n_slices // 2)
    M_giu_passive = P_p * z_p  # z_p âm hoặc gần 0 vì dưới chân cừ

    # Trọng lượng tường (giả định nằm tại trục cừ → tay đòn = 0 quanh chân cừ)
    # → Wpile không tạo moment quanh chân cừ (vì cùng trục).
    # Nhưng nếu có lệch tâm e → M_W = W × e. Tạm bỏ qua e=0.

    # Trọng lượng đất đắp phía Front (fill) → tay đòn ngang ~ B_fill/2
    # Tạm coi tay đòn ngang là 0 (đất đắp ngay trên đỉnh cừ).
    # → bỏ qua moment fill.

    M_giu = abs(M_giu_passive)
    Fs = M_giu / M_lat if M_lat > 1e-9 else 999.0
    return Fs, M_giu, M_lat


# ─────────────────────────────────────────────────────────────────────────────
# KIỂM TRA #3 — Xoay nhổ chân cừ (Toe Kick-Out, Free Earth Support)
# ─────────────────────────────────────────────────────────────────────────────


def check_toe_kickout(
    geom: WallGeometry,
    front_layers: list,
    back_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    n_slices: int = 200,
) -> tuple[float, float, float]:
    """Toe kick-out — Free Earth Support method.

    Mp / Ma ≥ Fs_min (1.5 theo USACE EM 1110-2-2504).

    Ma: moment của áp lực CHỦ ĐỘNG phía Front quanh chân cừ
    Mp: moment của áp lực BỊ ĐỘNG phía Back DƯỚI đáy đào quanh chân cừ

    Returns: (Fs, Ma_kNm, Mp_kNm)
    """
    P_a, z_a = _integrate_active_back_to_tip(geom, front_layers, fill, cdm,
                                              n_slices=n_slices)
    Ma = P_a * z_a  # tay đòn dương từ chân cừ lên

    P_p, z_p = _integrate_passive_back_below_dredge(geom, back_layers, cdm,
                                                     n_slices=n_slices // 2)
    Mp = abs(P_p * z_p)  # tay đòn từ chân cừ xuống (lấy abs)

    Fs = Mp / Ma if Ma > 1e-9 else 999.0
    return Fs, Ma, Mp


# ─────────────────────────────────────────────────────────────────────────────
# Hàm gộp — chạy cả 3 kiểm tra
# ─────────────────────────────────────────────────────────────────────────────


def check_all(
    geom: WallGeometry,
    front_layers: list,
    back_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    pile: Optional[PileProps] = None,
    method: str = "bishop",
) -> SWStabilityResult:
    """Chạy đầy đủ 3 kiểm tra ổn định tổng thể, trả về SWStabilityResult."""
    # Helper: ép float, None → 0.0 (đảm bảo format f"{x:.Nf}" luôn chạy)
    def _f(v) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    res = SWStabilityResult()
    # 1. Trượt cung tròn
    try:
        Fs1, xc, yc, R = check_global_slip(geom, front_layers, back_layers,
                                            fill, cdm, method=method)
        res.Fs_global_slip = _f(Fs1)
        res.slip_xc = _f(xc); res.slip_yc = _f(yc); res.slip_R = _f(R)
        res.slip_method = method
    except Exception as e:
        res.warnings.append(f"Trượt cung tròn: {e}")
        res.Fs_global_slip = 0.0
    # 2. Lật
    try:
        Fs2, Mg, Ml = check_overturning(geom, front_layers, back_layers,
                                         fill, cdm, pile)
        res.Fs_overturning = _f(Fs2)
        res.M_giu_kNm = _f(Mg); res.M_lat_kNm = _f(Ml)
    except Exception as e:
        res.warnings.append(f"Lật: {e}")
    # 3. Toe kick-out
    try:
        Fs3, Ma, Mp = check_toe_kickout(geom, front_layers, back_layers,
                                         fill, cdm)
        res.Fs_toe_kickout = _f(Fs3)
        res.Ma_kNm = _f(Ma); res.Mp_kNm = _f(Mp)
    except Exception as e:
        res.warnings.append(f"Toe kick-out: {e}")
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Tìm L cừ SW tối ưu — Thuật toán lặp +1m (tài liệu 48-ke-sw-L-optimal-search.md)
# ─────────────────────────────────────────────────────────────────────────────

import dataclasses as _dc
import sqlite3 as _sq_li
import uuid as _uuid_li
from pathlib import Path as _Path_li


def create_L_iteration_table(db_path: _Path_li) -> None:
    """Tạo bảng ke_sw_L_iteration (idempotent)."""
    with _sq_li.connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ke_sw_L_iteration (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                bh_name         TEXT NOT NULL,
                pile_type       TEXT NOT NULL,
                L_m             REAL NOT NULL,
                Fs_bishop       REAL,
                Fs_spencer      REAL,
                Fs_mp           REAL,
                Fs_overturning  REAL,
                pass_slip       INTEGER DEFAULT 0,
                pass_overt      INTEGER DEFAULT 0,
                all_pass        INTEGER DEFAULT 0,
                is_final        INTEGER DEFAULT 0,
                run_id          TEXT NOT NULL,
                ts              TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (bh_name, pile_type, L_m, run_id)
            )
        """)
        con.commit()


def find_optimal_L_iterative(
    bh_name: str,
    pile_type: str,
    geom_template: WallGeometry,
    front_layers: list,
    back_layers: list,
    fill: Optional[EarthLayer] = None,
    cdm: Optional[CDMBlock] = None,
    pile: Optional[PileProps] = None,
    L_start: float = 20.0,
    L_max: float = 50.0,
    L_step: float = 1.0,
    Fs_min_slip: float = 1.40,
    Fs_min_overt: float = 1.20,
    save_to_db: bool = True,
    db_path: Optional[_Path_li] = None,
    run_id: Optional[str] = None,
) -> dict:
    """Tìm L cừ SW tối ưu — lặp tăng L bước +1m cho đến khi 4 PP đạt ngưỡng.

    Args:
        bh_name:     'KE-HK1', 'KE-HK10'...
        pile_type:   'SW-740', 'SW-840'...
        geom_template: WallGeometry — sẽ copy + override pile_length per step
        L_start:     L bắt đầu (m) — thường = L_thiết_kế hiện tại
        L_max:       L tối đa (m) — thường = pile catalog L_max
        L_step:      bước tăng (m) — mặc định 1.0
        Fs_min_slip: ngưỡng Fs cho 3 PP trượt (mặc định 1.40)
        Fs_min_overt: ngưỡng Fs lật (mặc định 1.20)
        save_to_db:  True → ghi mỗi step vào ke_sw_L_iteration
        db_path:     đường dẫn TTHC.sqlite — bắt buộc khi save_to_db=True

    Returns:
        {
            'bh_name': str, 'pile_type': str,
            'L_optimal_m': float | None,   # None nếu không tìm được trong [L_start, L_max]
            'L_start_m': float, 'L_max_m': float, 'L_step_m': float,
            'Fs_min_slip': float, 'Fs_min_overt': float,
            'history': [{L_m, Fs_bishop, Fs_spencer, Fs_mp, Fs_lat,
                         pass_slip, pass_overt, all_pass, is_final}, ...],
            'n_iterations': int,
            'run_id': str,
        }
    """
    if save_to_db and db_path is None:
        raise ValueError("save_to_db=True yêu cầu db_path")

    rid = run_id or _uuid_li.uuid4().hex[:12]
    if save_to_db:
        create_L_iteration_table(db_path)

    history: list = []
    L_optimal: Optional[float] = None
    n_iter = 0
    L = float(L_start)

    while L <= L_max + 1e-6:
        n_iter += 1
        # Copy geom + override pile_length cho step này
        geom_iter = _dc.replace(geom_template, pile_length=float(L))

        # Chạy 3 PP slip + lật
        Fs_b = Fs_s = Fs_mp = Fs_ot = None
        try:
            res_b = check_all(geom_iter, front_layers, back_layers,
                              fill, cdm, pile, method="bishop")
            Fs_b = float(res_b.Fs_global_slip)
            Fs_ot = float(res_b.Fs_overturning)
        except Exception:
            pass
        try:
            res_s = check_all(geom_iter, front_layers, back_layers,
                              fill, cdm, pile, method="spencer")
            Fs_s = float(res_s.Fs_global_slip)
        except Exception:
            pass
        try:
            res_m = check_all(geom_iter, front_layers, back_layers,
                              fill, cdm, pile, method="morgenstern_price")
            Fs_mp = float(res_m.Fs_global_slip)
        except Exception:
            pass

        # Đánh giá pass/fail
        slip_vals = [v for v in (Fs_b, Fs_s, Fs_mp) if v is not None and v > 0]
        pass_slip  = bool(slip_vals) and (min(slip_vals) >= Fs_min_slip)
        pass_overt = (Fs_ot is not None) and (Fs_ot >= Fs_min_overt)
        all_pass   = pass_slip and pass_overt

        step = {
            "L_m":            round(L, 2),
            "Fs_bishop":      round(Fs_b, 3) if Fs_b is not None else None,
            "Fs_spencer":     round(Fs_s, 3) if Fs_s is not None else None,
            "Fs_mp":          round(Fs_mp, 3) if Fs_mp is not None else None,
            "Fs_lat":         round(Fs_ot, 3) if Fs_ot is not None else None,
            "pass_slip":      int(pass_slip),
            "pass_overt":     int(pass_overt),
            "all_pass":       int(all_pass),
            "is_final":       0,
        }
        history.append(step)

        if all_pass:
            L_optimal = L
            step["is_final"] = 1
            if save_to_db:
                _save_iteration(db_path, bh_name, pile_type, step, rid)
            break

        if save_to_db:
            _save_iteration(db_path, bh_name, pile_type, step, rid)

        L += L_step

    return {
        "bh_name":      bh_name,
        "pile_type":    pile_type,
        "L_optimal_m":  L_optimal,
        "L_start_m":    float(L_start),
        "L_max_m":      float(L_max),
        "L_step_m":     float(L_step),
        "Fs_min_slip":  float(Fs_min_slip),
        "Fs_min_overt": float(Fs_min_overt),
        "history":      history,
        "n_iterations": n_iter,
        "run_id":       rid,
    }


def _save_iteration(db_path: _Path_li, bh: str, pile: str,
                    step: dict, run_id: str) -> None:
    """Lưu 1 step vào ke_sw_L_iteration. INSERT OR REPLACE idempotent."""
    with _sq_li.connect(db_path) as con:
        con.execute("""
            INSERT INTO ke_sw_L_iteration
                (bh_name, pile_type, L_m, Fs_bishop, Fs_spencer, Fs_mp,
                 Fs_overturning, pass_slip, pass_overt, all_pass, is_final, run_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (bh_name, pile_type, L_m, run_id) DO UPDATE SET
                Fs_bishop       = excluded.Fs_bishop,
                Fs_spencer      = excluded.Fs_spencer,
                Fs_mp           = excluded.Fs_mp,
                Fs_overturning  = excluded.Fs_overturning,
                pass_slip       = excluded.pass_slip,
                pass_overt      = excluded.pass_overt,
                all_pass        = excluded.all_pass,
                is_final        = excluded.is_final,
                ts              = datetime('now','localtime')
        """, (bh, pile, step["L_m"], step["Fs_bishop"], step["Fs_spencer"],
              step["Fs_mp"], step["Fs_lat"], step["pass_slip"],
              step["pass_overt"], step["all_pass"], step["is_final"], run_id))
        con.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────────────────────


def _demo_ke_hk8():
    """Demo KE-HK8 + SW-840 L=29m + CDM Lc=26.2m."""
    geom = WallGeometry(
        top_elev=2.7, pile_length=29.0,
        soil_level_front=0.0, soil_level_back=-1.0,
        water_elev_front=-0.5, water_elev_back=-0.5,
        surcharge_front=10.0,
    )
    fill = EarthLayer(0.0, 18, 8, 28, 0)
    front_layers = [
        EarthLayer(-24.1, 15, 5, 10, 5),
        EarthLayer(-30, 18, 8, 30, 0),
    ]
    back_layers = list(front_layers)
    # CDM Lc=26.2, L_ngam=0.5 → CDM dày 25.7m từ 0.0 xuống -25.7
    cdm = CDMBlock(top_elev=0.0, bot_elev=-25.7,
                   area_ratio_a=0.20, c_col_kPa=75.0,
                   phi_col_deg=30.0, gamma_col_kNm3=19.0)

    res = check_all(geom, front_layers, back_layers,
                    fill=fill, cdm=cdm, method="bishop")
    print(res.summary())
    print(f"\nMặt trượt nguy hiểm nhất: tâm ({res.slip_xc:+.1f}, {res.slip_yc:+.1f})  "
          f"R = {res.slip_R:.1f} m")
    print(f"Moment lật/giữ: {res.M_lat_kNm:.0f} / {res.M_giu_kNm:.0f} kNm")
    print(f"Toe kick-out: Ma = {res.Ma_kNm:.0f}, Mp = {res.Mp_kNm:.0f} kNm")
    return res


if __name__ == "__main__":
    _demo_ke_hk8()
