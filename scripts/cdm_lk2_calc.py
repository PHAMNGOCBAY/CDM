# -*- coding: utf-8 -*-
"""Engine tái lập 100% bảng tính lún khối móng CDM — file 'TINH MONG TRU CDM - LK2.xlsx'.

Port trực tiếp từng cột công thức của sheet '(1)' (BẢNG TÍNH LÚN KHỐI MÓNG) sang Python,
để đổi input → tính lại sống mà vẫn khớp Excel < 1e-6.

Chuỗi công thức (TCVN 9403:2012 Phụ lục C + 22TCN 262-2000):
  - Hệ số cải tạo:   a = Ac / A_unit ;  Ac = π(D/2)² ;  A_unit = S² (vuông) | S²·√3/2 (tam giác)
  - Mô đun trụ:      Ecol = factor·quck/2          (factor mặc định 100)
  - Mô đun đất:      Esoil_i = E_i  (bảng địa chất, E = 200·Cu)
  - Mô đun tương đương khối: Eeq = Σ(M_i·g_i)/Σ g_i ;  M_i = Ecol·a + Esoil_i·(1−a)
                      g_i = bề dày sublayer NẰM TRONG khối gia cố [CD2 .. CD1]
  - Lún khối:        Sblock = P · L / Eeq          (L = CD1 − CD2 ; P = tải đắp KHÔNG hoạt tải)
  - Lún cố kết dưới mũi (mỗi sublayer có cao độ đáy < CD2):
        σ'vz   = Σ γ·h tới giữa sublayer (γ = γdn nếu dưới MNN)
        Δσ     = P                       nếu trên mũi cọc (z_bot ≥ CD2)
               = P·W / (2·z'·tanθ + W)   nếu dưới mũi (z' = bề dày tích luỹ dưới mũi tới đáy sublayer)
        σ'pz   = spz (áp lực tiền cố kết, bảng địa chất)
        nhánh:  NC      (σ'vz > σ'pz):  S = h/(1+e0)·Cc·log10((Δσ+σ'vz)/σ'pz)
                cross   (σ'vz<σ'pz<Δσ+σ'vz): S = h/(1+e0)·Cr·log10(σ'pz/σ'vz) + h/(1+e0)·Cc·log10((Δσ+σ'vz)/σ'pz)
                OC      (Δσ+σ'vz ≤ σ'pz): S = h/(1+e0)·Cr·log10((Δσ+σ'vz)/σ'vz)
  - Tổng lún:        S = Sblock + Sc

Nguồn dữ liệu LK2: data/lk2_cdm_settlement.json (trích từ file Excel gốc).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_JSON = _ROOT / "data" / "lk2_cdm_settlement.json"

# Ký hiệu lớp hạt rời (cát) — không nén cố kết theo Cc trong engine LK2
SAND_SYMBOLS_LK2 = {"F", "2a", "2b", "2c", "3a", "3b", "3c", "4", "5", "5a", "5b", "6", "7", "8"}

# Tiêu chí dừng vùng ảnh hưởng lún: chỉ tính cố kết khi Δσ ≥ 10%·σ'v0 (TCCS 41 / §71)
INFLUENCE_STOP_RATIO = 0.10


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class SubLayer:
    """Một phân tố địa chất (1 dòng bảng địa tầng)."""

    h: float                 # bề dày (m)
    z_bot_elev: float        # cao độ đáy (m)
    gamma: float             # dung trọng tự nhiên (kN/m³)
    gamma_dn: float          # dung trọng đẩy nổi (kN/m³)
    Cu: float                # cường độ cắt không thoát nước (kN/m²)
    e0: float                # hệ số rỗng
    Cc: float                # chỉ số nén
    Cr: float                # chỉ số nở (recompression)
    E: float                 # mô đun biến dạng đất (kN/m²)
    spz: float               # áp lực tiền cố kết σ'pz (kN/m²)
    soil: str = "Sét"
    layer: object = 1


@dataclass
class LK2Inputs:
    D_m: float = 0.8            # đường kính trụ
    S_m: float = 1.8           # khoảng cách trụ
    pattern: int = 1           # 1=vuông, 2=tam giác
    quck: float = 800.0        # cường độ trụ thiết kế (kN/m²)
    Fs: float = 1.0            # hệ số an toàn cường độ
    Ecol_factor: float = 100.0 # Ecol = factor·quck/2
    CD1_top_pile: float = 1.35 # cao độ đỉnh trụ (m)
    CD2_bot_pile: float = -9.65  # cao độ đáy trụ (m)
    W_group: float = 20.0      # bề rộng nhóm trụ (m)
    theta_deg: float = 30.0    # góc phân tán ứng suất (độ)
    water_elev: float = 1.8    # cao độ mực nước ngầm (m)
    P_fill: float = 21.3       # tải đắp KHÔNG hoạt tải (kN/m²) — dùng tính lún
    q_total: float = 36.774    # tải CÓ hoạt tải (kN/m²) — dùng tính sức chịu tải
    a_pier: float = 0.4        # hệ số triết giảm sức chống mũi (D.9)
    qsi: float = 5.0           # lực ma sát thành cho phép (kN/m²)


@dataclass
class SubResult:
    idx: int
    symbol: object
    Cu: float
    Esoil: float
    h: float
    z_bot_elev: float
    in_block_thickness: float   # g_i — bề dày trong khối gia cố
    M_eq: float                 # M_i = Ecol·a + Esoil·(1−a)
    sigma_vz: float             # σ'vz giữa phân tố
    z_below_tip: float          # z' — bề dày tích luỹ dưới mũi
    dsigma: float               # Δσ
    sigma_pz: float             # σ'pz
    branch: str                 # 'block' | 'NC' | 'cross' | 'OC' | '-'
    Sc_m: float                 # lún cố kết phân tố (m)


@dataclass
class LK2Result:
    Ac: float
    A_unit: float
    a_ratio: float
    Ecol: float
    Eeq: float
    L_pile: float
    Sblock_m: float
    Sc_m: float
    S_total_m: float
    sublayers: list = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Core engine
# --------------------------------------------------------------------------- #
def calc_area_ratio(D: float, S: float, pattern: int) -> tuple[float, float, float]:
    """Trả về (Ac, A_unit, a)."""
    Ac = math.pi * (D / 2.0) ** 2
    if pattern == 1:
        A_unit = S ** 2
    elif pattern == 2:
        A_unit = S ** 2 * math.sqrt(3) / 2.0
    else:
        raise ValueError("pattern phải là 1 (vuông) hoặc 2 (tam giác)")
    return Ac, A_unit, Ac / A_unit


def _block_overlap(z_top: float, z_bot: float, cd1_top: float, cd2_bot: float) -> float:
    """Bề dày sublayer nằm trong khối gia cố [cd2_bot .. cd1_top] — port công thức G97."""
    if z_bot < cd2_bot:
        return 0.0
    if z_top > cd1_top and z_bot < cd1_top:
        return abs(cd1_top - z_bot)
    if z_top < cd1_top:
        return z_bot if False else (z_top - z_bot)  # = h (z_top - z_bot)
    return 0.0


def compute_lk2(inp: LK2Inputs, geology: list[SubLayer],
                sand_elastic: bool = False, extend_below_bh: bool = False,
                max_extend_m: float = 80.0) -> LK2Result:
    """Tính toàn bộ lún khối móng CDM theo sheet (1).

    sand_elastic=True (§71): lớp cát + sét chặt (Cc=0) DƯỚI mũi cộng lún đàn hồi Si=Δσ·h/E.
    extend_below_bh=True (§71): mở rộng tích phân DƯỚI đáy hố khoan (dùng thông số lớp cuối)
        tới khi Δσ/σ'v0 < 10% — đáy vùng ảnh hưởng. (Mặc định TẮT để khớp hồ sơ Excel gốc.)
    """
    Ac, A_unit, a = calc_area_ratio(inp.D_m, inp.S_m, inp.pattern)
    Ecol = inp.Ecol_factor * inp.quck / 2.0
    L_pile = inp.CD1_top_pile - inp.CD2_bot_pile
    tan_t = math.tan(math.radians(inp.theta_deg))

    # Mở rộng địa tầng dưới đáy hố khoan bằng thông số lớp cuối (§71)
    if extend_below_bh and geology:
        last = geology[-1]
        z = last.z_bot_elev
        _sub = 2.0
        ext = []
        for _ in range(int(max_extend_m / _sub)):
            z -= _sub
            ext.append(SubLayer(h=_sub, z_bot_elev=round(z, 3), gamma=last.gamma,
                       gamma_dn=last.gamma_dn, Cu=last.Cu, e0=last.e0, Cc=last.Cc,
                       Cr=last.Cr, E=last.E, spz=last.spz, soil=last.soil, layer=last.layer))
        geology = list(geology) + ext

    subs: list[SubResult] = []

    # --- σ'vz cumulative (tính giữa từng phân tố từ đỉnh profile) ---
    cum_full = 0.0          # Σ γ·h của các phân tố hoàn chỉnh phía trên
    cum_below_tip = 0.0     # z' tích luỹ dưới mũi
    sum_Mg = 0.0
    sum_g = 0.0
    Sc_total = 0.0

    for i, ly in enumerate(geology):
        z_bot = ly.z_bot_elev
        z_top = z_bot + ly.h
        # γ hiệu dụng: dưới MNN -> đẩy nổi
        g_eff = ly.gamma_dn if z_bot <= inp.water_elev else ly.gamma
        sigma_vz = cum_full + g_eff * ly.h / 2.0
        cum_full += g_eff * ly.h

        # --- Eeq (khối gia cố) ---
        g_blk = _block_overlap(z_top, z_bot, inp.CD1_top_pile, inp.CD2_bot_pile)
        Esoil = ly.E
        M_eq = Ecol * a + Esoil * (1.0 - a) if g_blk > 0 else 0.0
        if g_blk > 0:
            sum_Mg += M_eq * g_blk
            sum_g += g_blk

        # --- Δσ + lún cố kết (chỉ phân tố dưới mũi) ---
        branch = "-"
        dsigma = 0.0
        Sc_i = 0.0
        z_below = 0.0
        if z_bot < inp.CD2_bot_pile:
            cum_below_tip += ly.h
            z_below = cum_below_tip
            dsigma = inp.P_fill * inp.W_group / (2.0 * z_below * tan_t + inp.W_group)
            spz = ly.spz
            # Vùng ảnh hưởng lún (TCCS 41/§71): chỉ tính khi Δσ ≥ 10%·σ'v0
            if sigma_vz > 0 and dsigma < INFLUENCE_STOP_RATIO * sigma_vz:
                branch = "ngoài vùng ảnh hưởng"
            elif ly.Cc <= 0:
                # Lớp cát / sét chặt (Cc=0) → lún đàn hồi Si=Δσ·h/E (§71) nếu bật sand_elastic
                if sand_elastic and ly.E > 0:
                    branch = "đàn hồi (cát/sét chặt)"
                    Sc_i = dsigma * ly.h / ly.E
                    Sc_total += Sc_i
                else:
                    branch = "cát (bỏ qua)"
            else:
                fac = ly.h / (1.0 + ly.e0)
                sig_f = dsigma + sigma_vz
                if sigma_vz > spz:          # NC
                    branch = "NC"
                    Sc_i = fac * ly.Cc * math.log10(sig_f / spz)
                elif sig_f > spz:           # cross-PC
                    branch = "cross"
                    Sc_i = fac * ly.Cr * math.log10(spz / sigma_vz) + fac * ly.Cc * math.log10(sig_f / spz)
                else:                       # OC
                    branch = "OC"
                    Sc_i = fac * ly.Cr * math.log10(sig_f / sigma_vz)
                Sc_total += Sc_i
        elif g_blk > 0:
            branch = "block"

        subs.append(SubResult(
            idx=i + 1, symbol=ly.layer, Cu=ly.Cu, Esoil=ly.E, h=ly.h, z_bot_elev=z_bot,
            in_block_thickness=g_blk, M_eq=M_eq, sigma_vz=sigma_vz, z_below_tip=z_below,
            dsigma=dsigma, sigma_pz=ly.spz, branch=branch, Sc_m=Sc_i,
        ))

    Eeq = sum_Mg / sum_g if sum_g else 0.0
    Sblock = inp.P_fill / Eeq * L_pile if Eeq else 0.0
    Sc = round(Sc_total, 3)   # Excel P180 = ROUND(...,3)
    S_total = Sblock + Sc

    return LK2Result(
        Ac=Ac, A_unit=A_unit, a_ratio=a, Ecol=Ecol, Eeq=Eeq, L_pile=L_pile,
        Sblock_m=Sblock, Sc_m=Sc, S_total_m=S_total, sublayers=subs,
    )


# --------------------------------------------------------------------------- #
# Sức chịu tải cọc (sheet SCT)
# --------------------------------------------------------------------------- #
@dataclass
class SCTResult:
    Ap: float
    Etd: float            # mô đun tương đương (L51/H51)
    Cu_soil: float        # Cu trung bình khối (K51/H51)
    Esoil_avg: float      # Esoil trung bình (J51/H51)
    N_load: float         # tải lên 1 cọc = q·s²
    Nvl: float            # SCT theo vật liệu = qa·Ap
    Ndn: float            # SCT theo đất nền = a·Ap·qp + π·d·qsi·L
    Nc: float             # min(Nvl, Ndn)
    qp: float             # sức chống mũi = 6·Cu
    ratio_Nc_N: float     # Nc / N
    ok_capacity: bool     # N <= Nc
    sigma_col: float      # ứng suất tập trung lên cọc = Ecol/Etd·q
    Pcol: float           # tải tập trung lên cọc = σ_col·Ap
    Qult_col_AIT: float   # AIT theo vật liệu
    Qult_soil_AIT: float  # AIT theo đất nền
    Qa_soil: float        # SCT cho phép (AIT đất) = Qult_soil/FS
    ok_AIT: bool          # Pcol <= Qa_soil


def compute_sct(inp: LK2Inputs, geology: list[SubLayer], Ecol: float, a: float) -> SCTResult:
    """Port sheet SCT — sức chịu tải cọc CDM. Dùng q CÓ hoạt tải."""
    Ap = math.pi * (inp.D_m / 2.0) ** 2
    cd2 = inp.CD2_bot_pile
    cd1 = inp.CD1_top_pile

    # --- Trung bình khối (port L51/J51/K51/H51) ---
    sum_Mg = 0.0          # Σ M_eq·g_blk  (L51)
    sum_hE = 0.0          # Σ h·Esoil (z_bot>=cd2)  (J51)
    sum_hCu = 0.0         # Σ h·Cu     (z_bot>=cd2)  (K51)
    max_depth = 0.0       # MAX cumulative depth (z_bot>=cd2)  (H51)
    cum_depth = 0.0
    Cu_tip = geology[0].Cu
    for ly in geology:
        cum_depth += ly.h
        z_bot = ly.z_bot_elev
        z_top = z_bot + ly.h
        g_blk = _block_overlap(z_top, z_bot, cd1, cd2)
        M_eq = Ecol * a + ly.E * (1.0 - a) if g_blk > 0 else 0.0
        sum_Mg += M_eq * g_blk
        if z_bot >= cd2:
            sum_hE += ly.h * ly.E
            sum_hCu += ly.h * ly.Cu
            max_depth = max(max_depth, cum_depth)
            Cu_tip = ly.Cu   # Cu của lớp sâu nhất trong khối (tại mũi)

    Etd = sum_Mg / max_depth if max_depth else 0.0
    Cu_soil = sum_hCu / max_depth if max_depth else 0.0
    Esoil_avg = sum_hE / max_depth if max_depth else 0.0

    L_pile = cd1 - cd2
    qa_mat = inp.quck / inp.Fs                 # cường độ vật liệu cho phép
    N_load = inp.q_total * inp.S_m ** 2        # tải lên 1 cọc = q·s²
    Nvl = qa_mat * Ap
    qp = 6.0 * Cu_tip                          # mũi trong sét: qp = 6·Cu
    Ndn = inp.a_pier * Ap * qp + math.pi * inp.D_m * inp.qsi * L_pile
    Nc = min(Nvl, Ndn)

    sigma_col = Ecol / Etd * inp.q_total if Etd else 0.0
    Pcol = sigma_col * Ap

    Qult_col = Ap * (3.5 * inp.quck + 3.0 * (inp.q_total + 5.0 * Cu_soil))
    Qult_soil = (math.pi * inp.D_m * L_pile + 2.25 * math.pi * inp.D_m ** 2) * Cu_soil
    Qa_soil = Qult_soil / inp.Fs

    return SCTResult(
        Ap=Ap, Etd=Etd, Cu_soil=Cu_soil, Esoil_avg=Esoil_avg,
        N_load=N_load, Nvl=Nvl, Ndn=Ndn, Nc=Nc, qp=qp,
        ratio_Nc_N=Nc / N_load if N_load else 0.0, ok_capacity=N_load <= Nc,
        sigma_col=sigma_col, Pcol=Pcol,
        Qult_col_AIT=Qult_col, Qult_soil_AIT=Qult_soil, Qa_soil=Qa_soil,
        ok_AIT=Pcol <= Qa_soil,
    )


# --------------------------------------------------------------------------- #
# Lún theo thời gian (sheet (2)) — cố kết Terzaghi
# --------------------------------------------------------------------------- #
_YEAR_SECONDS = 12 * 30 * 24 * 60 * 60   # 31_104_000 s (quy ước Excel: 360 ngày)


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    """Nội suy tuyến tính có kẹp đầu/cuối (mô phỏng TLOOKUP)."""
    pts = sorted((a, b) for a, b in zip(xs, ys) if a is not None and b is not None)
    if not pts:
        return 0.0
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y0
    return pts[-1][1]


@dataclass
class TimeHistoryResult:
    H_drain_m: float
    Ctbv_cm2s: float
    Sc_cm: float
    years: list = field(default_factory=list)
    Tv: list = field(default_factory=list)
    Uv: list = field(default_factory=list)
    St_cm: list = field(default_factory=list)
    residual_cm: list = field(default_factory=list)
    allowable_cm: float = 40.0
    design_time_idx: int = 1          # cột dùng để so sánh (E = t=1 năm)
    residual_check_cm: float = 0.0
    ok: bool = True


def compute_time_history(
    res: LK2Result,
    P_cv: list[float], Cv_vals: list[float],
    Tv_tab: list[float], U_tab: list[float],
    years: list[float],
    allowable_cm: float = 40.0,
    design_time_idx: int = 1,
) -> TimeHistoryResult:
    """Port sheet (2): cố kết theo thời gian. Cvi = nội suy(σ'vf)·1e-3 cm²/s."""
    H_drain = 0.0
    sum_term = 0.0    # Σ h·100/√Cvi
    for s in res.sublayers:
        if s.branch in ("NC", "cross", "OC"):       # phân tố cố kết (dưới mũi)
            sig_vf = s.sigma_vz + s.dsigma
            Cvi = _interp(P_cv, Cv_vals, sig_vf) * 1e-3
            H_drain += s.z_below_tip
            if Cvi > 0:
                sum_term += s.h * 100.0 / math.sqrt(Cvi)

    Ctbv = (H_drain * 100.0) ** 2 / sum_term ** 2 if sum_term else 0.0
    Sc_cm = round(res.Sc_m, 3) * 100.0

    Tv_list, Uv_list, St_list, resid_list = [], [], [], []
    for t in years:
        Tv = Ctbv / (H_drain * 100.0) ** 2 * t * _YEAR_SECONDS if H_drain else 0.0
        Uv = _interp(Tv_tab, U_tab, Tv) / 100.0
        St = round(Uv * Sc_cm, 4)
        Tv_list.append(Tv); Uv_list.append(Uv); St_list.append(St)
        resid_list.append(Sc_cm - St)

    idx = min(design_time_idx, len(resid_list) - 1)
    resid_check = resid_list[idx]
    return TimeHistoryResult(
        H_drain_m=H_drain, Ctbv_cm2s=Ctbv, Sc_cm=Sc_cm,
        years=list(years), Tv=Tv_list, Uv=Uv_list, St_cm=St_list, residual_cm=resid_list,
        allowable_cm=allowable_cm, design_time_idx=idx,
        residual_check_cm=resid_check, ok=resid_check <= allowable_cm,
    )


# --------------------------------------------------------------------------- #
# Kiểm toán lớp bê tông C10 (sheet KIEM TOAN) + Giới hạn lún
# --------------------------------------------------------------------------- #
@dataclass
class ConcreteCheckResult:
    Mtt: float            # mô men yêu cầu (kNm) = q(S-d)²/8
    Vtt: float            # lực cắt yêu cầu (kN)  = q(S-d)/2
    sigma_flex_MPa: float # cường độ chịu kéo khi uốn [σ] = 0.63√f'c
    Vr: float             # sức kháng cắt cho phép (kN) — 0 nếu dv=0
    Mr: float             # sức kháng uốn cho phép (kNm) — 0 nếu dv=0
    dv_m: float
    ok_shear: bool
    ok_moment: bool


def compute_concrete_check(
    D: float, S: float, q: float, dv_m: float,
    fc_MPa: float = 8.0, bv_mm: float = 1000.0, Rbt_MPa: float = 0.4,
    alpha: float = 1.0, b_coef: float = 2.0, phi: float = 0.9,
) -> ConcreteCheckResult:
    """Port sheet KIEM TOAN — kiểm toán cắt+uốn lớp bê tông (TCVN 11823-5 / TCVN 5574).
    LK2: dv=0 (không có lớp bê tông) → sức kháng = 0. Có dv>0 thì tính sống."""
    Mtt = round(q * (S - D) ** 2 / 8.0, 2)
    Vtt = round(q * (S - D) / 2.0, 2)
    sigma_flex = 0.63 * math.sqrt(fc_MPa)

    dv = dv_m * 1000.0   # mm
    if dv > 0:
        Vn1 = 0.25 * fc_MPa * 1e3 * (bv_mm * dv) * 1e-6
        Vn2 = 0.083 * b_coef * math.sqrt(fc_MPa) * 1e3 * bv_mm * dv * 1e-6
        Vn3 = (0.17 + 0.33 / (bv_mm / dv)) * math.sqrt(fc_MPa) * 1e3 * (bv_mm + dv) * 2 / 1e3 * dv / 1e3
        Vn4 = 0.33 * math.sqrt(fc_MPa) * 1e3 * (bv_mm + dv) * 2 / 1e3 * dv / 1e3
        Vr = round(phi * min(Vn1, Vn2, Vn3, Vn4), 1)
        Wpl = bv_mm * dv ** 2 / 3.5
        Mr1 = round(alpha * Rbt_MPa * Wpl / 1e6, 2)
        Zse = 1.0 / 6.0 * (bv_mm / 1e3) * (dv / 1e3) ** 2
        Mr2 = round(sigma_flex * Zse * 1e3, 2)
        Mr = min(Mr1, Mr2)
    else:
        Vr = 0.0
        Mr = 0.0

    return ConcreteCheckResult(
        Mtt=Mtt, Vtt=Vtt, sigma_flex_MPa=sigma_flex, Vr=Vr, Mr=Mr, dv_m=dv_m,
        ok_shear=(Vtt <= Vr), ok_moment=(Mtt <= Mr),
    )


# Bảng giới hạn lún cố kết còn lại (cm) — TCCS 41:2022 (sheet 'Gioihan lun')
SETTLEMENT_LIMITS = {
    "header": ["Gần mố cầu", "Chỗ có cống / đường dân sinh", "Đoạn nền đắp thông thường"],
    "Đường cao tốc và cấp I–IV": [10, 20, 30],
    "Đường cấp 60 trở xuống": [20, 30, 40],
}


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def build_geology_from_bh(bh_name: str, sublayer_m: float = 2.0,
                          db_path: Optional[Path] = None) -> tuple[list[SubLayer], float]:
    """Dựng địa tầng (list[SubLayer]) cho engine LK2 từ dữ liệu hố khoan trong SQLite.

    Chia phân tố `sublayer_m` (mặc định 1 m); mỗi phân tố gán chỉ tiêu từ **mẫu lab gần
    nhất** của hố (gamma, e0, Cc, Cs, PC, E, Cu); thiếu → mượn trung bình lớp (vùng×ký hiệu).
    Trả về (geology, cao_độ_tự_nhiên).
    """
    import math
    import sqlite3

    # Ưu tiên DB cục bộ (ngoài Drive, tránh sync corrupt) — đồng nhất với module khác
    if db_path:
        db = str(db_path)
    else:
        _local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
        db = str(_local if _local.exists() else (_ROOT / "data" / "TTHC.sqlite"))
    con = sqlite3.connect(db)
    cur = con.cursor()
    row = cur.execute("SELECT id, elevation_m FROM boreholes WHERE name=?", (bh_name,)).fetchone()
    if not row:
        con.close()
        raise ValueError(f"Không tìm thấy hố khoan {bh_name}")
    bh_id, elev = row[0], (row[1] or 0.0)
    layers = cur.execute(
        "SELECT symbol, depth_top_m, depth_bot_m FROM layers WHERE borehole_id=? "
        "AND symbol IS NOT NULL ORDER BY depth_top_m", (bh_id,)).fetchall()
    samples = cur.execute(
        "SELECT (depth_from_m+COALESCE(depth_to_m,depth_from_m+1.0))/2.0, gamma_kNm3, e0, Cc, "
        "Cs, PC_kPa, E_kPa, Cu_UU_kPa, c_kPa, gamma_sub_kNm3 FROM lab_tests WHERE borehole_id=? "
        "ORDER BY depth_from_m", (bh_id,)).fetchall()
    con.close()
    if not layers:
        raise ValueError(f"Hố khoan {bh_name} chưa có địa tầng")

    # fallback trung bình lớp theo vùng
    zone = "KE" if bh_name.startswith("KE-") else ("BXN" if bh_name.startswith("BXN") else
            ("NHC" if bh_name.startswith("NHC") else ("QTT" if bh_name.startswith("ND-") else "?")))
    try:
        from soil_param_stats import representative_params
        rep = representative_params(db_path)
    except Exception:
        rep = {}

    FIELD_IDX = {"gamma": 1, "e0": 2, "Cc": 3, "Cs": 4, "PC": 5, "E": 6, "Cu": 7, "c": 8, "gsub": 9}

    def _nearest(mid, idx):
        best, bd = None, 1e18
        for s in samples:
            v = s[idx]
            if v is None or v == 0:
                continue
            d = abs(s[0] - mid)
            if d < bd:
                bd, best = d, v
        return best

    def _sym_at(depth):
        for sym, t, b in layers:
            if t <= depth <= b:
                return sym
        return layers[-1][0]

    max_depth = max(b for _, _, b in layers)
    n = int(math.ceil(max_depth / sublayer_m))
    geo: list[SubLayer] = []
    for i in range(n):
        d_top = i * sublayer_m
        d_bot = min((i + 1) * sublayer_m, max_depth)
        h = d_bot - d_top
        if h <= 0:
            continue
        mid = (d_top + d_bot) / 2.0
        sym = _sym_at(mid)
        rp = rep.get((zone, sym), {}) if rep else {}
        gamma = _nearest(mid, FIELD_IDX["gamma"]) or rp.get("gamma_kNm3") or 16.0
        gsub = _nearest(mid, FIELD_IDX["gsub"])
        gamma_dn = gsub if gsub else (gamma - 9.81)
        Cu = _nearest(mid, FIELD_IDX["Cu"]) or _nearest(mid, FIELD_IDX["c"]) or rp.get("Cu_UU_kPa") or 10.0
        e0 = _nearest(mid, FIELD_IDX["e0"]) or rp.get("e0") or 1.5
        Cc = _nearest(mid, FIELD_IDX["Cc"]) or rp.get("Cc") or 0.5
        Cr = _nearest(mid, FIELD_IDX["Cs"]) or rp.get("Cs") or (Cc * 0.15)
        E = 250.0 * Cu   # Es = 250·Cu (tương quan Mesri & Olson 1974)
        spz = _nearest(mid, FIELD_IDX["PC"]) or rp.get("PC_kPa") or max(Cu * 4.0, 10.0)
        # Engine LK2 chỉ có nhánh nén cố kết (Cc-log) cho SÉT YẾU.
        # Lớp CÁT hoặc SÉT CHẶT (e0<1) → KHÔNG cố kết Cc → đặt Cc=Cr=0 (Si=0),
        # đồng bộ quy tắc "lún cố kết chỉ ở sét e0>1".
        if (sym in SAND_SYMBOLS_LK2) or (e0 is not None and e0 < 1.0):
            Cc, Cr = 0.0, 0.0
        geo.append(SubLayer(
            h=round(h, 3), z_bot_elev=round(elev - d_bot, 3), gamma=gamma, gamma_dn=gamma_dn,
            Cu=Cu, e0=e0, Cc=Cc, Cr=Cr, E=E, spz=spz, soil=sym, layer=sym))
    return geo, elev


def load_lk2_dataset(json_path: Optional[Path] = None) -> tuple[LK2Inputs, list[SubLayer]]:
    """Đọc dataset LK2 từ JSON (trích từ Excel gốc)."""
    path = Path(json_path) if json_path else _JSON
    d = json.loads(path.read_text(encoding="utf-8"))
    s = d["scalars"]
    inp = LK2Inputs(
        D_m=s["D_m"], S_m=s["S_m"], pattern=int(s["pattern"]),
        quck=s["quck"], Fs=s["Fs"], Ecol_factor=s["Ecol_factor_R90"],
        CD1_top_pile=s["CD1_top_pile"], CD2_bot_pile=s["CD2_bot_pile"],
        W_group=s["W_group"], theta_deg=s["theta_deg"],
        water_elev=s["CDNN_water"], P_fill=s["P_fill_noLL"],
        q_total=s.get("q_total_withLL", 36.774),
        a_pier=s.get("a_pier", 0.4), qsi=s.get("qsi", 5.0),
    )
    geo = [SubLayer(
        h=g["h"], z_bot_elev=g["z_bot_elev"], gamma=g["gamma"], gamma_dn=g["gamma_dn"],
        Cu=g["Cu"], e0=g["e0"], Cc=g["Cc"], Cr=g["Cr"], E=g["E"], spz=g["spz"],
        soil=g.get("soil", "Sét"), layer=g.get("layer", 1),
    ) for g in d["geology"]]
    return inp, geo


# --------------------------------------------------------------------------- #
# Demo / self-validation
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    inp, geo = load_lk2_dataset()
    r = compute_lk2(inp, geo)
    gold = json.loads(_JSON.read_text(encoding="utf-8"))["golden"]
    print("=== LK2 — Tinh lun khoi mong CDM ===")
    print(f"  Ac      = {r.Ac:.6f}  (Excel {gold['Ac']:.6f})")
    print(f"  A_unit  = {r.A_unit:.6f}  (Excel {gold['A_unit']:.6f})")
    print(f"  a ratio = {r.a_ratio:.6f}  (Excel {gold['ap']:.6f})")
    print(f"  Ecol    = {r.Ecol:.1f}  (Excel {gold['Ecol']:.1f})")
    print(f"  Eeq     = {r.Eeq:.6f}  (Excel {gold['Eeq']:.6f})")
    print(f"  Sblock  = {r.Sblock_m:.9f} m  (Excel {gold['Sblock_m']:.9f})")
    print(f"  Sc      = {r.Sc_m:.6f} m  (Excel {gold['Sc_m']:.6f})")
    print(f"  S total = {r.S_total_m:.9f} m  (Excel {gold['S_total_m']:.9f})")
    err = abs(r.S_total_m - gold["S_total_m"])
    print(f"  --> sai so S_total = {err:.2e} m  {'KHOP' if err < 1e-6 else 'LECH!!!'}")

    # --- SCT ---
    sct = compute_sct(inp, geo, r.Ecol, r.a_ratio)
    gs = json.loads(_JSON.read_text(encoding="utf-8")).get("golden_sct", {})
    print("\n=== LK2 — Suc chiu tai coc (SCT) ===")
    rows = [
        ("Etd", sct.Etd, gs.get("Etd")), ("Cu_soil", sct.Cu_soil, gs.get("Cu_soil")),
        ("N (tai 1 coc)", sct.N_load, gs.get("N_load")), ("Nvl (vat lieu)", sct.Nvl, gs.get("Nvl")),
        ("Ndn (dat nen)", sct.Ndn, gs.get("Ndn")), ("qp", sct.qp, gs.get("qp")),
        ("Nc=min", sct.Nc, gs.get("Nc")), ("ratio Nc/N", sct.ratio_Nc_N, gs.get("ratio_Nc_N")),
        ("sigma_col", sct.sigma_col, gs.get("sigma_col")), ("Pcol", sct.Pcol, gs.get("Pcol")),
        ("Qult.col AIT", sct.Qult_col_AIT, gs.get("Qult_col")),
        ("Qult.soil AIT", sct.Qult_soil_AIT, gs.get("Qult_soil")),
        ("Qa.soil", sct.Qa_soil, gs.get("Qa_soil")),
    ]
    maxerr = 0.0
    for name, v, g in rows:
        e = abs(v - g) if g is not None else float("nan")
        maxerr = max(maxerr, e if e == e else 0.0)
        print(f"  {name:16}= {v:14.6f}  (Excel {g})  d={e:.2e}")
    print(f"  --> sai so SCT max = {maxerr:.2e}  {'KHOP' if maxerr < 1e-6 else 'LECH!!!'}")

    # --- Sheet (2): lún theo thời gian ---
    full = json.loads(_JSON.read_text(encoding="utf-8"))
    cvt = full["cv_table"]; tvu = full["tvu_table"]; gt = full["golden_time"]
    th = compute_time_history(
        r, cvt["pressure_kPa"], cvt["Cv"], tvu["Tv"], tvu["U_pct"],
        gt["years"], allowable_cm=gt["allowable_cm"], design_time_idx=1,
    )
    print("\n=== LK2 — Lun theo thoi gian (sheet 2) ===")
    print(f"  H_drain = {th.H_drain_m:.4f} m  (Excel {gt['H_drain_m']})")
    print(f"  Ctbv    = {th.Ctbv_cm2s:.10f}  (Excel {gt['Ctbv_cm2s']:.10f})")
    print(f"  Sc      = {th.Sc_cm:.4f} cm  (Excel {gt['Sc_cm']})")
    print(f"  {'nam':>6} {'St(cm)':>12} {'Excel St':>12} {'d':>10}")
    me = 0.0
    for i, t in enumerate(th.years):
        ge = abs(th.St_cm[i] - gt["St_cm"][i]); me = max(me, ge)
        print(f"  {t:>6} {th.St_cm[i]:>12.4f} {gt['St_cm'][i]:>12.4f} {ge:>10.2e}")
    print(f"  residual check (t=1nam) = {th.residual_check_cm:.4f} cm  (Excel {gt['residual_check_cm']:.4f})  "
          f"<= {th.allowable_cm} -> {'Dat' if th.ok else 'Khong dat'}")
    print(f"  --> sai so St max = {me:.2e}  {'KHOP' if me < 1e-3 else 'LECH!!!'}")

    # --- Kiểm toán lớp bê tông C10 ---
    gc = full["golden_check"]; dv = full["scalars"].get("dv_concrete_m", 0.0)
    cc = compute_concrete_check(inp.D_m, inp.S_m, inp.q_total, dv,
                                fc_MPa=gc["fc_MPa"], bv_mm=gc["bv_mm"], Rbt_MPa=gc["Rbt_MPa"], phi=gc["phi"])
    print("\n=== LK2 — Kiem toan lop be tong C10 ===")
    print(f"  Mtt = {cc.Mtt} kNm  (Excel {gc['Mtt']})")
    print(f"  Vtt = {cc.Vtt} kN   (Excel {gc['Vtt']})")
    print(f"  [sigma] = {cc.sigma_flex_MPa:.6f} MPa  (Excel {gc['sigma_flex_MPa']:.6f})")
    print(f"  dv = {cc.dv_m} m -> Vr={cc.Vr} kN, Mr={cc.Mr} kNm (dv=0: khong co lop be tong)")
    ce = max(abs(cc.Mtt - gc["Mtt"]), abs(cc.Vtt - gc["Vtt"]), abs(cc.sigma_flex_MPa - gc["sigma_flex_MPa"]))
    print(f"  --> sai so kiem toan max = {ce:.2e}  {'KHOP' if ce < 1e-6 else 'LECH!!!'}")
