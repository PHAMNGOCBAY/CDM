"""
plate_properties.py
Tính toán đặc trưng vật liệu Plate cho PLAXIS 2D.

Công thức nguồn: PLAXIS 2D Reference Manual, Section 6.4.2.1 Stiffness properties
  - Eq.[54]: d_eq = sqrt(12 * EI / EA1)          -- Chiều dày tương đương
  - Eq.[55]: Shear stiffness = 5*EA / (12*(1+v))  -- Độ cứng cắt Mindlin

Sử dụng:
    from plate_properties import PlateSection, SteelSheetPile, ConcreteWall
    plate = PlateSection(EA1=10_335_000, EI=504_100, nu=0.0, w=4.371)
    plate.summary()

    # Hoặc từ thông số mặt cắt thép
    sp = SteelSheetPile.from_section(A_cm2=492.14, I_cm4=240047, spacing_m=0.84)
    sp.summary()
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Hằng số vật liệu
# ĐƠN VỊ PLAXIS: kN/m²   ≠   MPa
# Quy đổi:  1 MPa = 1,000 kN/m²   →   E_MPa × 1000 = E_kNm2
# ---------------------------------------------------------------------------
E_STEEL    = 210_000_000.0   # kN/m²  (= 210,000 MPa × 1,000)
E_CONCRETE = 30_000_000.0    # kN/m²  (= 30,000 MPa × 1,000)  — BTCT thường

# Bê tông cọc f'c = 70 MPa (NSL — dự án L=25M-HKT8-SW840)
# Ec = 43,628.13 MPa  →  43,628.13 × 1,000 = 43,628,130 kN/m²
E_CONCRETE_F70 = 43_628_130.0   # kN/m²  (= 43,628.13 MPa)

GAMMA_STEEL    = 78.5        # kN/m³
GAMMA_CONCRETE = 25.0        # kN/m³


def mpa_to_knm2(E_MPa: float) -> float:
    """Đổi đơn vị MPa → kN/m² để nhập vào PLAXIS. 1 MPa = 1,000 kN/m²."""
    return E_MPa * 1_000.0


def knm2_to_mpa(E_kNm2: float) -> float:
    """Đổi đơn vị kN/m² → MPa để đối chiếu với tài liệu."""
    return E_kNm2 / 1_000.0


# ---------------------------------------------------------------------------
# Lớp chính: PlateSection
# ---------------------------------------------------------------------------
@dataclass
class PlateSection:
    """
    Đặc trưng vật liệu plate PLAXIS 2D.
    Đầu vào là các thông số nhập trực tiếp vào PLAXIS.
    """
    name: str                # Tên vật liệu
    EA1: float               # kN/m  — độ cứng dọc trục in-plane
    EI:  float               # kN·m²/m — độ cứng uốn
    nu:  float = 0.0         # [-]  — hệ số Poisson (0 cho cừ thép, 0.15 cho BTCT)
    EA2: Optional[float] = None  # kN/m  — out-of-plane (None = isotropic = EA1)
    w:   float = 0.0         # kN/m/m — trọng lượng bản thân

    # Thông số tính ngược (điền khi biết loại vật liệu)
    E_material: Optional[float] = None  # kN/m² — mô đun đàn hồi vật liệu

    def __post_init__(self):
        if self.EA2 is None:
            self.EA2 = self.EA1  # isotropic

    # ------------------------------------------------------------------
    # Tính toán theo Eq.[54] và Eq.[55]
    # ------------------------------------------------------------------

    @property
    def d_eq(self) -> float:
        """Chiều dày tương đương [m] — Eq.[54]: d = sqrt(12*EI/EA1)."""
        if self.EA1 <= 0:
            return 0.0
        return math.sqrt(12.0 * self.EI / self.EA1)

    @property
    def shear_stiffness(self) -> float:
        """Độ cứng cắt [kN/m] — Eq.[55]: 5*EA1 / (12*(1+v))."""
        return 5.0 * self.EA1 / (12.0 * (1.0 + self.nu))

    @property
    def G_shear(self) -> float:
        """Mô đun cắt tương đương [kN/m²] = ShearStiffness / (d * 1m)."""
        d = self.d_eq
        if d <= 0:
            return 0.0
        return self.shear_stiffness / d

    # ------------------------------------------------------------------
    # Tính ngược khi biết E vật liệu
    # ------------------------------------------------------------------

    @property
    def E_equiv(self) -> Optional[float]:
        """Mô đun đàn hồi tương đương [kN/m²] = EA1 / d_eq."""
        d = self.d_eq
        if d <= 0:
            return None
        return self.EA1 / d

    @property
    def A_per_m(self) -> Optional[float]:
        """Diện tích mặt cắt trên 1m dài [cm²/m] (cần biết E_material)."""
        if self.E_material is None:
            return None
        return self.EA1 / self.E_material * 1e4  # m²/m → cm²/m

    @property
    def I_per_m(self) -> Optional[float]:
        """Mô men quán tính trên 1m dài [cm⁴/m] (cần biết E_material)."""
        if self.E_material is None:
            return None
        return self.EI / self.E_material * 1e8  # m⁴/m → cm⁴/m

    # ------------------------------------------------------------------
    # Kiểm tra kỹ thuật
    # ------------------------------------------------------------------

    def check_shear_deformation(self, plate_length_m: float) -> dict:
        """
        Kiểm tra điều kiện biến dạng cắt không đáng kể.
        PLAXIS Manual: d_eq nên nhỏ hơn ít nhất 10 lần chiều dài plate
        (áp dụng cho cừ thép — steel profile elements).
        """
        ratio = plate_length_m / self.d_eq if self.d_eq > 0 else float("inf")
        ok = ratio >= 10.0
        return {
            "L_m":        plate_length_m,
            "d_eq_m":     round(self.d_eq, 4),
            "L_d_ratio":  round(ratio, 1),
            "OK":         ok,
            "note":       "OK" if ok else
                          f"CANH BAO: L/d = {ratio:.1f} < 10 -- bien dang cat co the qua lon",
        }

    def check_poisson(self, is_steel_profile: bool = False) -> str:
        """
        Khuyến nghị hệ số Poisson theo PLAXIS Manual:
        - Cừ thép (flexible out-of-plane): nu = 0
        - Tường BTCT đặc (massive): nu = 0.15
        """
        if is_steel_profile and self.nu != 0.0:
            return f"CANH BAO: Cu thep nen dung nu=0, hien tai nu={self.nu}"
        if not is_steel_profile and self.nu == 0.0:
            return "GHI CHU: Nen xem xet nu=0.15 cho tuong BTCT dac"
        return "OK"

    # ------------------------------------------------------------------
    # In bảng kết quả
    # ------------------------------------------------------------------

    def summary(self, plate_length_m: Optional[float] = None,
                is_steel_profile: bool = False) -> None:
        """In toàn bộ đặc trưng plate ra console."""
        sep = "=" * 62
        print(f"\n{sep}")
        print(f"  PLAXIS PLATE PROPERTIES: {self.name}")
        print(sep)

        # Thông số đầu vào
        print("  [INPUT]")
        print(f"    EA1 (in-plane axial stiffness) : {self.EA1:>15,.0f} kN/m")
        iso_tag = "(= EA1, Isotropic)" if self.EA2 == self.EA1 else ""
        print(f"    EA2 (out-of-plane ax. stiffness): {self.EA2:>15,.0f} kN/m  {iso_tag}")
        print(f"    EI  (bending stiffness)         : {self.EI:>15,.0f} kN.m2/m")
        print(f"    nu  (Poisson's ratio)            : {self.nu:>15.3f}")
        print(f"    w   (unit weight)                : {self.w:>15.4f} kN/m/m")

        # Thông số tính từ Eq.[54] và [55]
        print("\n  [DERIVED — PLAXIS Eq.54 & 55]")
        print(f"    d_eq = sqrt(12*EI/EA1)   [Eq.54]: {self.d_eq:>15.5f} m")
        print(f"    Shear stiff = 5EA/(12(1+v))[55]: {self.shear_stiffness:>15,.0f} kN/m")
        print(f"    G_shear (= ShearStiff / d_eq)   : {self.G_shear:>15,.0f} kN/m2")

        # Tính ngược từ E vật liệu
        if self.E_material is not None:
            mat_name = (
                "Thep" if abs(self.E_material - E_STEEL) < 1e6 else
                "BTCT" if abs(self.E_material - E_CONCRETE) < 1e6 else
                "Custom"
            )
            print(f"\n  [BACK-CALC from E_{mat_name} = {self.E_material/1e6:.0f} MPa]")
            print(f"    A = EA1/E   : {self.A_per_m:>12.2f} cm2/m")
            print(f"    I = EI/E    : {self.I_per_m:>12.2f} cm4/m")
            print(f"    E_equiv     : {self.E_equiv/1e6:>12,.1f} MPa")

        # Kiểm tra
        print("\n  [CHECKS]")
        print(f"    Poisson : {self.check_poisson(is_steel_profile)}")
        if plate_length_m is not None:
            chk = self.check_shear_deformation(plate_length_m)
            print(f"    Shear   : L={chk['L_m']}m, d={chk['d_eq_m']}m, "
                  f"L/d={chk['L_d_ratio']} -- {chk['note']}")

        print(sep)


# ---------------------------------------------------------------------------
# Lớp tiện ích: Cừ thép (Steel Sheet Pile)
# ---------------------------------------------------------------------------
@dataclass
class SteelSheetPile:
    """
    Tính đặc trưng PLAXIS từ catalog cừ thép.
    Quy đổi từ mặt cắt đơn → trên 1m dài tường.
    """
    name:       str
    A_cm2:      float   # cm²   — diện tích mặt cắt một tấm cừ
    I_cm4:      float   # cm⁴   — mô men quán tính một tấm cừ
    spacing_m:  float   # m     — bề rộng một tấm cừ (e.g., 0.84m cho SW840)
    nu:         float = 0.0           # cừ thép: nu = 0
    gamma_kNm3: float = GAMMA_STEEL   # kN/m³

    @classmethod
    def from_section(cls, name: str, A_cm2: float, I_cm4: float,
                     spacing_m: float, **kwargs) -> "SteelSheetPile":
        return cls(name=name, A_cm2=A_cm2, I_cm4=I_cm4, spacing_m=spacing_m, **kwargs)

    @property
    def A_per_m(self) -> float:
        """Diện tích quy đổi trên 1m dài tường [cm²/m]."""
        return self.A_cm2 / self.spacing_m

    @property
    def I_per_m(self) -> float:
        """Mô men quán tính quy đổi trên 1m dài tường [cm⁴/m]."""
        return self.I_cm4 / self.spacing_m

    @property
    def EA1(self) -> float:
        """Độ cứng dọc trục PLAXIS [kN/m]."""
        return E_STEEL * (self.A_per_m / 1e4)   # cm²/m → m²/m

    @property
    def EI(self) -> float:
        """Độ cứng uốn PLAXIS [kN·m²/m]."""
        return E_STEEL * (self.I_per_m / 1e8)   # cm⁴/m → m⁴/m

    @property
    def w(self) -> float:
        """Trọng lượng bản thân [kN/m/m]."""
        return self.gamma_kNm3 * (self.A_per_m / 1e4)

    def to_plate_section(self) -> PlateSection:
        return PlateSection(
            name        = self.name,
            EA1         = self.EA1,
            EI          = self.EI,
            nu          = self.nu,
            w           = self.w,
            E_material  = E_STEEL,
        )

    def summary(self, plate_length_m: Optional[float] = None) -> None:
        print(f"\n{'='*62}")
        print(f"  STEEL SHEET PILE: {self.name}")
        print(f"  spacing = {self.spacing_m*100:.0f} cm / tám")
        print(f"{'='*62}")
        print(f"  [MOI MAT CAT DON (catalog)]")
        print(f"    A  = {self.A_cm2:>10.2f} cm2")
        print(f"    I  = {self.I_cm4:>10.2f} cm4")
        print(f"\n  [QUY DOI TREN 1m DAI TUONG (spacing={self.spacing_m}m)]")
        print(f"    A/m = {self.A_per_m:>10.2f} cm2/m")
        print(f"    I/m = {self.I_per_m:>10.2f} cm4/m")
        ps = self.to_plate_section()
        print(f"\n  [THONG SO PLAXIS]")
        print(f"    EA1 = {ps.EA1:>15,.0f} kN/m")
        print(f"    EI  = {ps.EI:>15,.0f} kN.m2/m")
        print(f"    nu  = {ps.nu:>15.3f}  (steel profile: nu=0)")
        print(f"    w   = {ps.w:>15.4f} kN/m/m")
        print(f"    d_eq= {ps.d_eq:>15.5f} m")
        print(f"    Shear stiff = {ps.shear_stiffness:>12,.0f} kN/m")
        if plate_length_m is not None:
            chk = ps.check_shear_deformation(plate_length_m)
            print(f"    L/d check: L={plate_length_m}m, L/d={chk['L_d_ratio']} -- {chk['note']}")
        print(f"{'='*62}")


# ---------------------------------------------------------------------------
# Lớp tiện ích: Tường BTCT (Concrete Wall / Plate)
# ---------------------------------------------------------------------------
@dataclass
class ConcreteWall:
    """
    Tính đặc trưng PLAXIS từ thông số hình học tường BTCT.
    Mô hình dạng plate với chiều dày thực d [m].
    """
    name:         str
    d_m:          float   # m    — chiều dày tường thực
    nu:           float = 0.15          # PLAXIS Manual: massive structure nu=0.15
    E_kNm2:       float = E_CONCRETE    # kN/m²
    gamma_kNm3:   float = GAMMA_CONCRETE

    @property
    def EA1(self) -> float:
        return self.E_kNm2 * self.d_m  # E * A/m = E * d * 1m

    @property
    def EI(self) -> float:
        return self.E_kNm2 * (self.d_m ** 3) / 12.0

    @property
    def w(self) -> float:
        return self.gamma_kNm3 * self.d_m

    def to_plate_section(self) -> PlateSection:
        return PlateSection(
            name       = self.name,
            EA1        = self.EA1,
            EI         = self.EI,
            nu         = self.nu,
            w          = self.w,
            E_material = self.E_kNm2,
        )

    def summary(self, plate_length_m: Optional[float] = None) -> None:
        print(f"\n{'='*62}")
        print(f"  CONCRETE WALL (Plate): {self.name}")
        print(f"  d = {self.d_m*100:.0f} cm, E = {self.E_kNm2/1e6:.0f} MPa, "
              f"nu = {self.nu}, gamma = {self.gamma_kNm3} kN/m3")
        print(f"{'='*62}")
        ps = self.to_plate_section()
        print(f"    EA1 = {ps.EA1:>15,.0f} kN/m")
        print(f"    EI  = {ps.EI:>15,.0f} kN.m2/m")
        print(f"    nu  = {ps.nu:>15.3f}")
        print(f"    w   = {ps.w:>15.4f} kN/m/m")
        print(f"    d_eq= {ps.d_eq:>15.5f} m  (phai = {self.d_m:.4f} m)")
        print(f"    Shear stiff = {ps.shear_stiffness:>12,.0f} kN/m")
        if plate_length_m is not None:
            chk = ps.check_shear_deformation(plate_length_m)
            print(f"    L/d check: L={plate_length_m}m, L/d={chk['L_d_ratio']}")
        print(f"{'='*62}")


# ---------------------------------------------------------------------------
# Hàm tiện ích: so sánh nhiều plate
# ---------------------------------------------------------------------------

def compare_plates(plates: list[PlateSection], plate_length_m: Optional[float] = None) -> None:
    """In bảng so sánh nhiều vật liệu plate."""
    header = (f"{'Ten':<16} {'EA1':>12} {'EI':>12} {'nu':>5} "
              f"{'d_eq(m)':>9} {'ShearStiff':>12} {'w':>8}")
    if plate_length_m:
        header += f" {'L/d':>6}"
    sep = "-" * len(header)
    print(f"\n{'='*len(header)}")
    print("  PLATE COMPARISON TABLE")
    if plate_length_m:
        print(f"  Plate length = {plate_length_m} m")
    print(f"{'='*len(header)}")
    print(header)
    print(sep)
    for p in plates:
        row = (f"{p.name:<16} {p.EA1:>12,.0f} {p.EI:>12,.0f} {p.nu:>5.2f} "
               f"{p.d_eq:>9.4f} {p.shear_stiffness:>12,.0f} {p.w:>8.3f}")
        if plate_length_m:
            chk = p.check_shear_deformation(plate_length_m)
            flag = "" if chk["OK"] else " <!"
            row += f" {chk['L_d_ratio']:>6.1f}{flag}"
        print(row)
    print(f"{'='*len(header)}")
    print("  Don vi: EA1 [kN/m], EI [kN.m2/m], ShearStiff [kN/m], w [kN/m/m]")
    if plate_length_m:
        print("  <! : L/d < 10 -- nen kiem tra bien dang cat (PLAXIS Manual)")


# ---------------------------------------------------------------------------
# Demo chạy trực tiếp
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print("\n" + "#" * 62)
    print("  VI DU 1: Doc truc tiep tu PLAXIS (L=25M-HKT8-SW840)")
    print("#" * 62)

    # ĐƠN VỊ: kiểm tra nhanh trước khi nhập PLAXIS
    print("  [DON VI] 43,628.13 MPa x 1,000 =", f"{mpa_to_knm2(43_628.13):,.0f}", "kN/m2")
    print()

    # Bê tông cọc f'c=70MPa: Ec = 43,628.13 MPa = 43,628,130 kN/m² (tu tai lieu NSL)
    plates_from_file = [
        PlateSection("SW840",     EA1=10_335_000, EI=504_100,  nu=0.0, w=4.371, E_material=E_STEEL),
        PlateSection("SW400",     EA1= 7_204_000, EI=118_800,  nu=0.0, w=3.237, E_material=E_STEEL),
        PlateSection("tuong-tren",EA1=19_700_000, EI=591_000,  nu=0.2, w=18.4,  E_material=E_CONCRETE_F70),
        PlateSection("tuong-dung",EA1=11_490_000, EI=117_300,  nu=0.2, w=10.72, E_material=E_CONCRETE_F70),
        PlateSection("tuongday",  EA1=16_420_000, EI=342_000,  nu=0.2, w=15.31, E_material=E_CONCRETE_F70),
    ]

    # In chi tiết cho SW840
    plates_from_file[0].summary(plate_length_m=25.0, is_steel_profile=True)

    # So sánh tất cả
    compare_plates(plates_from_file, plate_length_m=25.0)

    # ------------------------------------------------------------------
    print("\n" + "#" * 62)
    print("  VI DU 2: Tinh tu catalog cu thep (nhap tu so lieu)")
    print("#" * 62)

    # SW840 — bề rộng tấm cừ 840mm
    sw840 = SteelSheetPile.from_section(
        name       = "SW840",
        A_cm2      = 413.0,      # cm²/tam  (thay bang catalog thuc)
        I_cm4      = 201_638.0,  # cm4/tam
        spacing_m  = 0.840,      # m/tam
    )
    sw840.summary(plate_length_m=25.0)

    # ------------------------------------------------------------------
    print("\n" + "#" * 62)
    print("  VI DU 3: Coc BTCT f'c=70MPa, Ec=43,628.13 MPa, d=0.6m")
    print("#" * 62)

    # Ec tu tai lieu: 43,628.13 MPa -> phai nhan 1000 de co kN/m2
    coc_btct = ConcreteWall(
        name       = "Coc BTCT f'c=70MPa",
        d_m        = 0.60,
        nu         = 0.15,
        E_kNm2     = mpa_to_knm2(43_628.13),   # 43,628,130 kN/m2
        gamma_kNm3 = 25.0,
    )
    coc_btct.summary(plate_length_m=25.0)

    print("\n  LUU Y DON VI:")
    print(f"  Tai lieu: Ec = 43,628.13 MPa")
    print(f"  PLAXIS  : Ec = {mpa_to_knm2(43_628.13):,.0f} kN/m2  (nhan 1,000)")
    print(f"  SAI lam : Ec = 43,628 kN/m2 = {knm2_to_mpa(43_628):.2f} MPa  <- THIEU 1000 LAN!")
