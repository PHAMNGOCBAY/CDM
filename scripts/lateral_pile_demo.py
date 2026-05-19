"""
Demo: Phân tích cọc tải ngang + hệ số nền + dầm đàn hồi
Thư viện: openpile, geolysis, anastruct, numpy, matplotlib

Chạy:  python scripts/lateral_pile_demo.py
"""
import sys
import numpy as np
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")

# ===========================================================================
# 1. HỆ SỐ NỀN Ks — phương pháp Bowles (1996) qua geolysis
# ===========================================================================

def ks_bowles(qa_kNm2: float, SF: float = 3.0) -> float:
    """Ks = 40 * SF * qa  [kN/m³]  (Bowles 1996, hệ SI, giả định s_cho_phep = 25mm)."""
    return 40.0 * SF * qa_kNm2

def ks_vesic(Es_kNm2: float, nu: float, B_m: float, EI_kNm2: float) -> float:
    """Ks = 0.65*Es/(1-nu²) * (Es*B⁴/EI)^(1/12)  [kN/m³]  (Vesic 1961)."""
    ratio = (Es_kNm2 * B_m**4 / EI_kNm2) ** (1.0 / 12.0)
    return 0.65 * Es_kNm2 / (1.0 - nu**2) * ratio


def demo_ks() -> None:
    print("=" * 60)
    print("1. HỆ SỐ PHẢN LỰC NỀN Ks")
    print("=" * 60)

    # Thông số ví dụ: đất cát, N_SPT=15, phi=30°
    # qa ước tính theo Terzaghi (~150 kN/m²)
    qa = 150.0
    Ks_bowles = ks_bowles(qa, SF=3.0)
    print(f"  Bowles 1996 : qa = {qa} kN/m²  →  Ks = {Ks_bowles:.0f} kN/m³")

    Es, nu, B, EI = 20_000.0, 0.3, 1.5, 50_000.0
    Ks_vesic = ks_vesic(Es, nu, B, EI)
    print(f"  Vesic 1961  : Es = {Es} kN/m², B = {B} m  →  Ks = {Ks_vesic:.0f} kN/m³")
    print()


# ===========================================================================
# 2. CỌC TẢI NGANG — openpile (1D FEM, đường cong p-y API)
# ===========================================================================

def demo_openpile() -> None:
    print("=" * 60)
    print("2. CỌC TẢI NGANG — openpile")
    print("=" * 60)
    try:
        from openpile.construct import Pile, SoilProfile, Layer, Model, BoundaryFixation
        from openpile.soilmodels import API_sand
        from openpile.winkler import winkler

        # Cọc thép tròn D=840mm, t=16mm (wt), L=20m — demo địa tầng cát
        L_pile = 20.0
        pile = Pile.create_tubular(
            name="Demo D840",
            top_elevation=0.0,
            bottom_elevation=-L_pile,
            diameter=0.840,
            wt=0.016,
        )

        sp = SoilProfile(
            name="Cát hai lớp",
            top_elevation=0.0,
            water_line=-1.0,
            layers=[
                Layer(name="Cát phi=30", top=0.0, bottom=-10.0,
                      weight=18.0, lateral_model=API_sand(phi=30.0, kind="static")),
                Layer(name="Cát phi=35", top=-10.0, bottom=-L_pile,
                      weight=19.0, lateral_model=API_sand(phi=35.0, kind="static")),
            ],
        )

        # Bắt buộc: ngàm cứng tại mũi cọc để hội tụ
        bc = [BoundaryFixation(elevation=-L_pile, x=True, y=True, z=True)]
        model = Model(name="demo", pile=pile, soil=sp, boundary_conditions=bc)
        model.set_pointload(elevation=0.0, Py=100.0)  # Lực ngang 100 kN

        result = winkler(model)
        y_head = abs(result.deflection["Deflection [m]"].iloc[0]) * 1000  # mm
        M_max  = result.forces["M [kNm]"].abs().max()

        print(f"  Cọc: D=840mm, L={L_pile}m  |  Lực ngang H=100 kN")
        print(f"  Độ võng đỉnh cọc     : {y_head:.2f} mm")
        print(f"  Mô men uốn lớn nhất  : {M_max:.1f} kN·m")

    except Exception as exc:
        print(f"  [openpile] {exc}")
    print()


# ===========================================================================
# 3. DẦM TRÊN NỀN ĐÀN HỒI WINKLER — anastruct
# ===========================================================================

def demo_anastruct(Ks: float = 18_000.0) -> None:
    """
    Mô hình dầm bê tông cốt thép L=10m trên nền Winkler.
    Tải trọng tập trung P=200 kN tại giữa dầm.
    Ks: hệ số phản lực nền [kN/m³]
    b = 1.0m (bề rộng móng băng), dx = 1.0m (bước lưới)
    """
    print("=" * 60)
    print("3. DẦM MÓNG BĂNG TRÊN NỀN WINKLER — anastruct")
    print("=" * 60)
    try:
        from anastruct import SystemElements

        L      = 10.0   # m — chiều dài dầm
        dx     = 1.0    # m — bước lưới
        b      = 1.0    # m — bề rộng móng
        EI     = 1.2e5  # kN·m² — dầm BTCT 0.5×1.0m, E=30 GPa
        EA     = 1.5e7  # kN
        k_node = Ks * b * dx  # kN/m — độ cứng lò xo tại mỗi nút

        ss = SystemElements()
        n = int(L / dx)
        for i in range(n):
            ss.add_element(
                location=[[i * dx, 0], [(i + 1) * dx, 0]],
                EI=EI, EA=EA,
            )

        # Lò xo nền tại mọi nút (translation=2 → phương Y)
        for node in range(1, n + 2):
            ss.add_support_spring(node_id=node, translation=2, k=k_node)

        # Tải trọng tập trung tại giữa dầm
        mid_node = n // 2 + 1
        ss.point_load(node_id=mid_node, Fy=-200.0)

        ss.solve()

        # Lấy kết quả độ võng tại các nút
        displacements = [ss.get_node_displacements(n)["uy"] * 1000
                         for n in range(1, n + 2)]
        y_max = max(abs(v) for v in displacements)
        print(f"  Dầm L={L}m, EI={EI:.0e} kN·m², Ks={Ks:.0f} kN/m³")
        print(f"  P=200 kN tại giữa dầm")
        print(f"  Độ võng lớn nhất : {y_max:.2f} mm")

        # Vẽ biểu đồ
        x_vals = np.linspace(0, L, n + 1)
        plt.figure(figsize=(8, 3))
        plt.plot(x_vals, displacements, "b-o", markersize=4)
        plt.xlabel("Vị trí dọc dầm (m)")
        plt.ylabel("Độ võng (mm)")
        plt.title(f"Dầm móng băng trên nền Winkler  |  Ks = {Ks:.0f} kN/m³")
        plt.axhline(0, color="k", linewidth=0.5)
        plt.grid(True, alpha=0.4)
        plt.tight_layout()
        out_fig = "scripts/output_beam_winkler.png"
        plt.savefig(out_fig, dpi=120)
        plt.close()
        print(f"  Biểu đồ đã lưu: {out_fig}")

    except Exception as exc:
        print(f"  [anastruct] {exc}")
    print()


# ===========================================================================
# 4. KS PHÂN BỐ — ví dụ tính thủ công nhiều điểm
# ===========================================================================

def demo_ks_distribution() -> None:
    print("=" * 60)
    print("4. Ks PHÂN BỐ — Vesic theo chiều sâu móng Df")
    print("=" * 60)

    Es_profile = [10_000, 15_000, 20_000, 25_000, 30_000]  # kN/m² tại 0–4m
    B, nu, EI = 1.5, 0.3, 50_000.0

    print(f"  {'Df (m)':<8} {'Es (kN/m²)':<14} {'Ks Vesic (kN/m³)'}")
    print(f"  {'-'*40}")
    for i, Es in enumerate(Es_profile):
        Ks = ks_vesic(Es, nu, B, EI)
        print(f"  {i:<8} {Es:<14} {Ks:.0f}")
    print()


# ===========================================================================
# main
# ===========================================================================

if __name__ == "__main__":
    demo_ks()
    demo_ks_distribution()
    demo_openpile()
    demo_anastruct(Ks=18_000.0)
    print("Hoàn tất demo.")
