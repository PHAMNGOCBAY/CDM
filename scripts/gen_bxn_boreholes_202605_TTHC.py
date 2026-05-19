"""gen_bxn_boreholes_202605_TTHC.py — Tạo data/bxn_boreholes_202605_TTHC.json.

Nguồn: BXN-2. TRỤ_BXN-TTHC. Tru DC.pdf (Google Drive ID: 1c_RO3JKtaLKNYE0C_xSTOZ1hMYaifi7L)
Địa tầng và tọa độ trích thủ công từ trụ địa chất.
SPT tự động parse từ nội dung PDF đã đọc qua Google Drive MCP.

Usage:
    python scripts/gen_bxn_boreholes_202605_TTHC.py [pdf_text_file]
    # pdf_text_file: đường dẫn file JSON chứa fileContent từ MCP read_file_content
    # Nếu không truyền, script chỉ tạo JSON từ dữ liệu hardcode (không cần PDF)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT     = Path(__file__).parent.parent
OUT_PATH = ROOT / "data" / "bxn_boreholes_202605_TTHC.json"

# ── Địa tầng (trích từ trụ ĐC BXN-2.pdf) ────────────────────────────────────
# Mỗi tuple: (symbol, mô tả tiếng Việt có dấu, depth_top_m, depth_bot_m)

LAYERS: dict[int, list[tuple[str, str, float, float]]] = {
    1: [
        ("1",  "Đất san lấp",                                                           0.0,  2.7),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.7, 20.3),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        20.3, 25.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              25.0, 39.5),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              39.5, 43.0),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng, trạng thái nửa cứng",            43.0, 51.0),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng, trạng thái nửa cứng",            51.0, 60.3),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               60.3, 70.0),
    ],
    2: [
        ("1",  "Đất san lấp",                                                           0.0,  2.5),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.5, 19.5),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        19.5, 27.5),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              27.5, 35.5),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              35.5, 43.0),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 43.0, 55.0),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 55.0, 59.0),
        ("7",  "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                             59.0, 67.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               67.0, 70.0),
    ],
    3: [
        ("1",  "Đất san lấp",                                                           0.0,  2.0),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.0, 21.0),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        21.0, 27.2),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            27.2, 31.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              31.0, 42.5),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 42.5, 47.0),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a)",                            46.5, 48.9),
        ("7",  "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                             48.9, 59.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               59.0, 70.0),
    ],
    4: [
        ("1",  "Đất san lấp",                                                           0.0,  1.1),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       1.1, 21.0),
        ("3a", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp",                          21.0, 23.9),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        23.9, 27.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              27.0, 35.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              35.0, 43.0),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 43.0, 47.0),
        ("TK6a","Cát vừa lẫn bụi, màu xám nâu (thấu kính 6a)",                        47.22,51.0),
        ("7",  "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                             51.0, 59.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               59.0, 70.0),
    ],
    5: [
        ("1",  "Đất san lấp",                                                           0.0,  1.1),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       1.1, 20.8),
        ("3a", "Cát lẫn sét, bụi màu xám xanh",                                       20.8, 22.0),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        22.0, 29.0),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            29.0, 37.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              37.0, 42.6),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 42.6, 51.1),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 51.1, 60.9),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               60.9, 70.0),
    ],
    6: [
        ("1",  "Đất san lấp",                                                           0.0,  2.4),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.4, 21.7),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        21.7, 31.0),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            31.0, 37.2),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              37.2, 43.6),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 43.6, 63.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               63.0, 70.0),
    ],
    7: [
        ("1",  "Đất san lấp",                                                           0.0,  2.2),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.2, 22.1),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        22.1, 31.0),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            31.0, 32.2),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              32.2, 41.3),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 41.3, 51.3),
        ("7",  "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                             51.3, 59.5),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               59.5, 70.0),
    ],
    8: [
        ("1",   "Đất san lấp",                                                          0.0,  3.0),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      3.0, 22.7),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       22.7, 27.0),
        ("3c",  "Cát lẫn sét bụi màu xám xanh (lớp 3c)",                              27.0, 31.0),
        ("4",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",           31.0, 34.7),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             34.7, 41.7),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                41.7, 46.5),
        ("TK6a","Sét cứng ít – thấu kính 6a",                                          46.5, 49.0),
        ("TK6b","Cát lẫn sét, màu nâu vàng – thấu kính 6b",                           49.0, 51.5),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                51.5, 56.6),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              56.6, 70.0),
    ],
    9: [
        ("1",  "Đất san lấp",                                                           0.0,  3.0),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       3.0, 22.6),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        22.6, 29.0),
        ("3c", "Cát lẫn sét bụi màu xám xanh (lớp 3c)",                               29.0, 31.2),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            31.2, 35.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              35.0, 38.8),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 38.8, 61.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               61.0, 70.0),
    ],
    10: [
        ("1",   "Đất san lấp",                                                          0.0,  3.1),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      3.1, 23.9),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       23.9, 35.0),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             35.0, 42.4),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                42.4, 49.5),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a)",                            49.5, 50.8),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                50.8, 56.1),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a) – lần 2",                   53.03,59.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                59.0, 63.2),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              63.2, 70.0),
    ],
    11: [
        ("1",  "Đất san lấp",                                                           0.0,  3.3),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       3.3, 20.2),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        20.2, 29.0),
        ("3c", "Cát lẫn sét bụi màu xám xanh (lớp 3c)",                               29.0, 35.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              35.0, 37.5),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 37.5, 65.0),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               65.0, 70.0),
    ],
    12: [
        ("1",   "Đất san lấp",                                                          0.0,  2.3),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      2.3, 22.0),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       22.0, 32.0),
        ("4",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",           32.0, 36.0),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             36.0, 42.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                42.0, 50.2),
        ("TK6b","Cát lẫn sét, màu nâu vàng (thấu kính 6b)",                           50.2, 54.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                54.0, 58.0),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              58.0, 70.0),
    ],
    13: [
        ("1",  "Đất san lấp",                                                           0.0,  2.6),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       2.6, 21.5),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        21.5, 27.0),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              27.0, 40.9),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 40.9, 57.4),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               57.4, 70.0),
    ],
    14: [
        ("1",  "Đất san lấp",                                                           0.0,  1.3),
        ("2",  "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                       1.3, 21.4),
        ("3b", "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",        21.4, 30.7),
        ("4",  "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",            30.7, 33.2),
        ("5",  "Cát chặt lẫn vừa sét bụi, màu xám xanh",                              33.2, 44.9),
        ("6",  "Sét cứng ít – dẻo cứng màu nâu vàng",                                 44.9, 59.4),
        ("8",  "Cát lẫn bụi màu xám nâu, kết cấu chặt",                               59.4, 70.0),
    ],
    15: [
        ("1",   "Đất san lấp",                                                          0.0,  1.0),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      1.0, 21.5),
        ("3a",  "Cát lẫn sét, bụi màu xám xanh",                                      21.5, 25.0),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       25.0, 28.6),
        ("4",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm – dẻo cứng",           28.6, 35.0),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             35.0, 42.1),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                42.1, 47.5),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a)",                            45.19,49.0),
        ("TK6b","Cát lẫn sét, màu nâu vàng (thấu kính 6b)",                           46.69,51.2),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                51.2, 57.5),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              57.5, 70.0),
    ],
    16: [
        ("1",   "Đất san lấp",                                                          0.0,  2.5),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      2.5, 22.5),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       22.5, 33.0),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             33.0, 43.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                43.0, 51.0),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a)",                            48.36,55.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                55.0, 59.0),
        ("7",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                            59.0, 63.2),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              63.2, 70.0),
    ],
    17: [
        ("1",   "Đất san lấp",                                                          0.0,  1.0),
        ("2",   "Sét chảy rất dẻo màu xám xanh, trạng thái chảy",                      1.0, 19.0),
        ("3b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",       19.0, 27.0),
        ("5",   "Cát chặt lẫn vừa sét bụi, màu xám xanh",                             27.0, 38.8),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                38.8, 47.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                47.0, 55.0),
        ("TK6a","Cát lẫn bụi, màu xám nâu (thấu kính 6a)",                            54.89,57.0),
        ("6",   "Sét cứng ít – dẻo cứng màu nâu vàng",                                57.0, 63.0),
        ("8",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                              63.0, 70.0),
    ],
}

# ── Tọa độ và cao độ (VN2000, nguồn: BXN-2.pdf) ────────────────────────────
HK_META: dict[int, dict] = {
    1:  {"x": 1191602.053, "y": 606114.279, "z": 2.899, "depth": 70.0},
    2:  {"x": 1191585.870, "y": 606077.724, "z": 2.551, "depth": 70.0},
    3:  {"x": 1191569.698, "y": 606041.174, "z": 2.398, "depth": 70.0},
    4:  {"x": 1191553.467, "y": 606004.580, "z": 2.282, "depth": 70.0},
    5:  {"x": 1191537.283, "y": 605968.022, "z": 2.193, "depth": 70.0},
    6:  {"x": 1191573.853, "y": 605951.807, "z": 2.183, "depth": 70.0},
    7:  {"x": 1191590.044, "y": 605988.342, "z": 2.243, "depth": 70.0},
    8:  {"x": 1191606.260, "y": 606024.982, "z": 2.258, "depth": 70.0},
    9:  {"x": 1191622.441, "y": 606061.542, "z": 3.058, "depth": 70.0},
    10: {"x": 1191638.680, "y": 606098.186, "z": 3.070, "depth": 70.0},  # X: OCR 119163.868 → 1191638.680
    11: {"x": 1191678.381, "y": 606089.422, "z": 2.983, "depth": 70.0},
    12: {"x": 1191662.015, "y": 606052.169, "z": 2.708, "depth": 70.0},
    13: {"x": 1191645.843, "y": 606015.603, "z": 2.268, "depth": 70.0},
    14: {"x": 1191629.624, "y": 605979.066, "z": 2.185, "depth": 70.0},
    15: {"x": 1191683.770, "y": 606002.554, "z": 2.311, "depth": 70.0},
    16: {"x": 1191770.009, "y": 606039.124, "z": 2.642, "depth": 70.0},
    17: {"x": 1191633.615, "y": 605966.866, "z": 2.112, "depth": 70.0},
}


def _parse_spt_from_text(text: str) -> dict[int, list[dict]]:
    """Parse SPT từ nội dung PDF text, trả về dict keyed by HK number."""
    boreholes_starts: dict[int, int] = {}
    for m in re.finditer(r"CV-HK(\d+)", text):
        num = int(m.group(1))
        if num not in boreholes_starts:
            boreholes_starts[num] = m.start()
    sorted_keys = sorted(boreholes_starts.keys())
    ends: dict[int, int] = {}
    for i, k in enumerate(sorted_keys):
        ends[k] = boreholes_starts[sorted_keys[i + 1]] if i < len(sorted_keys) - 1 else len(text)

    result: dict[int, list[dict]] = {}
    for hk in range(1, 18):
        if hk not in boreholes_starts:
            result[hk] = []
            continue
        s = boreholes_starts[hk] - 800
        section = text[max(0, s): ends[hk]]
        rows: list[dict] = []
        seen: set[float] = set()
        for m in re.finditer(
            r"(?:D\d+\s+|U\d+\s+)?(\d+\.\d{2}) (\d+\.\d{2}) (\d+) (\d+) (\d+) (\d+)", section
        ):
            depth = float(m.group(1))
            n1, n2, n3, n = int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
            if 1.0 <= depth <= 71.0 and abs(n - (n2 + n3)) <= 2 and depth not in seen:
                seen.add(depth)
                rows.append({"depth_m": depth, "N1": n1, "N2": n2, "N3": n3, "N": n})
        rows.sort(key=lambda x: x["depth_m"])
        result[hk] = rows
    return result


def build(spt_map: dict[int, list[dict]] | None = None) -> dict:
    boreholes = []
    for hk in range(1, 18):
        meta = HK_META[hk]
        layers = [
            {"symbol": sym, "description": desc, "depth_top_m": top, "depth_bot_m": bot}
            for sym, desc, top, bot in LAYERS[hk]
        ]
        spt = spt_map[hk] if spt_map else []
        boreholes.append({
            "name":       f"BXN-CV-HK{hk}",
            "name_raw":   f"CV-HK{hk}",
            "elevation_m": meta["z"],
            "depth_m":     meta["depth"],
            "date":        None,
            "x_coord_m":   meta["x"],
            "y_coord_m":   meta["y"],
            "layers":      layers,
            "spt":         spt,
        })
    return {
        "_meta": {
            "project":         "Trung tâm Hành chính TP.HCM",
            "zone":            "BXN",
            "source":          "BXN-2. TRỤ_BXN-TTHC. Tru DC.pdf",
            "source_drive_id": "1c_RO3JKtaLKNYE0C_xSTOZ1hMYaifi7L",
            "updated":         "2026-05-18",
            "boreholes":       17,
            "notes": (
                "14 HK có KQTN (HK1-8,11,13-17); HK9,HK10,HK12 chỉ có trụ ĐC + SPT. "
                "Tọa độ VN2000 đầy đủ cho tất cả 17 HK. "
                "HK10 tọa độ X điều chỉnh từ OCR artifact 119163.868 → 1191638.680."
            ),
        },
        "boreholes": boreholes,
    }


if __name__ == "__main__":
    spt_map = None
    if len(sys.argv) > 1:
        pdf_json_path = sys.argv[1]
        with open(pdf_json_path, encoding="utf-8") as f:
            raw = json.load(f)
        text = raw["fileContent"]
        spt_map = _parse_spt_from_text(text)
        print(f"SPT parsed from PDF text: {sum(len(v) for v in spt_map.values())} điểm")
    else:
        print("Không có file PDF text — chỉ tạo địa tầng hardcode, không có SPT.")

    data = build(spt_map)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Written: {OUT_PATH}")
    for bh in data["boreholes"]:
        print(f"  {bh['name']}: {len(bh['layers'])} layers, {len(bh['spt'])} SPT")
