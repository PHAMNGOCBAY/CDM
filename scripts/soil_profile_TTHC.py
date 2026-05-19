"""Tra cứu địa tầng hố khoan — Dự án 202605-TTHC (Trung tâm Hành chính TP.HCM).

Nguồn dữ liệu: data/soil_profile_202605_TTHC.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent / "data" / "soil_profile_202605_TTHC.json"


@dataclass
class SoilLayer:
    symbol: str
    description: str
    thickness_m: float


@dataclass
class Borehole:
    name: str
    elevation_m: float
    depth_m: float
    date: str
    layers: list[SoilLayer]

    def summary(self) -> None:
        print(f"\n{'='*60}")
        print(f"{self.name}  |  Z = {self.elevation_m:+.3f} m  |  Sâu {self.depth_m} m  |  {self.date}")
        print(f"{'='*60}")
        print(f"  {'Lớp':<6}  {'Dày (m)':>8}  Mô tả")
        print(f"  {'-'*6}  {'-'*8}  {'-'*42}")
        for lyr in self.layers:
            print(f"  {lyr.symbol:<6}  {lyr.thickness_m:>8.2f}  {lyr.description}")
        print(f"  {'Tổng':<6}  {sum(l.thickness_m for l in self.layers):>8.2f}")

    def layer(self, symbol: str) -> SoilLayer | None:
        for lyr in self.layers:
            if lyr.symbol == symbol:
                return lyr
        return None

    def depth_to_layer(self, symbol: str) -> float | None:
        """Trả về chiều sâu đến đỉnh lớp (m từ mặt đất)."""
        depth = 0.0
        for lyr in self.layers:
            if lyr.symbol == symbol:
                return depth
            depth += lyr.thickness_m
        return None


def _load() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _parse(data: dict) -> list[Borehole]:
    boreholes = []
    for bh in data["boreholes"]:
        layers = [SoilLayer(**lyr) for lyr in bh["layers"]]
        boreholes.append(Borehole(
            name=bh["name"],
            elevation_m=bh["elevation_m"],
            depth_m=bh["depth_m"],
            date=bh["date"],
            layers=layers,
        ))
    return boreholes


def list_all() -> list[Borehole]:
    """Trả về danh sách tất cả hố khoan."""
    return _parse(_load())


def get(name: str) -> Borehole:
    """Tra cứu hố khoan theo tên (ví dụ: 'HK1')."""
    for bh in list_all():
        if bh.name.upper() == name.upper():
            return bh
    raise KeyError(f"Không tìm thấy hố khoan: {name}")


def layer_thickness_table(symbol: str) -> None:
    """In bảng chiều dày một lớp đất theo tất cả hố khoan."""
    print(f"\nLớp {symbol!r} — chiều dày theo hố khoan:")
    print(f"  {'HK':<6}  {'Dày (m)':>8}  {'Đỉnh lớp (m)':>14}")
    print(f"  {'-'*6}  {'-'*8}  {'-'*14}")
    for bh in list_all():
        lyr = bh.layer(symbol)
        if lyr:
            top = bh.depth_to_layer(symbol)
            print(f"  {bh.name:<6}  {lyr.thickness_m:>8.2f}  {top:>14.2f}")
        else:
            print(f"  {bh.name:<6}  {'—':>8}")


if __name__ == "__main__":
    # Demo: in tóm tắt HK1 và bảng chiều dày lớp 1
    hk1 = get("HK1")
    hk1.summary()

    layer_thickness_table("1")
    layer_thickness_table("4")
