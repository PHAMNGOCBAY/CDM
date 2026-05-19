"""
Demo geotech-staff-engineer 4.6.0 — API da kiem tra thuc te.

Chay: python scripts/geotech_staff_engineer_demo.py

Tham khao: 28-geotech-staff-engineer.md, data/geotech_staff_engineer.json
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. bearing_capacity — Mong nong Meyerhof/Vesic
# ---------------------------------------------------------------------------
def demo_bearing_capacity() -> None:
    from bearing_capacity import (
        BearingCapacityAnalysis, Footing,
        BearingSoilProfile, SoilLayer,
    )

    footing = Footing(width=2.0, length=2.0, depth=1.5, shape="square")
    layer1 = SoilLayer(friction_angle=25.0, cohesion=10.0, unit_weight=18.0)
    soil = BearingSoilProfile(layer1=layer1, gwt_depth=3.0)
    analysis = BearingCapacityAnalysis(
        footing=footing, soil=soil,
        vertical_load=500.0,        # kN
        factor_of_safety=3.0,
    )
    result = analysis.compute()

    print("=== bearing_capacity ===")
    print(f"  q_ult     = {result.q_ultimate:.1f}  kPa")
    print(f"  q_allow   = {result.q_allowable:.1f}  kPa  (FS=3)")
    print()


# ---------------------------------------------------------------------------
# 2. settlement — Do lun Terzaghi 1-D
# ---------------------------------------------------------------------------
def demo_settlement() -> None:
    from settlement import (
        SettlementAnalysis, ConsolidationLayer,
        time_factor, degree_of_consolidation,
    )

    layer = ConsolidationLayer(
        thickness=3.0,
        depth_to_center=1.5,
        e0=1.2,
        Cc=0.35,
        Cr=0.06,
        sigma_v0=40.0,    # kPa — initial effective stress
        sigma_p=60.0,     # kPa — preconsolidation
    )
    cv_m2s = 5e-8          # m2/s — dat set mem dien hinh
    analysis = SettlementAnalysis(
        q_applied=30.0,
        B=2.0, L=2.0,
        consolidation_layers=[layer],
        cv=cv_m2s,
        Hdr=1.5,           # m — one-way drainage
    )
    result = analysis.compute()

    t_sec = 1.0 * 365.25 * 24 * 3600   # 1 nam
    Tv = time_factor(cv=cv_m2s, t=t_sec, Hdr=1.5)
    U  = degree_of_consolidation(Tv)

    print("=== settlement ===")
    print(f"  S_c_total = {result.consolidation * 1000:.1f}  mm")
    print(f"  Tv (1 nam) = {Tv:.3f},  U = {U:.1f}%")
    print()


# ---------------------------------------------------------------------------
# 3. axial_pile — Coc dong FHWA GEC-12
# ---------------------------------------------------------------------------
def demo_axial_pile() -> None:
    from axial_pile import (
        AxialPileAnalysis, AxialSoilLayer, AxialSoilProfile,
        make_pipe_pile,
    )

    # SW-840: D=840mm, t=100mm BTCT (dung pipe pile tuong duong)
    pile = make_pipe_pile(diameter=0.84, thickness=0.1, closed_end=True, E=25_000_000.0)
    soil = AxialSoilProfile(layers=[
        AxialSoilLayer(thickness=5.0,  soil_type="cohesive",    unit_weight=17.0,
                       friction_angle=0.0, cohesion=10.0),
        AxialSoilLayer(thickness=15.0, soil_type="cohesionless", unit_weight=19.0,
                       friction_angle=30.0, cohesion=0.0),
    ], gwt_depth=1.0)
    analysis = AxialPileAnalysis(
        pile=pile, soil=soil,
        pile_length=20.0,
        method="auto",
        factor_of_safety=2.5,
    )
    result = analysis.compute()

    print("=== axial_pile (FHWA GEC-12) ===")
    print(f"  Q_skin  = {result.Q_skin:.1f}  kN")
    print(f"  Q_tip   = {result.Q_tip:.1f}   kN")
    print(f"  Q_ult   = {result.Q_ultimate:.1f}  kN")
    print(f"  Q_allow = {result.Q_allowable:.1f}  kN  (FS={result.factor_of_safety})")
    print()


# ---------------------------------------------------------------------------
# 4. sheet_pile — Ke coc ban consolle
# ---------------------------------------------------------------------------
def demo_sheet_pile() -> None:
    from sheet_pile import analyze_cantilever, WallSoilLayer

    layers = [
        WallSoilLayer(thickness=5.0,  unit_weight=17.0, friction_angle=0.0,  cohesion=20.0),
        WallSoilLayer(thickness=10.0, unit_weight=19.0, friction_angle=30.0, cohesion=0.0),
    ]
    result = analyze_cantilever(
        excavation_depth=3.0,
        soil_layers=layers,
        gwt_depth_active=2.0,
        gwt_depth_passive=5.0,
        FOS_passive=1.5,
    )

    print("=== sheet_pile — consolle (Rankine) ===")
    print(f"  Chieu sau ngam = {result.embedment_depth:.2f}  m")
    print(f"  Tong chieu dai = {result.total_wall_length:.2f}  m")
    print(f"  M_max          = {result.max_moment:.1f}   kN.m/m")
    print()


# ---------------------------------------------------------------------------
# 5. soe — Ho dao co chong da tang
# ---------------------------------------------------------------------------
def demo_soe() -> None:
    from soe import (
        analyze_braced_excavation, ExcavationGeometry,
        SOEWallLayer, SupportLevel,
        check_basal_heave_terzaghi,
    )

    geom = ExcavationGeometry(
        excavation_depth=6.0,
        excavation_width=8.0,
        soil_layers=[
            SOEWallLayer(thickness=10.0, unit_weight=17.0,
                         friction_angle=0.0, cohesion=25.0, soil_type="soft_clay"),
        ],
        support_levels=[
            SupportLevel(depth=1.0),
            SupportLevel(depth=3.5),
        ],
        surcharge=10.0,
    )
    result = analyze_braced_excavation(geometry=geom)

    heave = check_basal_heave_terzaghi(H=6.0, cu=25.0, gamma=17.0, B=8.0)

    print("=== soe — ho dao co chong (Terzaghi-Peck) ===")
    print(f"  M_max = {result.max_moment_kNm_per_m:.1f}  kN.m/m")
    print(f"  V_max = {result.max_shear_kN_per_m:.1f}   kN/m")
    print(f"  Chieu sau ngam can = {result.required_embedment_m:.2f}  m")
    for i, d in enumerate(result.support_reactions):
        F = d.get("reaction_kN_per_m", d.get("force", list(d.values())[0]))
        print(f"  Strut {i+1} = {F:.1f}  kN/m")
    print(f"  Fs_heave (Terzaghi) = {heave.FOS:.2f}  {'OK' if heave.passes else 'FAIL'}")
    print()


# ---------------------------------------------------------------------------
# 6. slope_stability — On dinh mai doc Bishop
# ---------------------------------------------------------------------------
def demo_slope_stability() -> None:
    from slope_stability import analyze_slope, SlopeGeometry, SlopeSoilLayer

    # Mat cat mai doc don gian: H=8m, goc 30 do
    import math
    H = 8.0
    cot_len = H / math.tan(math.radians(30))  # ~13.86m
    # surface: toe (0,0) -> crest (cot_len, H) -> flat top (cot_len+10, H)
    surface_pts = [(0.0, 0.0), (cot_len, H), (cot_len + 10.0, H)]

    layer = SlopeSoilLayer(
        name="Clay",
        top_elevation=H,
        bottom_elevation=-5.0,
        gamma=18.0,
        phi=20.0,
        c_prime=10.0,
    )
    geom = SlopeGeometry(surface_points=surface_pts, soil_layers=[layer])

    # Chon mat truot: tam o giua mai, du lon de cat qua 2 diem tren mat dat
    xc = cot_len / 2.0
    yc = H + 5.0
    R  = math.sqrt((xc - 0.0)**2 + (yc - 0.0)**2) * 0.95  # cat qua chan mai
    result = analyze_slope(geom=geom, xc=xc, yc=yc, radius=R, method="bishop")

    print("=== slope_stability (Bishop) ===")
    print(f"  FoS_Bishop    = {result.FOS:.3f}")
    if result.FOS_fellenius is not None:
        print(f"  FoS_Fellenius = {result.FOS_fellenius:.3f}")
    print()


# ---------------------------------------------------------------------------
# 7. seismic_geotech — Mononobe-Okabe
# ---------------------------------------------------------------------------
def demo_seismic() -> None:
    from seismic_geotech import mononobe_okabe_KAE, seismic_earth_pressure
    from sheet_pile import rankine_Ka

    phi, kh, H, gamma = 30.0, 0.15, 6.0, 18.0
    KAE = mononobe_okabe_KAE(phi_deg=phi, delta_deg=0.0, kh=kh, kv=0.0)
    KA  = rankine_Ka(phi)
    result = seismic_earth_pressure(gamma=gamma, H=H, KAE=KAE, KA=KA)

    print("=== seismic_geotech — Mononobe-Okabe ===")
    print(f"  KAE = {KAE:.4f}")
    print(f"  KA  = {KA:.4f}")
    for k, v in result.items():
        print(f"  {k} = {v:.3f}")
    print()


# ---------------------------------------------------------------------------
# 8. wave_equation — Phuong trinh song dong coc (Smith 1-D)
# ---------------------------------------------------------------------------
def demo_wave_equation() -> None:
    from wave_equation import (
        get_hammer, make_cushion_from_properties,
        discretize_pile, SmithSoilModel, generate_bearing_graph,
    )

    hammer = get_hammer("Delmag D30-32")
    cushion = make_cushion_from_properties(
        area=0.04,           # m2
        thickness=0.075,     # m
        elastic_modulus=200_000.0,  # kPa (wood cushion ~200 MPa)
        cor=0.8,
    )
    pile = discretize_pile(
        length=20.0,
        area=5.5e-4 * 3.14159,   # ~SW-840 net area ~1730 cm2, dung hon
        elastic_modulus=25_000_000.0,  # kPa BTCT
        segment_length=1.0,
        unit_weight_material=24.0,
    )
    soil = SmithSoilModel(R_ultimate=800.0, quake=2.5e-3, damping=0.5)

    bg = generate_bearing_graph(
        hammer=hammer, cushion=cushion, pile=pile,
        skin_fraction=0.8,
        R_min=200.0, R_max=1600.0, R_step=200.0,
    )

    print("=== wave_equation (Smith 1-D) ===")
    print(f"  Hammer: {hammer.name}")
    print(f"  Rult [kN] | Blow count [blows/m]")
    for R_val, bc in zip(bg.R_values, bg.blow_counts):
        print(f"    {R_val:6.0f}   |   {bc:5.1f}")
    print()


# ---------------------------------------------------------------------------
# 9. geotech_common — Doi don vi + SPT correlation
# ---------------------------------------------------------------------------
def demo_common() -> None:
    from geotech_common.units import kPa_to_ksf, kNm3_to_pcf
    from geotech_common.soil_properties import spt_to_phi, spt_to_cu

    print("=== geotech_common — don vi + SPT ===")
    print(f"  100 kPa  -> {kPa_to_ksf(100):.3f}  ksf")
    print(f"  18 kN/m3 -> {kNm3_to_pcf(18):.2f}  pcf")
    for N in [5, 10, 15, 25]:
        print(f"  N={N:2d}: phi={spt_to_phi(N):.1f} deg,  cu={spt_to_cu(N):.1f} kPa")
    print()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("geotech-staff-engineer 4.6.0 — Demo cac module chinh\n")

    for name, fn in [
        ("bearing_capacity", demo_bearing_capacity),
        ("settlement",       demo_settlement),
        ("axial_pile",       demo_axial_pile),
        ("sheet_pile",       demo_sheet_pile),
        ("soe",              demo_soe),
        ("slope_stability",  demo_slope_stability),
        ("seismic_geotech",  demo_seismic),
        ("wave_equation",    demo_wave_equation),
        ("geotech_common",   demo_common),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"  {name} ERROR: {e}\n")
