# -*- coding: utf-8 -*-
"""Golden tests — engine cdm_lk2_calc khớp 100% bản tính Excel 'TINH MONG TRU CDM - LK2.xlsx'.

Giá trị vàng (golden) lấy trực tiếp từ ô đã tính của Excel, lưu trong
data/lk2_cdm_settlement.json. Engine phải tái tạo sai số < 1e-6 (settlement/bearing)
và < 1e-3 (lún theo thời gian, do làm tròn ROUND 4 chữ số trong Excel).
"""
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from cdm_lk2_calc import (  # noqa: E402
    compute_concrete_check, compute_lk2, compute_sct, compute_time_history,
    load_lk2_dataset,
)

_JSON = _ROOT / "data" / "lk2_cdm_settlement.json"


@pytest.fixture(scope="module")
def data():
    inp, geo = load_lk2_dataset()
    full = json.loads(_JSON.read_text(encoding="utf-8"))
    res = compute_lk2(inp, geo)
    sct = compute_sct(inp, geo, res.Ecol, res.a_ratio)
    cvt, tvu, gt = full["cv_table"], full["tvu_table"], full["golden_time"]
    th = compute_time_history(res, cvt["pressure_kPa"], cvt["Cv"], tvu["Tv"], tvu["U_pct"],
                              gt["years"], allowable_cm=gt["allowable_cm"], design_time_idx=1)
    cc = compute_concrete_check(inp.D_m, inp.S_m, inp.q_total,
                                full["scalars"].get("dv_concrete_m", 0.0))
    return inp, full, res, sct, th, cc


# ── Sheet (1): lún khối móng ─────────────────────────────────────────────
def test_area_ratio(data):
    _, full, res, *_ = data
    assert res.a_ratio == pytest.approx(full["golden"]["ap"], abs=1e-9)


def test_eeq(data):
    _, full, res, *_ = data
    assert res.Eeq == pytest.approx(full["golden"]["Eeq"], abs=1e-6)


def test_sblock(data):
    _, full, res, *_ = data
    assert res.Sblock_m == pytest.approx(full["golden"]["Sblock_m"], abs=1e-9)


def test_sc_consolidation(data):
    _, full, res, *_ = data
    assert res.Sc_m == pytest.approx(full["golden"]["Sc_m"], abs=1e-6)


def test_s_total(data):
    _, full, res, *_ = data
    assert res.S_total_m == pytest.approx(full["golden"]["S_total_m"], abs=1e-6)


# ── Sheet SCT: sức chịu tải ──────────────────────────────────────────────
@pytest.mark.parametrize("attr,key", [
    ("Etd", "Etd"), ("Cu_soil", "Cu_soil"), ("N_load", "N_load"), ("Nvl", "Nvl"),
    ("Ndn", "Ndn"), ("Nc", "Nc"), ("qp", "qp"), ("ratio_Nc_N", "ratio_Nc_N"),
    ("sigma_col", "sigma_col"), ("Pcol", "Pcol"),
    ("Qult_col_AIT", "Qult_col"), ("Qult_soil_AIT", "Qult_soil"), ("Qa_soil", "Qa_soil"),
])
def test_sct(data, attr, key):
    _, full, _, sct, *_ = data
    assert getattr(sct, attr) == pytest.approx(full["golden_sct"][key], abs=1e-6)


# ── Sheet (2): lún theo thời gian ────────────────────────────────────────
def test_time_ctbv(data):
    _, full, *_rest = data
    th = _rest[2]
    assert th.Ctbv_cm2s == pytest.approx(full["golden_time"]["Ctbv_cm2s"], abs=1e-9)


def test_time_history_St(data):
    _, full, _, _, th, _ = data
    for i, st_gold in enumerate(full["golden_time"]["St_cm"]):
        assert th.St_cm[i] == pytest.approx(st_gold, abs=1e-3)


def test_time_residual_check(data):
    _, full, _, _, th, _ = data
    assert th.residual_check_cm == pytest.approx(full["golden_time"]["residual_check_cm"], abs=1e-3)


# ── Sheet kiểm toán bê tông ──────────────────────────────────────────────
def test_concrete_demand(data):
    *_, cc = data
    gc = data[1]["golden_check"]
    assert cc.Mtt == pytest.approx(gc["Mtt"], abs=1e-6)
    assert cc.Vtt == pytest.approx(gc["Vtt"], abs=1e-6)
    assert cc.sigma_flex_MPa == pytest.approx(gc["sigma_flex_MPa"], abs=1e-6)


# ── Engine sống: đổi input -> kết quả đổi đúng hướng ─────────────────────
def test_live_quck_increases_reduces_settlement():
    inp, geo = load_lk2_dataset()
    base = compute_lk2(inp, geo).Sblock_m
    inp.quck = 1600.0   # tăng cường độ trụ -> Ecol tăng -> Sblock giảm
    hi = compute_lk2(inp, geo).Sblock_m
    assert hi < base
