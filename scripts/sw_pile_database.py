"""
BETON 6 SW Prestressed Concrete Sheet Pile Database
Sources:
  - BENTO6-DAC TRUNG HINH HOC SW.pdf  : section geometry (Atd, Itd, Yt, Yb)
  - BENTO6-THONG SO KY THUAT SW.pdf   : technical specs (width, thickness,
                                         Mcr, weight, length range)

Key correction (v2): pile width = 996 mm (SW-120..SW-940) or 1246 mm (SW-1100/1200).
  Earlier assumption of 500 mm was incorrect.
  PLAXIS spacing = pile width when piles touch side-by-side.

Usage:
    from scripts.sw_pile_database import lookup, lookup_first, list_all, SWPile, EC_FC70_KNM2

    pile = lookup_first("SW-840")
    pile.summary(plate_length_m=25.0)

    piles = lookup("SW-400")   # returns [SW-400A, SW-400B]
    list_all()                 # full catalog with PLAXIS EA1/EI
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# Ec for f'c = 70 MPa concrete (= 43,628.13 MPa × 1,000 kN/m²)
EC_FC70_KNM2: float = 43_628_130.0
EC_FC30_KNM2: float = 30_000_000.0

TM_TO_KNM: float = 9.81   # 1 T.m = 9.81 kN.m


@dataclass
class SWPile:
    """One SW prestressed concrete sheet pile (BETON 6).

    Geometry per pile — PLAXIS inputs normalized per meter of wall
    by dividing by spacing_m (= width_m when piles are placed touching).

    Sources:
      Atd, Itd, Yt, Yb : BENTO6-DAC TRUNG HINH HOC SW.pdf
      width, t, Mcr, weight, L_std, L_range : BENTO6-THONG SO KY THUAT SW.pdf
    """

    name: str               # e.g. "SW-840"
    H_mm: int               # pile section depth / CAO (mm)
    n_strands: int          # number of prestress strands
    phi_strand_mm: float    # strand diameter (mm)
    Atd_cm2: float          # transformed section area (cm²)
    Yt_cm: float            # dist. top fiber → neutral axis (cm)
    Yb_cm: float            # dist. bottom fiber → neutral axis (cm)
    Itd_cm4: float          # transformed moment of inertia (cm⁴)
    # --- from THONG SO KY THUAT ---
    width_mm: int = 996     # pile width / RONG (mm): 996 for SW≤940, 1246 for SW≥1100
    t_mm: int = 120         # wall thickness / DAY (mm)
    Mcr_Tm: float = 0.0     # cracking bending moment (T.m)  ≥ value
    weight_T: float = 0.0   # pile weight (T) at standard length
    L_std_m: float = 0.0    # standard (catalog) length (m)
    L_min_m: float = 0.0    # min. available length (m)
    L_max_m: float = 0.0    # max. available length (m)

    # ---------------------------------------------------------------- derived
    @property
    def H_m(self) -> float:
        return self.H_mm / 1_000.0

    @property
    def width_m(self) -> float:
        return self.width_mm / 1_000.0

    @property
    def Atd_m2(self) -> float:
        return self.Atd_cm2 / 10_000.0

    @property
    def Itd_m4(self) -> float:
        return self.Itd_cm4 / 1e8

    @property
    def Mcr_kNm(self) -> float:
        """Cracking moment in kN.m (1 T.m = 9.81 kN.m)."""
        return self.Mcr_Tm * TM_TO_KNM

    @property
    def weight_kN_per_m(self) -> float:
        """Pile self-weight per meter length (kN/m/pile)."""
        if self.L_std_m > 0:
            return self.weight_T * 9.81 / self.L_std_m
        return 0.0

    # -------------------------------------------------------- PLAXIS inputs
    def EA1(
        self,
        Ec_kNm2: float = EC_FC70_KNM2,
        spacing_m: Optional[float] = None,
    ) -> float:
        """Axial stiffness EA1 per meter of wall (kN/m).
        spacing_m defaults to pile width (piles touching).
        """
        sp = spacing_m if spacing_m is not None else self.width_m
        return Ec_kNm2 * self.Atd_m2 / sp

    def EI(
        self,
        Ec_kNm2: float = EC_FC70_KNM2,
        spacing_m: Optional[float] = None,
    ) -> float:
        """Bending stiffness EI per meter of wall (kN.m2/m)."""
        sp = spacing_m if spacing_m is not None else self.width_m
        return Ec_kNm2 * self.Itd_m4 / sp

    def d_eq(
        self,
        Ec_kNm2: float = EC_FC70_KNM2,
        spacing_m: Optional[float] = None,
    ) -> float:
        """Equivalent thickness d_eq (m) — PLAXIS Manual Eq.[54]."""
        ea = self.EA1(Ec_kNm2, spacing_m)
        ei = self.EI(Ec_kNm2, spacing_m)
        return math.sqrt(12.0 * ei / ea)

    def shear_stiffness(
        self,
        Ec_kNm2: float = EC_FC70_KNM2,
        spacing_m: Optional[float] = None,
        nu: float = 0.15,
    ) -> float:
        """Mindlin shear stiffness (kN/m) — PLAXIS Manual Eq.[55]."""
        ea = self.EA1(Ec_kNm2, spacing_m)
        return 5.0 * ea / (12.0 * (1.0 + nu))

    def w_plaxis(self, spacing_m: Optional[float] = None) -> float:
        """Self-weight w per meter of wall (kN/m/m) for PLAXIS plate."""
        sp = spacing_m if spacing_m is not None else self.width_m
        return self.weight_kN_per_m / sp

    # --------------------------------------------------------------- summary
    def summary(
        self,
        Ec_kNm2: float = EC_FC70_KNM2,
        spacing_m: Optional[float] = None,
        plate_length_m: Optional[float] = None,
        nu: float = 0.15,
    ) -> None:
        sp = spacing_m if spacing_m is not None else self.width_m
        ea1 = self.EA1(Ec_kNm2, sp)
        ei  = self.EI(Ec_kNm2, sp)
        deq = self.d_eq(Ec_kNm2, sp)
        shear = self.shear_stiffness(Ec_kNm2, sp, nu)

        print(f"\n{'='*64}")
        print(f"  {self.name}  (BETON 6 — SW Prestressed Concrete Sheet Pile)")
        print(f"{'='*64}")
        print(f"  Section      : H={self.H_mm} mm,  width={self.width_mm} mm,  t={self.t_mm} mm")
        print(f"  Strands      : {self.n_strands} x phi {self.phi_strand_mm} mm")
        print(f"  Atd          : {self.Atd_cm2:.1f} cm2")
        print(f"  Itd          : {self.Itd_cm4:,.0f} cm4")
        print(f"  Yt / Yb      : {self.Yt_cm:.2f} / {self.Yb_cm:.2f} cm")
        if self.Mcr_Tm > 0:
            print(f"  Mcr          : >= {self.Mcr_Tm:.2f} T.m  (= {self.Mcr_kNm:.1f} kN.m)")
        if self.L_std_m > 0:
            print(f"  Length       : std={self.L_std_m:.0f} m,  range {self.L_min_m:.0f}..{self.L_max_m:.0f} m")
        if self.weight_T > 0:
            print(f"  Weight       : {self.weight_T:.2f} T/pile  ({self.weight_kN_per_m:.2f} kN/m)")
        print(f"  ---")
        print(f"  PLAXIS inputs  (Ec={Ec_kNm2/1e6:.3f} GPa,  spacing={sp:.3f} m):")
        print(f"    EA1          : {ea1:>14,.0f}  kN/m")
        print(f"    EI           : {ei:>14,.0f}  kN.m2/m")
        print(f"    nu           : {nu:.2f}  (concrete)")
        print(f"    w            : {self.w_plaxis(sp):>14.3f}  kN/m/m")
        print(f"    d_eq [Eq.54] : {deq:>14.3f}  m")
        print(f"    Shear [Eq.55]: {shear:>14,.0f}  kN/m")
        if plate_length_m is not None:
            ld = plate_length_m / deq
            flag = "OK" if ld >= 10 else "WARN: L/d < 10"
            print(f"    L/d_eq       : {plate_length_m}/{deq:.3f} = {ld:.1f}  [{flag}]")
        print(f"{'='*64}")


# ---------------------------------------------------------------------------
# Complete BETON 6 SW catalog — 22 pile types
# Geometry (Atd/Itd/Yt/Yb): BENTO6-DAC TRUNG HINH HOC SW.pdf
# Tech specs (width/t/Mcr/weight/L): BENTO6-THONG SO KY THUAT SW.pdf
# ---------------------------------------------------------------------------
_CATALOG: list[SWPile] = [
    SWPile("SW-120",  H_mm=120,  n_strands= 8, phi_strand_mm= 9.53,
           Atd_cm2=  548.0, Yt_cm= 6.00, Yb_cm= 6.00, Itd_cm4=    6_514,
           width_mm=996, t_mm= 60, Mcr_Tm=1.53, weight_T=0.83, L_std_m= 5, L_min_m=3, L_max_m= 7),
    SWPile("SW-120",  H_mm=120,  n_strands=10, phi_strand_mm= 9.00,
           Atd_cm2=  556.0, Yt_cm= 6.00, Yb_cm= 6.00, Itd_cm4=    6_544,
           width_mm=996, t_mm= 60, Mcr_Tm=1.53, weight_T=0.83, L_std_m= 5, L_min_m=3, L_max_m= 7),
    SWPile("SW-160",  H_mm=160,  n_strands= 8, phi_strand_mm= 9.53,
           Atd_cm2=  723.0, Yt_cm= 8.00, Yb_cm= 8.00, Itd_cm4=   15_336,
           width_mm=996, t_mm= 80, Mcr_Tm=2.04, weight_T=1.30, L_std_m= 6, L_min_m=4, L_max_m= 8),
    SWPile("SW-160",  H_mm=160,  n_strands= 8, phi_strand_mm= 9.00,
           Atd_cm2=  727.0, Yt_cm= 8.00, Yb_cm= 8.00, Itd_cm4=   15_389,
           width_mm=996, t_mm= 80, Mcr_Tm=2.04, weight_T=1.30, L_std_m= 6, L_min_m=4, L_max_m= 8),
    SWPile("SW-225",  H_mm=225,  n_strands= 8, phi_strand_mm=11.10,
           Atd_cm2=  954.0, Yt_cm=11.25, Yb_cm=11.25, Itd_cm4=   42_780,
           width_mm=996, t_mm=100, Mcr_Tm=4.28, weight_T=2.38, L_std_m= 8, L_min_m=5, L_max_m= 9),
    SWPile("SW-225",  H_mm=225,  n_strands= 8, phi_strand_mm=10.70,
           Atd_cm2=  959.0, Yt_cm=11.25, Yb_cm=11.25, Itd_cm4=   43_003,
           width_mm=996, t_mm=100, Mcr_Tm=4.28, weight_T=2.38, L_std_m= 8, L_min_m=5, L_max_m= 9),
    SWPile("SW-300",  H_mm=300,  n_strands=10, phi_strand_mm=12.70,
           Atd_cm2= 1168.0, Yt_cm=15.00, Yb_cm=15.00, Itd_cm4=  101_168,
           width_mm=996, t_mm=110, Mcr_Tm=9.58, weight_T=3.38, L_std_m=10, L_min_m=7, L_max_m=12),
    SWPile("SW-350A", H_mm=350,  n_strands=14, phi_strand_mm=12.70,
           Atd_cm2= 1376.0, Yt_cm=17.50, Yb_cm=17.50, Itd_cm4=  162_003,
           width_mm=996, t_mm=120, Mcr_Tm=16.31, weight_T=5.00, L_std_m=13, L_min_m=9, L_max_m=15),
    SWPile("SW-350B", H_mm=350,  n_strands=16, phi_strand_mm=12.70,
           Atd_cm2= 1385.0, Yt_cm=17.50, Yb_cm=17.50, Itd_cm4=  162_756,
           width_mm=996, t_mm=120, Mcr_Tm=17.33, weight_T=5.38, L_std_m=14, L_min_m=10, L_max_m=15),
    SWPile("SW-400A", H_mm=400,  n_strands=16, phi_strand_mm=12.70,
           Atd_cm2= 1543.0, Yt_cm=20.00, Yb_cm=20.00, Itd_cm4=  240_449,
           width_mm=996, t_mm=120, Mcr_Tm=20.39, weight_T=6.28, L_std_m=15, L_min_m=10, L_max_m=16),
    SWPile("SW-400B", H_mm=400,  n_strands=18, phi_strand_mm=12.70,
           Atd_cm2= 1552.0, Yt_cm=20.00, Yb_cm=20.00, Itd_cm4=  240_449,
           width_mm=996, t_mm=120, Mcr_Tm=23.45, weight_T=6.68, L_std_m=16, L_min_m=11, L_max_m=16),
    SWPile("SW-450A", H_mm=450,  n_strands=18, phi_strand_mm=12.70,
           Atd_cm2= 1787.0, Yt_cm=22.50, Yb_cm=22.50, Itd_cm4=  341_010,
           width_mm=996, t_mm=120, Mcr_Tm=27.52, weight_T=7.65, L_std_m=16, L_min_m=11, L_max_m=17),
    SWPile("SW-450B", H_mm=450,  n_strands=16, phi_strand_mm=15.24,
           Atd_cm2= 1808.0, Yt_cm=22.50, Yb_cm=22.50, Itd_cm4=  348_089,
           width_mm=996, t_mm=120, Mcr_Tm=31.60, weight_T=8.13, L_std_m=17, L_min_m=12, L_max_m=17),
    SWPile("SW-500A", H_mm=500,  n_strands=16, phi_strand_mm=15.24,
           Atd_cm2= 1885.0, Yt_cm=25.00, Yb_cm=25.00, Itd_cm4=  467_240,
           width_mm=996, t_mm=120, Mcr_Tm=35.68, weight_T=8.13, L_std_m=17, L_min_m=12, L_max_m=19),
    SWPile("SW-500B", H_mm=500,  n_strands=20, phi_strand_mm=15.24,
           Atd_cm2= 1910.0, Yt_cm=25.00, Yb_cm=25.00, Itd_cm4=  469_288,
           width_mm=996, t_mm=120, Mcr_Tm=40.77, weight_T=8.58, L_std_m=18, L_min_m=13, L_max_m=20),
    SWPile("SW-600A", H_mm=600,  n_strands=20, phi_strand_mm=15.24,
           Atd_cm2= 2262.0, Yt_cm=30.00, Yb_cm=30.00, Itd_cm4=  795_348,
           width_mm=996, t_mm=120, Mcr_Tm=50.97, weight_T=10.38, L_std_m=19, L_min_m=14, L_max_m=22),
    SWPile("SW-600B", H_mm=600,  n_strands=24, phi_strand_mm=15.24,
           Atd_cm2= 2288.0, Yt_cm=30.00, Yb_cm=30.00, Itd_cm4=  797_396,
           width_mm=996, t_mm=120, Mcr_Tm=60.14, weight_T=10.88, L_std_m=20, L_min_m=15, L_max_m=24),
    SWPile("SW-740",  H_mm=740,  n_strands=20, phi_strand_mm=15.24,
           Atd_cm2= 2794.0, Yt_cm=37.00, Yb_cm=37.00, Itd_cm4=1_480_428,
           width_mm=996, t_mm=160, Mcr_Tm=60.40, weight_T=14.55, L_std_m=21, L_min_m=16, L_max_m=28),
    SWPile("SW-840",  H_mm=840,  n_strands=22, phi_strand_mm=15.24,
           Atd_cm2= 3107.0, Yt_cm=42.00, Yb_cm=42.00, Itd_cm4=2_125_017,
           width_mm=996, t_mm=160, Mcr_Tm=77.10, weight_T=16.35, L_std_m=22, L_min_m=17, L_max_m=29),
    SWPile("SW-940",  H_mm=940,  n_strands=24, phi_strand_mm=15.24,
           Atd_cm2= 3544.0, Yt_cm=47.00, Yb_cm=47.00, Itd_cm4=2_983_488,
           width_mm=996, t_mm=160, Mcr_Tm=93.30, weight_T=18.31, L_std_m=23, L_min_m=17, L_max_m=30),
    SWPile("SW-1100", H_mm=1100, n_strands=28, phi_strand_mm=15.24,
           Atd_cm2= 5327.0, Yt_cm=55.00, Yb_cm=55.00, Itd_cm4=5_663_367,
           width_mm=1246, t_mm=200, Mcr_Tm=136.00, weight_T=25.80, L_std_m=24, L_min_m=17, L_max_m=32),
    SWPile("SW-1200", H_mm=1200, n_strands=30, phi_strand_mm=15.24,
           Atd_cm2= 5789.7, Yt_cm=60.00, Yb_cm=60.00, Itd_cm4=7_318_551,
           width_mm=1246, t_mm=200, Mcr_Tm=158.00, weight_T=28.75, L_std_m=25, L_min_m=17, L_max_m=34),
]


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def lookup(name: str) -> list[SWPile]:
    """Return all pile variants matching name (case-insensitive, flexible separator).

    Examples:
        lookup("SW-840")  -> [SWPile("SW-840", ...)]
        lookup("SW400A")  -> [SWPile("SW-400A", ...)]
        lookup("sw-120")  -> two SW-120 variants
    """
    normalized = name.strip().upper().replace(" ", "").replace("_", "-")
    if not normalized.startswith("SW-"):
        normalized = normalized.replace("SW", "SW-", 1)
    return [p for p in _CATALOG if p.name.upper() == normalized]


def lookup_first(name: str) -> SWPile:
    """Return first pile matching name. Raises ValueError if not found."""
    results = lookup(name)
    if not results:
        available = sorted({p.name for p in _CATALOG})
        raise ValueError(f"Pile '{name}' not found. Available: {available}")
    return results[0]


def list_all(
    Ec_kNm2: float = EC_FC70_KNM2,
    use_pile_width: bool = True,
    spacing_m: Optional[float] = None,
) -> None:
    """Print full catalog table with PLAXIS EA1 and EI.

    Args:
        use_pile_width : if True, spacing = pile width (default, piles touching)
        spacing_m      : override spacing for all piles
    """
    hdr = (
        f"{'No':>3}  {'Name':<9}  {'W':>5}  {'H':>5}  {'t':>4}  {'n':>3}  {'phi':>5}  "
        f"{'Atd':>7}  {'Itd':>11}  {'Mcr':>7}  "
        f"{'EA1':>13}  {'EI':>12}  {'d_eq':>6}  {'L-range':>10}"
    )
    print(f"\nBETON 6 SW Catalog v2  (Ec={Ec_kNm2/1e6:.3f} GPa)")
    print(f"  Sources: DAC TRUNG HINH HOC SW + THONG SO KY THUAT SW (BETON 6)")
    print(f"{'='*len(hdr)}")
    print(hdr)
    print(
        f"{'':>3}  {'':9}  {'mm':>5}  {'mm':>5}  {'mm':>4}  {'':>3}  {'mm':>5}  "
        f"{'cm2':>7}  {'cm4':>11}  {'T.m':>7}  "
        f"{'kN/m':>13}  {'kN.m2/m':>12}  {'m':>6}  {'m':>10}"
    )
    print(f"{'-'*len(hdr)}")
    for i, p in enumerate(_CATALOG, 1):
        sp = spacing_m if spacing_m is not None else (p.width_m if use_pile_width else 1.0)
        ea1 = p.EA1(Ec_kNm2, sp)
        ei  = p.EI(Ec_kNm2, sp)
        deq = p.d_eq(Ec_kNm2, sp)
        lrange = f"{p.L_min_m:.0f}..{p.L_max_m:.0f}" if p.L_max_m else ""
        mcr_str = f">={p.Mcr_Tm:.2f}" if p.Mcr_Tm else ""
        print(
            f"{i:>3}  {p.name:<9}  {p.width_mm:>5}  {p.H_mm:>5}  {p.t_mm:>4}  "
            f"{p.n_strands:>3}  {p.phi_strand_mm:>5.2f}  "
            f"{p.Atd_cm2:>7.1f}  {p.Itd_cm4:>11,.0f}  {mcr_str:>7}  "
            f"{ea1:>13,.0f}  {ei:>12,.0f}  {deq:>6.3f}  {lrange:>10}"
        )
    print(f"{'='*len(hdr)}")
    print(f"  EA1/EI computed with spacing = pile width (piles touching side-by-side)")
    print(f"  Mcr: cracking bending moment (T.m). 1 T.m = 9.81 kN.m")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick lookup
    pile = lookup_first("SW-840")
    pile.summary(plate_length_m=25.0)

    # SW-400 variants
    print("\nSW-400 variants:")
    for p in lookup("SW-400A") + lookup("SW-400B"):
        sp = p.width_m
        print(f"  {p.name}: width={p.width_mm}mm  Atd={p.Atd_cm2}cm2  "
              f"Itd={p.Itd_cm4:,}cm4  Mcr>={p.Mcr_Tm}T.m  "
              f"EA1={p.EA1():,.0f}kN/m  EI={p.EI():,.0f}kN.m2/m")

    # Full catalog
    list_all(Ec_kNm2=EC_FC70_KNM2)
