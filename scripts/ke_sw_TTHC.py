"""Tra cứu thiết kế kè cọc ván SW — Dự án 202605-TTHC (Trung tâm Hành chính TP.HCM).

Hai nguyên tắc chọn cọc:
  NT1: L_req = H_lớp1 + 3.70  (xuyên qua sét chảy + 1m)
  NT2: RR = phi_stat*(Rs+Rp) >= W_coc  (TCVN 11823-10:2017, Dieu 7.3.8.6.2)
       Bo qua doan dat dap khi tinh Rs.

Nguồn dữ liệu:
  data/ke_sw_202605_TTHC.json
  data/sw_pile_catalog.json
  data/soil_profile_202605_TTHC.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).parent.parent / "data"
_DATA     = _ROOT / "ke_sw_202605_TTHC.json"
_CATALOG  = _ROOT / "sw_pile_catalog.json"
_SOIL     = _ROOT / "soil_profile_202605_TTHC.json"

T_TO_KN        = 9.81   # 1 Tan (T) = 9.81 kN
PHI_STAT_ALPHA = 0.35   # TCVN 11823-10, Bang 9 — phuong phap alpha, set bao hoa
TOP_KE_M       = 2.70   # cao do dinh ke (m)

# su (kN/m2) cho tung lop dat — dung cho NT2 da lop
SU_PER_LAYER: dict[str, float] = {
    "1":  10.0,
    "1b": 20.0,
    "3":  35.0,
    "5":  75.0,
    "5b": 100.0,
}
# Lop cat / khong co ma sat than ben (qs = 0)
SAND_LAYERS: frozenset[str] = frozenset({"F", "2a", "2b", "2c", "4", "5a", "6", "7", "XMD"})

# Toa do noi suy alpha Tomlinson (1980) — Hinh 18 TCVN 11823-10
_ALPHA_SU  = [0.000, 0.025, 0.050, 0.075, 0.100, 0.150, 0.200]
_ALPHA_VAL = [1.000, 1.000, 0.920, 0.750, 0.600, 0.500, 0.400]


def _alpha_tomlinson(su_kNm2: float) -> float:
    """He so ket dinh alpha theo Tomlinson (1980), su tinh bang kN/m2."""
    su_MPa = su_kNm2 / 1000.0
    if su_MPa <= _ALPHA_SU[0]:
        return _ALPHA_VAL[0]
    if su_MPa >= _ALPHA_SU[-1]:
        return _ALPHA_VAL[-1]
    for i in range(len(_ALPHA_SU) - 1):
        if _ALPHA_SU[i] <= su_MPa <= _ALPHA_SU[i + 1]:
            t = (su_MPa - _ALPHA_SU[i]) / (_ALPHA_SU[i + 1] - _ALPHA_SU[i])
            return _ALPHA_VAL[i] + t * (_ALPHA_VAL[i + 1] - _ALPHA_VAL[i])
    return _ALPHA_VAL[-1]


@dataclass
class PileRequirement:
    name: str           # tên hố khoan
    Z_m: float          # cao độ mặt đất
    H_layer1_m: float   # chiều dày lớp sét chảy
    L_req_m: float      # chiều dài tối thiểu (NT1)
    tip_elevation_m: float
    tip_layer: str
    recommended_pile: str
    recommended_L_m: float | None
    margin_NT1_m: float | None
    W_pile_kN: float | None
    required_Qa_kN: float | None
    NT1: str
    NT2: str
    note: str

    def summary(self) -> None:
        print(f"\n{self.name}  Z={self.Z_m:+.3f}m  H_Lớp1={self.H_layer1_m:.1f}m")
        print(f"  NT1: L_req={self.L_req_m:.1f}m  biên={self.margin_NT1_m}m  → {self.NT1}")
        print(f"  NT2: {self.NT2}")
        print(f"  Đề xuất: {self.recommended_pile}  L={self.recommended_L_m}m")
        if self.note:
            print(f"  Canh bao: {self.note}")


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse() -> list[PileRequirement]:
    data   = _load(_DATA)
    fields = {f.name for f in PileRequirement.__dataclass_fields__.values()}
    return [PileRequirement(**{k: v for k, v in bh.items() if k in fields})
            for bh in data["boreholes"]]


# ── Truy vấn ─────────────────────────────────────────────────────────────────

def list_all() -> list[PileRequirement]:
    """Trả về danh sách yêu cầu thiết kế cho tất cả hố khoan."""
    return _parse()


def get(name: str) -> PileRequirement:
    """Tra cứu theo tên hố khoan (ví dụ: 'HK10')."""
    for req in list_all():
        if req.name.upper() == name.upper():
            return req
    raise KeyError(f"Không tìm thấy hố khoan: {name}")


def critical_boreholes() -> list[PileRequirement]:
    """Trả về các hố khoan có NT1 = PASS_CRITICAL hoặc SPECIAL."""
    return [r for r in list_all() if r.NT1 in ("PASS_CRITICAL", "SPECIAL")]


# ── Tính toán NT1 theo công thức ──────────────────────────────────────────────

def calc_L_req(
    H_layer1_m: float,
    top_ke_m: float = 2.70,
    min_penetration_m: float = 1.00,
) -> float:
    """Chiều dài tối thiểu theo NT1.

    L_req = top_ke_m + H_layer1_m + min_penetration_m
    """
    return top_ke_m + H_layer1_m + min_penetration_m


def check_NT1(pile_name: str, L_max_m: float, H_layer1_m: float) -> dict:
    """Kiểm tra NT1 cho một loại cọc và một hố khoan."""
    L_req = calc_L_req(H_layer1_m)
    margin = L_max_m - L_req
    return {
        "pile": pile_name,
        "L_max_m": L_max_m,
        "L_req_m": round(L_req, 2),
        "margin_m": round(margin, 2),
        "pass": margin >= 0,
    }


# ── Tính toán NT2 ─────────────────────────────────────────────────────────────

def pile_weight(weight_T: float, L_std_m: float, L_m: float) -> float:
    """Trọng lượng bản thân cọc (kN/cọc) — dùng cho kiểm tra NT2.

    weight_T: cột TL(T) trong catalog, đơn vị Tấn → nhân T_TO_KN=9.81 ra kN.

    Phân biệt hai đại lượng:
      w_per_pile [kN/m/cọc] = TL×9.81/L_std   → W = w×L     (dùng cho NT2)
      w_plaxis   [kN/m/m]   = w_per_pile/spacing              (PLAXIS Plate)
    Ví dụ SW-840: 16.35T×9.81/22m = 7.29 kN/m/cọc; PLAXIS: 7.29/0.996 = 7.32 kN/m/m
    """
    w_per_m = weight_T * T_TO_KN / L_std_m   # kN/m/cọc
    return w_per_m * L_m


def pile_weight_plaxis(weight_T: float, L_std_m: float, spacing_m: float = 0.996) -> float:
    """Trọng lượng cho PLAXIS Plate element (kN/m/m).

    = w_per_pile / spacing_m — khác với pile_weight() dùng cho NT2.
    Ví dụ SW-840: 7.29 / 0.996 = 7.32 kN/m/m (khớp với 11-sw-pile-database.md §11.4)
    """
    return weight_T * T_TO_KN / L_std_m / spacing_m


def check_NT2_tcvn(
    L_total_m: float,
    Z_natural_m: float,
    su_kNm2: float,
    perimeter_mm: float,
    Ap_mm2: float,
    W_pile_kN: float,
    alpha: float = 1.0,
    phi_stat: float = PHI_STAT_ALPHA,
    top_ke_m: float = TOP_KE_M,
) -> dict:
    """Kiem tra NT2 theo TCVN 11823-10:2017, Dieu 7.3.8.6.2 (alpha-method).

    Bo qua doan dat dap (tu dinh ke xuong den mat dat tu nhien) khi tinh Rs.
    Gom ca suc khang mui Rp = 9*Su*Ap (Pt. 65).
    Khong nhan FS len W_pile — phi_stat (= 0.35) la he so suc khang LRFD.

    RR = phi_stat * (Rs + Rp) >= W_pile
    Rs = alpha * su * (perimeter_mm/1000) * L_in_soil_m   [kN]
    Rp = 9 * su * Ap_mm2 * 1e-6                           [kN]
    L_in_soil_m = L_total - (top_ke_m - Z_natural_m)
    """
    fill_m      = top_ke_m - Z_natural_m          # chieu day dat dap (m)
    L_in_soil_m = max(0.0, L_total_m - fill_m)
    Rs_kN       = alpha * su_kNm2 * (perimeter_mm / 1000.0) * L_in_soil_m
    Rp_kN       = 9.0 * su_kNm2 * Ap_mm2 * 1e-6
    Rn_kN       = Rs_kN + Rp_kN
    RR_kN       = phi_stat * Rn_kN
    return {
        "fill_m":         round(fill_m, 2),
        "L_in_soil_m":    round(L_in_soil_m, 2),
        "Rs_kN":          round(Rs_kN, 1),
        "Rp_kN":          round(Rp_kN, 1),
        "Rn_kN":          round(Rn_kN, 1),
        "phi_stat":       phi_stat,
        "RR_kN":          round(RR_kN, 1),
        "W_pile_kN":      round(W_pile_kN, 1),
        "pass":           RR_kN >= W_pile_kN,
        "ratio":          round(RR_kN / W_pile_kN, 2),
    }


# ── NT2 đa lớp ───────────────────────────────────────────────────────────────

def check_NT2_multilayer(
    bh_layers: list[dict],
    Z_natural_m: float,
    L_total_m: float,
    perimeter_mm: float,
    Ap_mm2: float,
    W_pile_kN: float,
    phi_stat: float = PHI_STAT_ALPHA,
    top_ke_m: float = TOP_KE_M,
) -> dict:
    """NT2 da lop: tinh Rs theo tung lop dat thuc, Rp theo lop mui coc.

    Bo qua phan dat dap (tu dinh ke xuong den mat dat tu nhien).
    Lop cat (SAND_LAYERS) co qs = 0. Alpha tinh theo Tomlinson (1980).

    RR = phi_stat * (Rs + Rp) >= W_pile
    Rs = sum_lop( alpha*su * (perimeter/1000) * thickness_used )
    Rp = 9 * su_tip * Ap_mm2 * 1e-6   (0 neu lop mui la cat)
    """
    fill_m      = top_ke_m - Z_natural_m
    L_in_soil_m = max(0.0, L_total_m - fill_m)

    depth_used = 0.0
    rs_layers: list[dict] = []
    tip_layer  = None

    for layer in bh_layers:
        if depth_used >= L_in_soil_m:
            break
        sym   = layer["symbol"]
        thick = layer["thickness_m"]
        used  = min(thick, L_in_soil_m - depth_used)

        if sym in SAND_LAYERS:
            qs = 0.0
            alpha = 0.0
        else:
            su    = SU_PER_LAYER.get(sym, 0.0)
            alpha = _alpha_tomlinson(su)
            qs    = alpha * su

        rs_this = qs * (perimeter_mm / 1000.0) * used
        rs_layers.append({
            "symbol":        sym,
            "thickness_m":   round(used, 3),
            "su_kNm2":       SU_PER_LAYER.get(sym, 0.0) if sym not in SAND_LAYERS else 0.0,
            "alpha":         round(alpha, 3),
            "qs_kNm2":       round(qs, 3),
            "Rs_kN":         round(rs_this, 1),
        })
        depth_used += used
        tip_layer   = sym

    Rs_kN   = round(sum(l["Rs_kN"] for l in rs_layers), 1)
    su_tip  = SU_PER_LAYER.get(tip_layer, 0.0) if (tip_layer and tip_layer not in SAND_LAYERS) else 0.0
    Rp_kN   = round(9.0 * su_tip * Ap_mm2 * 1e-6, 1)
    Rn_kN   = round(Rs_kN + Rp_kN, 1)
    RR_kN   = round(phi_stat * Rn_kN, 1)
    return {
        "fill_m":       round(fill_m, 2),
        "L_in_soil_m":  round(L_in_soil_m, 2),
        "layers":       rs_layers,
        "Rs_kN":        Rs_kN,
        "tip_layer":    tip_layer,
        "su_tip_kNm2":  su_tip,
        "Rp_kN":        Rp_kN,
        "Rn_kN":        Rn_kN,
        "phi_stat":     phi_stat,
        "RR_kN":        RR_kN,
        "W_pile_kN":    round(W_pile_kN, 1),
        "pass":         RR_kN >= W_pile_kN,
        "ratio":        round(RR_kN / W_pile_kN, 2),
    }


def run_all_NT2_multilayer(design_L_m: float = 29.0) -> list[dict]:
    """Tinh NT2 da lop cho toan bo ho khoan du an TTHC.

    SW-940 cho HK10, SW-840 cho tat ca HK con lai (tru HK12 SPECIAL).
    Chu vi SW-940 dung 4984 mm (noi suy — catalog ghi null).
    """
    soil    = _load(_SOIL)
    catalog = _load(_CATALOG)

    SW840 = next(p for p in catalog["piles"] if p["name"] == "SW-840")
    SW940 = next(p for p in catalog["piles"] if p["name"] == "SW-940")
    SW940_PERIM_MM = 4984.0   # noi suy tuyen tinh tu SW-740/SW-840 — can xac nhan catalog

    results = []
    for bh in soil["boreholes"]:
        name = bh["name"]
        Z    = bh["elevation_m"]

        if name == "HK12":
            results.append({"name": "HK12", "note": "SPECIAL — XMD, thiet ke rieng"})
            continue

        if name == "HK10":
            pile  = SW940
            perim = SW940_PERIM_MM
            pile_label = "SW-940"
        else:
            pile  = SW840
            perim = SW840["perimeter_mm"]
            pile_label = "SW-840"

        Ap_mm2 = pile["Atd_cm2"] * 100.0
        W_kN   = pile_weight(pile["weight_T"], pile["L_std_m"], design_L_m)

        try:
            H_L1 = next(l["thickness_m"] for l in bh["layers"] if l["symbol"] == "1")
        except StopIteration:
            H_L1 = 0.0

        L_req   = calc_L_req(H_L1)
        margin  = design_L_m - L_req
        nt2     = check_NT2_multilayer(
            bh_layers=bh["layers"],
            Z_natural_m=Z,
            L_total_m=design_L_m,
            perimeter_mm=perim,
            Ap_mm2=Ap_mm2,
            W_pile_kN=W_kN,
        )
        results.append({
            "name":        name,
            "Z_m":         Z,
            "H_L1_m":      H_L1,
            "L_req_m":     round(L_req, 1),
            "pile":        pile_label,
            "L_m":         design_L_m,
            "NT1_pass":    margin >= 0,
            "margin_NT1_m": round(margin, 1),
            "NT2":         nt2,
        })
    return results


def print_NT2_multilayer_table() -> None:
    """In bang tong hop NT2 da lop — tat ca ho khoan."""
    rows = run_all_NT2_multilayer()
    print(f"\n{'='*95}")
    print(f"  NT2 da lop — alpha-method TCVN 11823-10:2017, phi=0.35, bo qua dat dap")
    print(f"  su/lop: L1=10, L1b=20, L3=35, L5=75, L5b=100 kN/m2 | cat: qs=0")
    print(f"{'='*95}")
    hdr = (f"  {'HK':<5} {'Z(m)':>7} {'H_L1':>6} {'L_req':>6} {'Coc':>7} {'L':>3}"
           f" {'Lop mui':>7} {'Rs':>6} {'Rp':>5} {'RR':>6} {'W':>6} {'Ti so':>6} {'NT2':>8} {'NT1':>14}")
    print(hdr)
    print(f"  {'-'*5} {'-'*7} {'-'*6} {'-'*6} {'-'*7} {'-'*3}"
          f" {'-'*7} {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*14}")
    for r in rows:
        if "note" in r:
            print(f"  {r['name']:<5} — {r['note']}")
            continue
        nt2     = r["NT2"]
        nt2_str = "Dat" if nt2["pass"] else "Khong dat"
        nt1_str = f"Dat(+{r['margin_NT1_m']}m)" if r["NT1_pass"] else f"Khong dat({r['margin_NT1_m']}m)"
        print(
            f"  {r['name']:<5} {r['Z_m']:>7.3f} {r['H_L1_m']:>6.1f} {r['L_req_m']:>6.1f}"
            f" {r['pile']:>7} {r['L_m']:>3.0f}"
            f" {nt2['tip_layer']:>7} {nt2['Rs_kN']:>6.0f} {nt2['Rp_kN']:>5.0f}"
            f" {nt2['RR_kN']:>6.0f} {nt2['W_pile_kN']:>6.1f} {nt2['ratio']:>6.2f}"
            f" {nt2_str:>8} {nt1_str:>14}"
        )
    print(f"{'='*95}")


# ── Bảng tổng hợp ─────────────────────────────────────────────────────────────

def print_summary() -> None:
    """In bảng tổng hợp thiết kế toàn bộ hố khoan."""
    reqs = list_all()
    print(f"\n{'='*80}")
    print(f"{'Kè SW — Dự án TTHC HCM (202605)':^80}")
    print(f"  Cao độ đỉnh kè: +2.70m  |  Mặt đất: 0.00m  |  Xuyên qua Lớp 1 + 1.0m")
    print(f"{'='*80}")
    header = f"  {'HK':<5} {'Z(m)':>7} {'H_L1(m)':>8} {'L_req':>7} {'Cọc':>8} {'L(m)':>5} {'Biên':>6} {'NT1':>14} {'NT2':>5}"
    print(header)
    print(f"  {'-'*5} {'-'*7} {'-'*8} {'-'*7} {'-'*8} {'-'*5} {'-'*6} {'-'*14} {'-'*5}")
    for r in reqs:
        margin = f"{r.margin_NT1_m:.1f}" if r.margin_NT1_m is not None else "—"
        L_str  = str(r.recommended_L_m) if r.recommended_L_m else "—"
        print(
            f"  {r.name:<5} {r.Z_m:>7.3f} {r.H_layer1_m:>8.1f} "
            f"{r.L_req_m:>7.1f} {r.recommended_pile:>8} {L_str:>5} {margin:>6} "
            f"{r.NT1:>14} {r.NT2:>5}"
        )
    print(f"{'='*80}")
    crits = critical_boreholes()
    if crits:
        print("\n  Canh bao — Ho khoan can chu y:")
        for r in crits:
            print(f"  {r.name}: {r.note}")


if __name__ == "__main__":
    print_summary()
    print_NT2_multilayer_table()

    print("\n--- Kiểm tra chi tiết HK10 ---")
    hk10 = get("HK10")
    hk10.summary()

    print("\n--- NT2 TCVN 11823-10: SW-840 L=29m tai HK1 (Z=-0.800m) ---")
    result = check_NT2_tcvn(
        L_total_m=29,
        Z_natural_m=-0.800,
        su_kNm2=10,
        perimeter_mm=4594.913,
        Ap_mm2=310_700,
        W_pile_kN=pile_weight(weight_T=16.35, L_std_m=22, L_m=29),
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n--- NT2 TCVN 11823-10: SW-940 L=29m tai HK10 (Z=-0.381m) ---")
    result10 = check_NT2_tcvn(
        L_total_m=29,
        Z_natural_m=-0.381,
        su_kNm2=10,
        perimeter_mm=4984,
        Ap_mm2=354_400,
        W_pile_kN=pile_weight(weight_T=18.31, L_std_m=23, L_m=29),
    )
    for k, v in result10.items():
        print(f"  {k}: {v}")

    print("\n--- NT1: SW-840 vs các HK ---")
    for req in list_all():
        if req.NT1 not in ("SPECIAL",):
            check = check_NT1("SW-840", L_max_m=29, H_layer1_m=req.H_layer1_m)
            status = "Dat" if check["pass"] else "Khong dat"
            print(f"  {req.name}: L_req={check['L_req_m']}m  bien={check['margin_m']}m  {status}")
