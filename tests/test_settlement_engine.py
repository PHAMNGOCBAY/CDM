"""
tests/test_settlement_engine.py — Golden tests cho settlement engine.

calc_settlement_S1 — TCVN 9403 Phụ lục C công thức C.6:
  S₁ = q·H / (a·Ec + (1-a)·Es)  [m] → returned in CM

Hàm đã nhân 100 bên trong → đơn vị trả về là cm.
"""
from __future__ import annotations

import pytest

from cdm_column_calc import calc_settlement_S1, calc_area_ratio, calc_Ec, calc_Es


class TestCalcSettlementS1:
    """Pin giá trị S1 cho cấu hình TTHC. Đơn vị trả về: cm."""

    def test_baseline_TTHC(self):
        """q=40.8, H=23, a=0.155, Ec=40000, Es=2859 — TTHC baseline."""
        S1_cm = calc_settlement_S1(
            q_kPa=40.8, H_m=23.0, area_ratio=0.155,
            Ec_kPa=40000.0, Es_kPa=2859.0,
        )
        # S1 (m) = 40.8 × 23 / (0.155×40000 + 0.845×2859) = 0.1089 m
        # → S1_cm = 10.89 cm
        assert S1_cm == pytest.approx(10.89, abs=0.1)

    def test_zero_a_pure_soil(self):
        """a=0 → S1 = q·H/Es × 100 (cm)."""
        S1_cm = calc_settlement_S1(
            q_kPa=50.0, H_m=10.0, area_ratio=0.0,
            Ec_kPa=40000.0, Es_kPa=2500.0,
        )
        # S1 (m) = 50 × 10 / 2500 = 0.2 → 20 cm
        assert S1_cm == pytest.approx(20.0, abs=1e-3)

    def test_a_one_pure_column(self):
        """a=1 → S1 = q·H/Ec × 100 (cm)."""
        S1_cm = calc_settlement_S1(
            q_kPa=50.0, H_m=10.0, area_ratio=1.0,
            Ec_kPa=40000.0, Es_kPa=2500.0,
        )
        # S1 (m) = 50 × 10 / 40000 = 0.0125 → 1.25 cm
        assert S1_cm == pytest.approx(1.25, abs=1e-3)

    def test_inverse_proportional_to_E(self):
        """Nhân đôi cả Ec và Es → S1 giảm đúng 1/2."""
        s1 = calc_settlement_S1(q_kPa=40.8, H_m=23, area_ratio=0.155,
                                  Ec_kPa=40000, Es_kPa=2859)
        s2 = calc_settlement_S1(q_kPa=40.8, H_m=23, area_ratio=0.155,
                                  Ec_kPa=80000, Es_kPa=5718)
        assert s2 == pytest.approx(s1 / 2, rel=1e-6)

    def test_proportional_to_q_and_H(self):
        """S1 tuyến tính theo q và H."""
        s1 = calc_settlement_S1(q_kPa=40.0, H_m=20.0, area_ratio=0.155,
                                  Ec_kPa=40000, Es_kPa=2859)
        s2 = calc_settlement_S1(q_kPa=80.0, H_m=20.0, area_ratio=0.155,
                                  Ec_kPa=40000, Es_kPa=2859)
        assert s2 == pytest.approx(2 * s1, rel=1e-9)
        s3 = calc_settlement_S1(q_kPa=40.0, H_m=40.0, area_ratio=0.155,
                                  Ec_kPa=40000, Es_kPa=2859)
        assert s3 == pytest.approx(2 * s1, rel=1e-9)


class TestAreaRatio:
    """Tỷ lệ thay thế a = Ac/A_unit."""

    def test_square_TTHC(self):
        """D=0.80, s=1.80, lưới vuông → a = π(0.4)²/1.80² ≈ 0.155"""
        a = calc_area_ratio(0.80, 1.80, "square")
        assert a == pytest.approx(0.155, abs=1e-3)

    def test_a_increases_with_D(self):
        """D lớn → a tăng (D² scaling)."""
        a_small = calc_area_ratio(0.60, 1.80, "square")
        a_big = calc_area_ratio(1.00, 1.80, "square")
        assert a_big > a_small

    def test_a_decreases_with_s(self):
        """s lớn → a giảm (1/s² scaling)."""
        a_dense = calc_area_ratio(0.80, 1.50, "square")
        a_sparse = calc_area_ratio(0.80, 2.50, "square")
        assert a_dense > a_sparse


class TestEcEs:
    """Mô đun đàn hồi."""

    def test_Ec_default(self):
        """Ec = 75 × Cc_col (TCVN 9403 B.5.1, k=75 mặc định)."""
        Ec = calc_Ec(400.0)
        assert Ec == pytest.approx(75 * 400.0, abs=1e-6)

    def test_Ec_custom_factor(self):
        """Ec = k × Cc_col, k editable."""
        Ec = calc_Ec(400.0, factor=100)
        assert Ec == pytest.approx(100 * 400.0, abs=1e-6)

    def test_Es_default(self):
        """Es = 250 × Cu (Mesri & Olson)."""
        Es = calc_Es(12.0)
        assert Es == pytest.approx(250 * 12.0, abs=1e-6)
