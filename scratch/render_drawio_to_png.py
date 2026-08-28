"""Render cdm3d_workflow.drawio -> PNG bang matplotlib (khong co draw.io desktop
app / drawio CLI cai san tren may de export truc tiep). Doc chinh xac toa do/mau/
text tu file .drawio (mxGraph XML) de dam bao PNG khop voi file goc, KHONG hardcode
lai layout mot lan nua (tranh sai lech/typo giua 2 ban).
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.path import Path as MplPath

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
DRAWIO_PATH = ROOT / "cdm3d_workflow.drawio"
OUT_PNG = ROOT / "cdm3d_workflow.png"

tree = ET.parse(DRAWIO_PATH)
root = tree.getroot()


def parse_style(style: str) -> dict:
    d = {}
    for part in style.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k] = v
        elif part:
            d[part] = "1"
    return d


def clean_text(value: str) -> str:
    value = value.replace("&lt;br&gt;", "\n").replace("<br>", "\n")
    value = value.replace("&#8594;", "\u2192").replace("&#8226;", "\u2022")
    value = value.replace("&#947;", "\u03b3").replace("&#945;", "\u03b1")
    value = value.replace("&#956;", "\u03bc").replace("&#10;", "\n")
    value = value.replace("&amp;", "&").replace("&#8217;", "'")
    return value


vertices = {}
edges = []
for cell in root.iter("mxCell"):
    cid = cell.get("id")
    value = cell.get("value") or ""
    style = parse_style(cell.get("style") or "")
    if cell.get("vertex") == "1":
        geom = cell.find("mxGeometry")
        x, y = float(geom.get("x")), float(geom.get("y"))
        w, h = float(geom.get("width")), float(geom.get("height"))
        vertices[cid] = {"x": x, "y": y, "w": w, "h": h, "text": clean_text(value), "style": style}
    elif cell.get("edge") == "1":
        edges.append((cell.get("source"), cell.get("target")))

max_y = max(v["y"] + v["h"] for v in vertices.values())
max_x = max(v["x"] + v["w"] for v in vertices.values())

fig, ax = plt.subplots(figsize=(max_x / 80, max_y / 80), dpi=150)

for cid, v in vertices.items():
    st = v["style"]
    is_text_only = st.get("text") == "1"
    x, y, w, h = v["x"], v["y"], v["w"], v["h"]
    y_mpl = max_y - y - h  # flip truc Y (drawio: Y tang xuong; matplotlib: Y tang len)

    if not is_text_only:
        fill = st.get("fillColor", "#ffffff")
        stroke = st.get("strokeColor", "#000000")
        rect = Rectangle((x, y_mpl), w, h, facecolor=fill, edgecolor=stroke,
                          linewidth=1.4, joinstyle="round",
                          zorder=2, capstyle="round")
        ax.add_patch(rect)

    font_color = st.get("fontColor", "#000000")
    font_size = float(st.get("fontSize", 12)) * 0.72
    weight = "bold" if st.get("fontStyle") == "1" else "normal"
    ha = {"left": "left", "center": "center", "right": "right"}.get(st.get("align", "center"), "center")
    tx = x + 6 if ha == "left" else x + w / 2
    ax.text(tx, y_mpl + h / 2, v["text"], ha=ha, va="center", fontsize=font_size,
            color=font_color, weight=weight, wrap=True, zorder=3,
            linespacing=1.35)

id_to_center_edge = {}
for cid, v in vertices.items():
    x, y, w, h = v["x"], v["y"], v["w"], v["h"]
    y_mpl = max_y - y - h
    id_to_center_edge[cid] = (x, y_mpl, w, h)

for src, tgt in edges:
    if src not in id_to_center_edge or tgt not in id_to_center_edge:
        continue
    sx, sy, sw, sh = id_to_center_edge[src]
    tx, ty, tw, th = id_to_center_edge[tgt]
    p0 = (sx + sw, sy + sh / 2) if (sx + sw) <= tx else (sx + sw / 2, sy)
    p1 = (tx, ty + th / 2) if tx >= (sx + sw) else (tx + tw / 2, ty + th)
    arrow = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12,
                             color="#555555", linewidth=1.1, zorder=1,
                             connectionstyle="arc3,rad=0.0", shrinkA=2, shrinkB=2)
    ax.add_patch(arrow)

ax.set_xlim(0, max_x)
ax.set_ylim(0, max_y)
ax.axis("off")
plt.tight_layout(pad=0.5)
fig.savefig(OUT_PNG, facecolor="white")
print("wrote:", OUT_PNG)
