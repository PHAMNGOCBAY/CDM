"""
tests/test_alicc_cushion.py — Golden tests cho engine ALiCC.

Cố định: q_uckse=600, Fs=3, theta=80°, D=0.80, s=1.80, gamma_TB=21.2

Bộ giá trị tham chiếu được verify thủ công với Excel hồ sơ
'02. Tính toán CDM (2Tm2).xlsm' sheet 'Tinh choc thung '.
"""
from __future__ import annotations

import pytest

from cdm_cushion_params import check_alicc, find_Hse_min


# ════════ Golden inputs/outputs ════════
TOL = 1e-3        # tolerance cho giá trị tính (0.1%)
TOL_RATIO = 1e-2  # tolerance cho ratio (1%)


class TestCheckAlicc:
    """Pin các giá trị tính ALiCC cho 5 cấu hình chuẩn."""

    def test_baseline_Hse_040_qu_600(self):
        """Cấu hình hiện trạng TTHC — KĐ với ratio = 1.247."""
        r = check_alicc(0.40, q_uckse=600.0)
        assert r["tau_ase_kPa"] == pytest.approx(100.0, rel=TOL)
        assert r["ratio"] == pytest.approx(1.247, abs=TOL_RATIO)
        assert r["ok"] is False
        # γ_TB phải là TB trọng số (áo đường + He), KHÔNG dùng γ_he đơn lẻ
        assert r["gamma_fill_TB"] == pytest.approx(21.2, abs=1e-2)
        # H_se=0.40, He=0.70 → γ_TB = (0.8×24 + 0.7×18)/1.5 = 21.2
        # He_total = h_aod + He = 0.8 + 0.7 = 1.5 (chiều cao đắp TRÊN đệm cho ALiCC)
        assert r["He_total_m"] == pytest.approx(1.50, abs=1e-3)

    def test_hse_min_pass_504(self):
        """Hse=0.504m là biên ĐẠT (ratio=1.0)."""
        r = check_alicc(0.504, q_uckse=600.0)
        assert r["ratio"] == pytest.approx(1.000, abs=TOL_RATIO)
        assert r["ok"] is True

    def test_option_A_pass(self):
        """PA A — giữ Hse=0.40, tăng q_uckse=800 → ratio 0.94."""
        r = check_alicc(0.40, q_uckse=800.0)
        assert r["ratio"] == pytest.approx(0.936, abs=TOL_RATIO)
        assert r["ok"] is True

    def test_option_B_pass(self):
        """PA B — giữ q_uckse=600, tăng Hse=0.55 → ratio 0.92."""
        r = check_alicc(0.55, q_uckse=600.0)
        assert r["ratio"] == pytest.approx(0.917, abs=TOL_RATIO)
        assert r["ok"] is True

    def test_option_C_borderline(self):
        """PA C — Hse=0.30 + q_uckse=1000 → ratio cận 1."""
        r = check_alicc(0.30, q_uckse=1000.0)
        assert r["ratio"] == pytest.approx(0.991, abs=TOL_RATIO)
        assert r["ok"] is True


class TestFindHseMin:
    """Bisection tìm Hse min."""

    def test_default_finds_504(self):
        h = find_Hse_min(target_ratio=1.0)
        assert h == pytest.approx(0.504, abs=5e-3)

    def test_higher_quckse_lower_Hse_min(self):
        """q_uckse cao hơn → Hse_min thấp hơn."""
        h_600 = find_Hse_min(target_ratio=1.0, q_uckse=600.0)
        h_800 = find_Hse_min(target_ratio=1.0, q_uckse=800.0)
        h_1000 = find_Hse_min(target_ratio=1.0, q_uckse=1000.0)
        assert h_600 > h_800 > h_1000


class TestAliccPhysics:
    """Kiểm tra tính chất vật lý — không phụ thuộc giá trị cụ thể."""

    def test_tau_ase_formula(self):
        """τ_ase = q_uckse / (2·Fs) — bất biến với mọi Hse."""
        for Hse in (0.30, 0.50, 0.70):
            r = check_alicc(Hse, q_uckse=900.0, Fs=2.5)
            expected = 900.0 / (2.0 * 2.5)
            assert r["tau_ase_kPa"] == pytest.approx(expected, rel=TOL)

    def test_ratio_decreases_with_Hse(self):
        """Tăng Hse (giữ q_uckse) → ratio giảm."""
        ratios = [check_alicc(h, q_uckse=600.0)["ratio"]
                  for h in (0.30, 0.40, 0.50, 0.60, 0.70)]
        for i in range(len(ratios) - 1):
            assert ratios[i] > ratios[i + 1], f"ratios={ratios}"

    def test_gamma_TB_weighted(self):
        """γ_TB = (h_aod·γ_aod + He·γ_he) / (h_aod + He) — verify thủ công."""
        # Hse=0.40, He=0.70, h_aod=0.80
        # γ_TB = (0.8×24 + 0.7×18) / 1.5 = 21.2
        r = check_alicc(0.40, q_uckse=600.0)
        expected = (0.8 * 24.0 + 0.7 * 18.0) / (0.8 + 0.7)
        assert r["gamma_fill_TB"] == pytest.approx(expected, abs=1e-3)
