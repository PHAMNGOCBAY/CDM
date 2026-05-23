"""
wall_internal_force.py — Solver Winkler tường cọc ván SW thay thế anastruct.

Quy ước Front/Back (CLAUDE.md §20 — BẮT BUỘC toàn dự án):
  Front = TRÁI = đất đắp / mặt đường / xe chạy / tải trọng → Active (Ka) — đẩy cừ về Back
  Back  = PHẢI = đào / sông / mặt nước hở                  → Passive (Kp) — kháng dưới đáy đào
  Front có fill cao hơn cừ; Back đào xuống thấp.

Hỗ trợ 2 chế độ tải:
- TẢI TẬP TRUNG: H + M tại đỉnh cọc (giống _calc_py_winkler hiện tại)
- TẢI PHÂN BỐ:   áp lực đất chủ động Front + nước + bị động Back (thực tế)

Solver chính: PyNiteFEA (MIT, pure Python, Streamlit Cloud-ready).
Solver tham chiếu: anastruct (so sánh kết quả với tải tập trung).

Đơn vị: SI (m, kN, kPa, kN/m³). Cọc per-meter-tường (PLAXIS Plate convention).
Net pressure dương → đẩy tường từ Front sang Back.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


GAMMA_W = 9.81  # kN/m³


# ─────────────────────────────────────────────────────────────────────────────
# Dữ liệu — lò xo nền (Winkler) p-y
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SoilLayer:
    """Lớp đất cho mô hình Winkler p-y (theo chiều dày dọc cọc)."""
    symbol: str
    thickness_m: float
    Su_kPa: float = 10.0
    gamma_kNm3: float = 15.0
    is_clay: bool | None = None

    SAND_SYMBOLS = {"F", "2a", "2b", "2c", "4", "5a", "6", "7"}

    def __post_init__(self) -> None:
        if self.is_clay is None:
            self.is_clay = self.symbol not in self.SAND_SYMBOLS


@dataclass
class PileProps:
    name: str
    D_m: float
    EI_kNm2: float
    Mcr_kNm: float = 0.0
    Atd_m2: float = 0.0


def sw_pile_props(H_mm: float, Itd_cm4: float, Mcr_Tm: float = 0.0,
                  Atd_cm2: float = 0.0, fc_MPa: float = 70.0,
                  name: str = "SW-?") -> PileProps:
    """Eurocode 2: Ec = 22*(fcm/10)^0.3 GPa. f'c=70 → Ec ≈ 31.6 GPa."""
    Ec_kNm2 = 22e6 * (fc_MPa / 10.0) ** 0.3
    return PileProps(
        name=name, D_m=H_mm / 1000.0,
        EI_kNm2=Ec_kNm2 * Itd_cm4 * 1e-8,
        Mcr_kNm=Mcr_Tm * 9.81, Atd_m2=Atd_cm2 * 1e-4,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dữ liệu — Áp lực đất ngang Front (Active) + Back (Passive)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EarthLayer:
    """Lớp đất cho tính áp lực ngang (theo cao độ đáy lớp)."""
    tip_elev: float    # cao độ đáy lớp (m)
    gamma: float       # dung trọng tự nhiên (kN/m³)
    gamma_sub: float   # dung trọng đẩy nổi (kN/m³)
    phi: float         # góc ma sát hữu hiệu (°)
    c: float = 0.0     # lực dính hữu hiệu (kPa)


def insert_cdm_block(
    layers: list,
    soil_top: float,
    cdm_top_elev: float,
    cdm_bot_elev: float,
    cdm_phi: float = 30.0,
    cdm_c: float = 50.0,
    cdm_gamma: float = 20.0,
    cdm_gamma_sub: float = 10.0,
) -> list:
    """Chèn khối CDM gia cố vào danh sách EarthLayer.

    Strategy: dùng phương pháp segment — duyệt từng đoạn cao độ giữa các điểm gãy,
    với mỗi đoạn xác định lớp đất gốc bao quanh, rồi quyết định CDM hay lớp gốc.

    Args:
        layers: danh sách EarthLayer gốc (sắp xếp từ trên xuống theo tip_elev giảm)
        soil_top: cao độ đỉnh lớp đầu tiên (= soil_level_front của bài toán)
        cdm_top_elev, cdm_bot_elev: phạm vi khối CDM (cdm_top > cdm_bot)
        cdm_phi/c/gamma/gamma_sub: thông số CDM (mặc định: cement-treated điển hình)

    Returns:
        list[EarthLayer] mới với CDM chèn đúng vị trí, lớp gốc bị split tự động.

    Ví dụ KE-HK8:
        # Soft clay 24.1m, chèn CDM từ -1 → -10 m
        layers = [EarthLayer(-24.1, 15, 5, 10, 5), EarthLayer(-30, 18, 8, 30, 0)]
        new = insert_cdm_block(layers, soil_top=0.0,
                               cdm_top_elev=-1.0, cdm_bot_elev=-10.0)
        # → [
        #   EarthLayer(-1.0,   15, 5, 10, 5),   # soft clay từ 0 → -1
        #   EarthLayer(-10.0,  20, 10, 30, 50), # CDM từ -1 → -10
        #   EarthLayer(-24.1,  15, 5, 10, 5),   # soft clay từ -10 → -24.1
        #   EarthLayer(-30.0,  18, 8, 30, 0),   # sand
        # ]
    """
    if cdm_top_elev <= cdm_bot_elev:
        raise ValueError("cdm_top_elev phải > cdm_bot_elev")

    # 1. Build segment list từ layers gốc: (top, bot, lay)
    segs_orig = []
    cur_top = soil_top
    for lay in layers:
        segs_orig.append((cur_top, lay.tip_elev, lay))
        cur_top = lay.tip_elev

    # 2. Split mỗi segment bằng cdm_top/cdm_bot, build new segments
    cdm_lay = EarthLayer(tip_elev=cdm_bot_elev, gamma=cdm_gamma,
                         gamma_sub=cdm_gamma_sub, phi=cdm_phi, c=cdm_c)
    new_segs: list[tuple[float, float, "EarthLayer"]] = []

    for (s_top, s_bot, lay) in segs_orig:
        # Phần trên cdm_top (giữ nguyên lớp gốc)
        top_above = min(s_top, soil_top)
        bot_above = max(s_bot, cdm_top_elev)
        if top_above > bot_above:
            new_segs.append((top_above, bot_above, lay))
        # Phần trong CDM (bỏ qua — sẽ thay bằng CDM block sau)
        # Phần dưới cdm_bot (giữ nguyên lớp gốc)
        top_below = min(s_top, cdm_bot_elev)
        bot_below = s_bot
        if top_below > bot_below:
            new_segs.append((top_below, bot_below, lay))

    # 3. Chèn CDM block — chỉ phần CDM overlap với toàn vùng layers
    soil_bot = layers[-1].tip_elev if layers else cdm_bot_elev
    cdm_top_eff = min(cdm_top_elev, soil_top)
    cdm_bot_eff = max(cdm_bot_elev, soil_bot)
    if cdm_top_eff > cdm_bot_eff:
        new_segs.append((cdm_top_eff, cdm_bot_eff, cdm_lay))

    # 4. Sort theo top giảm dần, build EarthLayer list mới (chỉ giữ tip_elev)
    new_segs.sort(key=lambda s: -s[0])
    return [EarthLayer(tip_elev=s[1], gamma=s[2].gamma, gamma_sub=s[2].gamma_sub,
                       phi=s[2].phi, c=s[2].c) for s in new_segs]


@dataclass
class WallGeometry:
    """Hình học bài toán tường cừ SW.

    Quy ước (CLAUDE.md §20):
        Front (TRÁI) = đất đắp + tải trọng → soil_level_front THƯỜNG CAO
        Back  (PHẢI) = đào / sông          → soil_level_back  THƯỜNG THẤP HƠN
    """
    top_elev: float            # cao độ đỉnh cừ (m) = đỉnh fill
    pile_length: float         # chiều dài cừ (m)
    soil_level_front: float    # cao độ mặt đất Front (chân đất đắp, cao)
    soil_level_back: float     # cao độ mặt đất Back  (đáy đào, thấp)
    water_elev_front: float    # mực nước phía Front (m)
    water_elev_back: float     # mực nước phía Back  (m)
    surcharge_front: float = 0.0  # tải mặt Front (kPa) — xe/người/công trình
    gamma_w: float = GAMMA_W

    @property
    def bot_elev(self) -> float:
        return self.top_elev - self.pile_length

    @property
    def fill_thickness(self) -> float:
        """Chiều dày đất đắp phía Front (từ soil_level_front lên top_elev)."""
        return max(0.0, self.top_elev - self.soil_level_front)


def _Ka_rankine(phi_deg: float) -> float:
    return math.tan(math.radians(45.0 - phi_deg / 2.0)) ** 2


def _Kp_rankine(phi_deg: float) -> float:
    return math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2


def _layer_at_elev(elev: float, top: float, layers: list[EarthLayer]) -> EarthLayer | None:
    cur_top = top
    for lay in layers:
        if lay.tip_elev <= elev <= cur_top:
            return lay
        cur_top = lay.tip_elev
    return layers[-1] if layers else None


def _eff_gamma(lay: EarthLayer, e_top: float, e_bot: float, water_elev: float) -> float:
    dz = e_top - e_bot
    if dz <= 1e-9: return lay.gamma
    if water_elev >= e_top: return lay.gamma
    if water_elev <= e_bot: return lay.gamma_sub
    return (lay.gamma * (e_top - water_elev) + lay.gamma_sub * (water_elev - e_bot)) / dz


def build_lateral_load(geom: WallGeometry,
                       front_layers: list[EarthLayer],
                       back_layers: list[EarthLayer],
                       fill: EarthLayer | None = None,
                       N: int = 200,
                       include_water: bool = True,
                       mode: str = "winkler",
                       ) -> dict:
    """Tính áp lực ngang phân bố tổng hợp dọc cừ — quy ước CLAUDE.md §20.

    Mode='winkler' (mặc định, dùng với solve_pynite_dist + lò xo nền):
        p_net = σ_h_active_front + p_w_front − p_w_back
        → Chỉ tải MẤT ỔN ĐỊNH (Active phía đắp + nước). Lò xo Winkler đảm
          nhiệm phản kháng bị động tự động. Trừ σ_h_passive ở đây → DOUBLE-COUNT.

    Mode='free_earth' (sheet pile cantilever, không lò xo):
        p_net = (σ_h_active_front + p_w_front) − (σ_h_passive_back + p_w_back)
        → Tổng hợp tải net, dùng cân bằng tĩnh ΣM=0 quanh điểm xoay.

    Args:
        front_layers: lớp đất tự nhiên phía Front (dưới soil_level_front)
        back_layers:  lớp đất tự nhiên phía Back  (dưới soil_level_back)
        fill: lớp đắp phía Front, nằm từ soil_level_front → top_elev

    Returns dict:
        elevs:             cao độ array từ top xuống bot (m, giảm dần)
        zs_depth_m:        độ sâu từ đỉnh cừ (m, tăng dần) — input solver
        sigma_h_active:    áp lực chủ động Front (kN/m²)
        sigma_h_passive:   áp lực bị động Back   (kN/m²)
        p_water_front, p_water_back: áp lực nước (kN/m²)
        p_net:             áp lực ngang tổng hợp (kN/m²) — theo mode
        F_active, F_passive, F_water_net, F_net: lực tổng hợp (kN/m tường)
    """
    import numpy as np

    # 1. Lưới cao độ với các điểm gãy
    keys = sorted({
        geom.top_elev, geom.bot_elev,
        geom.water_elev_front, geom.water_elev_back,
        geom.soil_level_front, geom.soil_level_back,
        *[l.tip_elev for l in front_layers],
        *[l.tip_elev for l in back_layers],
    }, reverse=True)
    keys = [k for k in keys if geom.bot_elev <= k <= geom.top_elev]
    segs = []
    n_per = max(3, N // max(len(keys) - 1, 1))
    for i in range(len(keys) - 1):
        seg = np.linspace(keys[i], keys[i + 1], n_per)
        segs.append(seg[:-1])
    segs.append(np.array([keys[-1]]))
    elevs = np.concatenate(segs)

    # 2. Front side = đất đắp (fill) bên trên + đất tự nhiên bên dưới
    all_front: list[EarthLayer] = []
    if fill is not None and geom.fill_thickness > 0:
        all_front.append(EarthLayer(
            tip_elev=geom.soil_level_front,
            gamma=fill.gamma, gamma_sub=fill.gamma_sub,
            phi=fill.phi, c=fill.c,
        ))
    all_front.extend(front_layers)

    # Back side = chỉ đất tự nhiên (không có fill)
    all_back: list[EarthLayer] = list(back_layers)

    # 3. Tích phân áp lực dọc cọc
    n = len(elevs)
    sh_a = np.zeros(n)   # Active phía Front
    sh_p = np.zeros(n)   # Passive phía Back
    sv_front = geom.surcharge_front
    sv_back = 0.0
    prev_e = geom.top_elev

    for i, e in enumerate(elevs):
        dz = prev_e - e

        # FRONT (Active): tích lũy σ_v từ top xuống
        lay_f = _layer_at_elev(e, geom.top_elev, all_front)
        if lay_f is not None and dz > 0:
            sv_front += _eff_gamma(lay_f, prev_e, e, geom.water_elev_front) * dz
        if lay_f is not None:
            Ka = _Ka_rankine(lay_f.phi)
            sh_a[i] = max(0.0, Ka * sv_front - 2.0 * lay_f.c * math.sqrt(max(Ka, 0.0)))

        # BACK (Passive): chỉ tính dưới soil_level_back (đáy đào)
        if e <= geom.soil_level_back:
            lay_b = _layer_at_elev(e, geom.soil_level_back, all_back)
            if lay_b is not None:
                if dz > 0 and prev_e <= geom.soil_level_back:
                    sv_back += _eff_gamma(lay_b, prev_e, e, geom.water_elev_back) * dz
                elif dz > 0 and prev_e > geom.soil_level_back and e < geom.soil_level_back:
                    dz_b = geom.soil_level_back - e
                    sv_back += _eff_gamma(lay_b, geom.soil_level_back, e, geom.water_elev_back) * dz_b
                Kp = _Kp_rankine(lay_b.phi)
                sh_p[i] = Kp * sv_back + 2.0 * lay_b.c * math.sqrt(max(Kp, 0.0))

        prev_e = e

    # 4. Áp lực nước hydrostatic
    if include_water:
        p_w_front = np.maximum(0.0, (geom.water_elev_front - elevs) * geom.gamma_w)
        # Phía Back: chỉ có nước phía dưới mặt đào (Back exposed)
        p_w_back = np.where(
            elevs <= min(geom.soil_level_back, geom.water_elev_back),
            np.maximum(0.0, (geom.water_elev_back - elevs) * geom.gamma_w),
            0.0,
        )
    else:
        p_w_front = np.zeros(n)
        p_w_back = np.zeros(n)

    # 5. Net pressure theo mode
    if mode == "winkler":
        p_net = sh_a + p_w_front - p_w_back
    elif mode == "free_earth":
        p_net = (sh_a + p_w_front) - (sh_p + p_w_back)
    else:
        raise ValueError(f"mode={mode!r} không hợp lệ. Dùng 'winkler' hoặc 'free_earth'.")

    zs_depth = geom.top_elev - elevs

    def _F(p):
        F = 0.0
        for i in range(n - 1):
            F += (p[i] + p[i + 1]) / 2.0 * abs(elevs[i] - elevs[i + 1])
        return F

    return {
        "elevs": elevs,
        "zs_depth_m": zs_depth,
        "sigma_h_active": sh_a,
        "sigma_h_passive": sh_p,
        "p_water_front": p_w_front,
        "p_water_back": p_w_back,
        "p_net": p_net,
        "F_active": _F(sh_a),
        "F_passive": _F(sh_p),
        "F_water_net": _F(p_w_front - p_w_back),
        "F_net": _F(p_net),
    }


# ─────────────────────────────────────────────────────────────────────────────
# p-y curves — Matlock (sét) + API RP2GEO (cát)
# ─────────────────────────────────────────────────────────────────────────────


def kh_clay_matlock(z_m: float, D_m: float, Su_kPa: float, gamma_kNm3: float,
                    eps50: float = 0.02) -> float:
    Np = min(3.0 + gamma_kNm3 * z_m / max(Su_kPa, 1.0), 9.0)
    pu = Np * Su_kPa * D_m
    y50 = 2.5 * eps50 * D_m
    return pu / y50 if y50 > 0 else 0.0


def kh_sand_api(z_m: float, k_sand_kNm3: float = 10_000.0) -> float:
    return k_sand_kNm3 * z_m


def kh_profile(layers: list[SoilLayer], pile: PileProps, L_m: float,
               N: int, eps50: float = 0.02, k_sand_kNm3: float = 10_000.0,
               cdm_thickness_m: float = 0.0, cdm_factor: float = 3.0
               ) -> tuple[list[float], list[float]]:
    zs = [i * L_m / (N - 1) for i in range(N)]
    k_h = []
    for z in zs:
        dep = 0.0; layer = layers[-1]
        for lr in layers:
            if dep + lr.thickness_m >= z:
                layer = lr; break
            dep += lr.thickness_m
        if layer.is_clay:
            kz = kh_clay_matlock(z, pile.D_m, layer.Su_kPa, layer.gamma_kNm3, eps50)
        else:
            kz = kh_sand_api(z, k_sand_kNm3)
        if z < cdm_thickness_m: kz *= cdm_factor
        k_h.append(max(kz, 1.0))
    return zs, k_h


# ─────────────────────────────────────────────────────────────────────────────
# PyNite model builder (chung cho 2 chế độ tải)
# ─────────────────────────────────────────────────────────────────────────────


def _build_pynite_model(layers, pile, L_m, N, eps50, k_sand_kNm3,
                        cdm_thickness_m, cdm_factor, tip_fixity="free",
                        top_pin: bool = False):
    from Pynite import FEModel3D
    EI = pile.EI_kNm2
    zs, k_h = kh_profile(layers, pile, L_m, N, eps50, k_sand_kNm3,
                         cdm_thickness_m, cdm_factor)
    dz = L_m / (N - 1)
    model = FEModel3D()
    E = 30e6; nu = 0.15; G = E / (2 * (1 + nu))
    I_eff = EI / E
    model.add_material("Concrete", E=E, G=G, nu=nu, rho=24.0)
    model.add_section("PileSec", A=1.0, Iy=I_eff, Iz=I_eff, J=I_eff)
    for i, z in enumerate(zs):
        model.add_node(f"N{i}", X=z, Y=0.0, Z=0.0)
    for i in range(N - 1):
        model.add_member(f"M{i}", f"N{i}", f"N{i+1}", "Concrete", "PileSec")
    for i in range(N):
        model.def_support(f"N{i}", support_DX=True, support_DY=False, support_DZ=True,
                          support_RX=True, support_RY=True, support_RZ=False)
    if top_pin:
        # Dầm mũ (headwall) — pin support tại đỉnh: khóa DY, cho phép quay RZ
        model.def_support("N0", support_DX=True, support_DY=True, support_DZ=True,
                          support_RX=True, support_RY=True, support_RZ=False)
    if tip_fixity == "pinned":
        model.def_support(f"N{N-1}", support_DX=True, support_DY=True, support_DZ=True,
                          support_RX=True, support_RY=True, support_RZ=False)
    elif tip_fixity == "fixed":
        model.def_support(f"N{N-1}", support_DX=True, support_DY=True, support_DZ=True,
                          support_RX=True, support_RY=True, support_RZ=True)
    for i in range(N):
        model.def_support_spring(f"N{i}", dof="DY", stiffness=k_h[i] * pile.D_m * dz, direction=None)
    return model, zs, k_h, dz


def _extract_results(model, N, pile, zs, k_h, name):
    ux = [model.nodes[f"N{i}"].DY["Combo 1"] * 1000 for i in range(N)]
    Ms = []; Qs = []
    for i in range(N - 1):
        mem = model.members[f"M{i}"]
        Mz = mem.moment_array("Mz", 5, combo_name="Combo 1")[1]
        Ms.append(max(Mz.min(), Mz.max(), key=abs))
        Fy = mem.shear_array("Fy", 5, combo_name="Combo 1")[1]
        Qs.append(max(Fy.min(), Fy.max(), key=abs))
    return {
        "solver": name, "u_top_mm": ux[0], "u_max_mm": max(abs(u) for u in ux),
        "M_max_kNm": max(abs(m) for m in Ms) if Ms else 0.0,
        "Q_max_kN": max(abs(q) for q in Qs) if Qs else 0.0,
        "Mcr_kNm": pile.Mcr_kNm, "EI_kNm2": pile.EI_kNm2, "D_mm": pile.D_m * 1000,
        "zs": zs, "ux": ux, "Ms": Ms, "Qs": Qs, "k_h": k_h,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Solver 1: Tải tập trung H + M tại đỉnh
# ─────────────────────────────────────────────────────────────────────────────


def solve_pynite(layers, pile, L_m, H_kNm, M_kNm=0.0, N=60,
                 eps50=0.02, k_sand_kNm3=10_000.0,
                 cdm_thickness_m=0.0, cdm_factor=3.0,
                 tip_fixity="free", top_pin=False):
    if pile.EI_kNm2 <= 0: return {"error": "EI=0"}
    model, zs, k_h, dz = _build_pynite_model(
        layers, pile, L_m, N, eps50, k_sand_kNm3,
        cdm_thickness_m, cdm_factor, tip_fixity, top_pin=top_pin)
    if abs(H_kNm) > 0: model.add_node_load("N0", "FY", H_kNm)
    if abs(M_kNm) > 0: model.add_node_load("N0", "MZ", M_kNm)
    try: model.analyze(check_statics=False, check_stability=False)
    except Exception as e: return {"error": f"PyNite: {e}"}
    return _extract_results(model, N, pile, zs, k_h, "PyNite-conc")


# ─────────────────────────────────────────────────────────────────────────────
# Solver 2: Tải phân bố p(z) dọc cừ
# ─────────────────────────────────────────────────────────────────────────────


def solve_pynite_dist(layers, pile, L_m, zs_load, p_load_kNm2, N=60,
                      eps50=0.02, k_sand_kNm3=10_000.0,
                      cdm_thickness_m=0.0, cdm_factor=3.0,
                      tip_fixity="free", load_method="distributed",
                      top_pin=False):
    """Winkler với tải phân bố p(z) [kN/m²].

    Dấu p_load_kNm2: dương → đẩy cừ từ Front sang Back.
    """
    import numpy as np
    if pile.EI_kNm2 <= 0: return {"error": "EI=0"}
    model, zs, k_h, dz = _build_pynite_model(
        layers, pile, L_m, N, eps50, k_sand_kNm3,
        cdm_thickness_m, cdm_factor, tip_fixity, top_pin=top_pin)
    p_at = np.interp(np.array(zs), zs_load, p_load_kNm2)
    if load_method == "distributed":
        for i in range(N - 1):
            p1 = float(p_at[i]); p2 = float(p_at[i + 1])
            if abs(p1) > 1e-9 or abs(p2) > 1e-9:
                model.add_member_dist_load(f"M{i}", "FY", w1=p1, w2=p2, x1=0.0, x2=dz)
    else:
        for i in range(N):
            p_i = float(p_at[i])
            F_i = p_i * dz / 2.0 if (i == 0 or i == N - 1) else p_i * dz
            if abs(F_i) > 1e-9: model.add_node_load(f"N{i}", "FY", F_i)
    try: model.analyze(check_statics=False, check_stability=False)
    except Exception as e: return {"error": f"PyNite: {e}"}
    res = _extract_results(model, N, pile, zs, k_h, f"PyNite-{load_method}")
    res["p_load_kNm2"] = p_at.tolist()
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Solver tham chiếu — anastruct (tải tập trung)
# ─────────────────────────────────────────────────────────────────────────────


def solve_anastruct(layers, pile, L_m, H_kNm, M_kNm=0.0, N=60,
                    eps50=0.02, k_sand_kNm3=10_000.0,
                    cdm_thickness_m=0.0, cdm_factor=3.0):
    # Legacy debug solver — production dùng winkler_np.py (Cloud Python 3.14)
    from anastruct.fem.system import SystemElements  # pyright: ignore[reportMissingImports]
    EI = pile.EI_kNm2
    zs, k_h = kh_profile(layers, pile, L_m, N, eps50, k_sand_kNm3,
                         cdm_thickness_m, cdm_factor)
    dz = L_m / (N - 1)
    ss = SystemElements(EA=1e9, EI=EI)
    for i in range(N - 1):
        ss.add_element(location=[[0, -zs[i]], [0, -zs[i + 1]]], EI=EI)
    for i in range(1, N + 1):
        ss.add_support_spring(node_id=i, translation=1, k=k_h[i - 1] * pile.D_m * dz)
    ss.point_load(node_id=1, Fx=H_kNm)
    if abs(M_kNm) > 0: ss.moment_load(node_id=1, Ty=M_kNm)
    ss.solve()
    disp = ss.get_node_displacements()  # pyright: ignore[reportCallIssue]
    ux_mm = [d["ux"] * 1000.0 for d in disp]
    er = ss.get_element_results(verbose=False)  # pyright: ignore[reportCallIssue]
    Ms = [e["Mmax"] for e in er]
    Qs = [e.get("wmax", 0) or e.get("qmax", 0) for e in er]
    return {
        "solver": "anastruct",
        "u_top_mm": ux_mm[0], "u_max_mm": max(abs(u) for u in ux_mm),
        "M_max_kNm": max(abs(m) for m in Ms) if Ms else 0.0,
        "Q_max_kN": max(abs(q) for q in Qs) if Qs else 0.0,
        "Mcr_kNm": pile.Mcr_kNm, "EI_kNm2": EI, "D_mm": pile.D_m * 1000,
        "zs": zs, "ux": ux_mm, "Ms": Ms, "Qs": Qs, "k_h": k_h,
    }


def compare(layers, pile, L_m, H_kNm, M_kNm=0.0, **kw):
    """So sánh PyNite vs anastruct (tải tập trung)."""
    r1 = solve_pynite(layers, pile, L_m, H_kNm, M_kNm, **kw)
    r2 = solve_anastruct(layers, pile, L_m, H_kNm, M_kNm, **kw)
    if "error" in r1 or "error" in r2:
        return {"pynite": r1, "anastruct": r2}
    print(f"\n{'Đại lượng':<22} {'PyNite':>14} {'anastruct':>14} {'Sai khác %':>12}")
    print("─" * 70)
    for key, label in [("u_top_mm", "u đỉnh (mm)"), ("u_max_mm", "|u| max (mm)"),
                       ("M_max_kNm", "M max (kNm)"), ("Q_max_kN", "Q max (kN)")]:
        a, b = r1[key], r2[key]
        diff_pct = (a - b) / b * 100.0 if abs(b) > 1e-9 else 0.0
        print(f"{label:<22} {a:>14.4f} {b:>14.4f} {diff_pct:>11.2f}%")
    return {"pynite": r1, "anastruct": r2}


# ─────────────────────────────────────────────────────────────────────────────
# DEMO: tải phân bố — KE-HK8 theo quy ước CLAUDE.md §20
# ─────────────────────────────────────────────────────────────────────────────


def _demo_distributed():
    """Demo KE-HK8 với điều kiện thực tế kè công viên TTHC.

    Quy ước:
        Front (TRÁI) = phía park — có đất đắp + xe/người
        Back  (PHẢI) = phía hồ Trung Tâm — đào xuống thấp, nước hở
    """
    pile = sw_pile_props(H_mm=840, Itd_cm4=2_125_017, Mcr_Tm=77.10,
                         Atd_cm2=3107, fc_MPa=70.0, name="SW-840")
    geom = WallGeometry(
        top_elev=2.7, pile_length=29.0,
        soil_level_front=0.0,    # Front: mặt đất tự nhiên (có fill 2.7m bên trên)
        soil_level_back=-1.0,    # Back: đáy đào (phía hồ, thấp hơn 1m)
        water_elev_front=-0.5,   # nước ngầm
        water_elev_back=-0.5,    # mặt hồ
        surcharge_front=10.0,    # tải hoạt xe/người 10 kPa
    )
    fill = EarthLayer(tip_elev=0.0, gamma=18.0, gamma_sub=8.0, phi=28.0, c=0.0)
    front_layers = [
        EarthLayer(tip_elev=-24.1, gamma=15.0, gamma_sub=5.0, phi=10.0, c=5.0),
        EarthLayer(tip_elev=-30.0, gamma=18.0, gamma_sub=8.0, phi=30.0, c=0.0),
    ]
    back_layers = [
        EarthLayer(tip_elev=-24.1, gamma=15.0, gamma_sub=5.0, phi=10.0, c=5.0),
        EarthLayer(tip_elev=-30.0, gamma=18.0, gamma_sub=8.0, phi=30.0, c=0.0),
    ]
    layers_kh = [
        SoilLayer("1", 24.1, Su_kPa=10.0, gamma_kNm3=15.0),
        SoilLayer("2b", 10.0, gamma_kNm3=18.0),
    ]

    print("=" * 70)
    print("DEMO KE-HK8 SW-840 L=29m — TẢI PHÂN BỐ THEO QUY ƯỚC §20")
    print("=" * 70)
    print(f"Đỉnh cừ:              {geom.top_elev:+.1f} m")
    print(f"Front (đắp, park):    {geom.soil_level_front:+.1f} m  "
          f"(fill {geom.fill_thickness:.1f} m + q={geom.surcharge_front:.0f} kPa)")
    print(f"Back  (đào, hồ):      {geom.soil_level_back:+.1f} m")
    print(f"Mực nước Front/Back:  {geom.water_elev_front:+.1f} / {geom.water_elev_back:+.1f} m")

    load = build_lateral_load(geom, front_layers, back_layers, fill=fill,
                              N=300, mode="winkler")
    print(f"\nLực tổng hợp dọc tường (kN/m chiều dài):")
    print(f"  F_active   (Front, đắp)  = {load['F_active']:8.1f}")
    print(f"  F_passive  (Back, đào)   = {load['F_passive']:8.1f}  [chỉ tham khảo — không vào tải mode Winkler]")
    print(f"  F_water_net               = {load['F_water_net']:8.1f}")
    print(f"  F_NET (Winkler)           = {load['F_net']:8.1f}")

    res = solve_pynite_dist(layers_kh, pile, 29.0,
                            zs_load=load["zs_depth_m"], p_load_kNm2=load["p_net"],
                            N=60, top_pin=True)
    print("\n(mô phỏng có dầm mũ headwall — pin support tại đỉnh)")

    if res.get("error"):
        print(f"\nLỖI: {res['error']}")
        return None

    print(f"\nKết quả nội lực Winkler:")
    print(f"  u đỉnh = {res['u_top_mm']:+8.2f} mm")
    print(f"  |u|max = {res['u_max_mm']:8.2f} mm  (giới hạn 25)")
    print(f"  M max  = {res['M_max_kNm']:8.1f} kNm (Mcr = {res['Mcr_kNm']:.0f})")
    print(f"  Q max  = {res['Q_max_kN']:8.1f} kN")
    u_ok = float(res["u_max_mm"]) < 25.0
    M_ok = float(res["M_max_kNm"]) < float(res["Mcr_kNm"])
    print(f"\nKiểm tra: u {'Đạt' if u_ok else 'KHÔNG ĐẠT'}, "
          f"M {'Đạt' if M_ok else 'KHÔNG ĐẠT'}")
    return {"load": load, "res": res, "geom": geom}


def _plot_distributed(demo, png_path):
    """4 panel: áp lực phân bố | u | M | Q. Front=TRÁI (đỏ), Back=PHẢI (xanh)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    load = demo["load"]; res = demo["res"]; geom = demo["geom"]
    if res.get("error"): return

    fig, ax = plt.subplots(1, 4, figsize=(17, 8), sharey=True)
    el = load["elevs"]

    # Panel 1: áp lực — Front = TRÁI (âm), Back = PHẢI (dương)
    # Active phía Front: đẩy về Back → vẽ phía âm (trái)
    ax[0].fill_betweenx(el, 0, -load["sigma_h_active"], alpha=0.4, color="tomato",
                        label="Active Front (đắp)")
    ax[0].fill_betweenx(el, 0, load["sigma_h_passive"], alpha=0.4, color="steelblue",
                        label="Passive Back (đào)")
    ax[0].plot(-load["sigma_h_active"], el, "r-", lw=1.5)
    ax[0].plot(load["sigma_h_passive"], el, "b-", lw=1.5)
    ax[0].plot(-load["p_water_front"], el, "m--", lw=1.2, label="Water Front")
    ax[0].plot(load["p_water_back"], el, "c--", lw=1.2, label="Water Back")
    # Net dương → đẩy Back: vẽ bên phải dương
    ax[0].plot(-load["p_net"], el, "k-", lw=2.5, label="NET = A_front − P_back")
    for y, c, lbl in [(geom.soil_level_front, "brown", "Front gr. (đắp)"),
                      (geom.soil_level_back, "orange", "Back gr. (đào)"),
                      (geom.water_elev_front, "cyan", "MNN")]:
        ax[0].axhline(y, color=c, linestyle=":", alpha=0.7, label=lbl)
    ax[0].axvline(0, color="black", lw=0.5)
    ax[0].set_xlabel("σ_h (kN/m²)  ← Front | Back →")
    ax[0].set_ylabel("Cao độ (m)")
    ax[0].set_title("Áp lực ngang phân bố")
    ax[0].grid(alpha=0.3)
    ax[0].legend(fontsize=7, loc="lower right")

    # Panel 2: u(z)
    zs = res["zs"]
    el_pile = [geom.top_elev - z for z in zs]
    ax[1].plot(res["ux"], el_pile, "b-", lw=2)
    ax[1].axvline(25, color="orange", linestyle=":", label="±25 mm")
    ax[1].axvline(-25, color="orange", linestyle=":")
    for y, c in [(geom.soil_level_front, "brown"),
                 (geom.soil_level_back, "orange"),
                 (geom.water_elev_front, "cyan")]:
        ax[1].axhline(y, color=c, linestyle=":", alpha=0.5)
    ax[1].set_xlabel("u (mm)  →")
    ax[1].set_title("Chuyển vị u(z)")
    ax[1].grid(alpha=0.3)
    ax[1].legend(fontsize=8)

    # Panel 3: M(z)
    el_mid = [geom.top_elev - (zs[i] + zs[i + 1]) / 2 for i in range(len(zs) - 1)]
    ax[2].plot(res["Ms"], el_mid, "g-", lw=2)
    ax[2].axvline(res["Mcr_kNm"], color="red", linestyle=":",
                  label=f"Mcr={res['Mcr_kNm']:.0f}")
    ax[2].axvline(-res["Mcr_kNm"], color="red", linestyle=":")
    for y, c in [(geom.soil_level_front, "brown"), (geom.soil_level_back, "orange")]:
        ax[2].axhline(y, color=c, linestyle=":", alpha=0.5)
    ax[2].set_xlabel("M (kNm)")
    ax[2].set_title("Moment M(z)")
    ax[2].grid(alpha=0.3)
    ax[2].legend(fontsize=8)

    # Panel 4: Q(z)
    ax[3].plot(res["Qs"], el_mid, "m-", lw=2)
    for y, c in [(geom.soil_level_front, "brown"), (geom.soil_level_back, "orange")]:
        ax[3].axhline(y, color=c, linestyle=":", alpha=0.5)
    ax[3].set_xlabel("Q (kN)")
    ax[3].set_title("Lực cắt Q(z)")
    ax[3].grid(alpha=0.3)

    fig.suptitle(
        f"KE-HK8 SW-840 L=29m — Quy ước §20: Front(TRÁI)=đắp+xe | Back(PHẢI)=đào+hồ\n"
        f"F_NET = {load['F_net']:.0f} kN/m  |  u_top = {res['u_top_mm']:+.1f} mm  |  "
        f"M_max = {res['M_max_kNm']:.0f} kNm",
        fontsize=11, fontweight="bold",
    )
    plt.tight_layout()
    plt.savefig(png_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"\nBiểu đồ đã lưu: {png_path}")


# ─────────────────────────────────────────────────────────────────────────────
# SQLite persistence — bảng ke_sw_winkler_results
# ─────────────────────────────────────────────────────────────────────────────
#
# Schema tối thiểu theo yêu cầu (CLAUDE.md §5 — SQLite bắt buộc cho mọi kết quả
# kỹ thuật). Lưu sau mỗi lần solve để app/báo cáo PDF không phụ thuộc Word.
#
# PRIMARY KEY (bh_name, pile_type, L_m, load_case)
#   load_case: 'concentrated' (H+M tại đỉnh) | 'distributed' (Front-Back tự động)
# Idempotent: INSERT OR REPLACE — chạy lại cùng cấu hình ghi đè kết quả cũ.


_DEFAULT_DB_PATH = None  # lazy resolve trong _resolve_db_path()


def _resolve_db_path(db_path=None) -> str:
    """Trả về path tới TTHC.sqlite — default = data/TTHC.sqlite cạnh repo."""
    if db_path:
        return str(db_path)
    from pathlib import Path
    here = Path(__file__).resolve().parent.parent
    return str(here / "data" / "TTHC.sqlite")


def create_winkler_results_table(db_path=None) -> None:
    """Tạo bảng ke_sw_winkler_results (idempotent)."""
    import sqlite3
    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS ke_sw_winkler_results (
            bh_name      TEXT NOT NULL,
            pile_type    TEXT NOT NULL,
            L_m          REAL NOT NULL,
            load_case    TEXT NOT NULL DEFAULT 'concentrated',
            u_top_mm     REAL,
            u_max_mm     REAL,
            M_max_kNm    REAL,
            Mcr_kNm      REAL,
            Q_max_kN     REAL,
            EI_kNm2      REAL,
            D_mm         REAL,
            H_load_kN    REAL,
            M_load_kNm   REAL,
            mcr_ratio    REAL,
            u_ok         INTEGER,
            mcr_ok       INTEGER,
            solver       TEXT,
            ts           TEXT NOT NULL,
            PRIMARY KEY (bh_name, pile_type, L_m, load_case)
        )
        """)
        con.commit()


def save_winkler_results_to_db(
    result: dict,
    bh_name: str,
    pile_type: str,
    L_m: float,
    load_case: str = "concentrated",
    H_load_kN: float = 0.0,
    M_load_kNm: float = 0.0,
    u_limit_mm: float = 50.0,
    db_path=None,
) -> bool:
    """Lưu 1 result Winkler vào bảng ke_sw_winkler_results.

    result: dict trả về từ solve_pynite/solve_pynite_dist/solve_numpy/solve_numpy_dist
            phải có các key: u_top_mm, u_max_mm, M_max_kNm, Mcr_kNm, Q_max_kN
    bh_name: tên hố khoan ĐẦY ĐỦ (vd 'KE-HK1') — quy ước CLAUDE.md §10
    pile_type: 'SW-600', 'SW-740', ...
    load_case: 'concentrated' | 'distributed'

    Returns: True nếu lưu OK, False nếu skip (result có error hoặc thiếu key).
    """
    import sqlite3
    from datetime import datetime

    if not result or "error" in result:
        return False
    required = ("u_top_mm", "u_max_mm", "M_max_kNm", "Mcr_kNm", "Q_max_kN")
    if not all(k in result for k in required):
        return False

    create_winkler_results_table(db_path)  # idempotent guard

    u_top = float(result["u_top_mm"])
    u_max = float(result["u_max_mm"])
    M_max = float(result["M_max_kNm"])
    Mcr   = float(result["Mcr_kNm"])
    Q_max = float(result["Q_max_kN"])
    EI    = float(result.get("EI_kNm2", 0.0))
    D_mm  = float(result.get("D_mm", 0.0))
    solver = str(result.get("solver", ""))
    ratio = (M_max / Mcr) if Mcr > 0 else 0.0
    u_ok = 1 if abs(u_max) < u_limit_mm else 0
    mcr_ok = 1 if (Mcr > 0 and M_max < Mcr) else 0

    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as con:
        con.execute("""
        INSERT OR REPLACE INTO ke_sw_winkler_results
          (bh_name, pile_type, L_m, load_case,
           u_top_mm, u_max_mm, M_max_kNm, Mcr_kNm, Q_max_kN,
           EI_kNm2, D_mm, H_load_kN, M_load_kNm,
           mcr_ratio, u_ok, mcr_ok, solver, ts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            bh_name, pile_type, float(L_m), load_case,
            u_top, u_max, M_max, Mcr, Q_max,
            EI, D_mm, float(H_load_kN), float(M_load_kNm),
            ratio, u_ok, mcr_ok, solver,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        con.commit()
    return True


def load_winkler_results(bh_name=None, db_path=None) -> list[dict]:
    """Đọc kết quả Winkler từ DB. Filter theo bh_name nếu truyền."""
    import sqlite3
    path = _resolve_db_path(db_path)
    create_winkler_results_table(db_path)
    sql = "SELECT * FROM ke_sw_winkler_results"
    params: tuple = ()
    if bh_name:
        sql += " WHERE bh_name = ?"
        params = (bh_name,)
    sql += " ORDER BY bh_name, pile_type, L_m"
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import sys
    out_png = sys.argv[1] if len(sys.argv) > 1 else "wall_demo_distributed.png"
    d = _demo_distributed()
    if d:
        try:
            _plot_distributed(d, out_png)
        except ImportError:
            print("(matplotlib không có)")
