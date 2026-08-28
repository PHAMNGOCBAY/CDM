"""cdm3d.types — Dataclass tham so mo hinh 3D CDM-dat nen.

Don vi: m, kPa (kN/m^2), kN/m^3. Cao do z: duong huong LEN (dung quy uoc dia ky thuat,
z=0 la mat dat tu nhien, z am la duoi mat dat).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SoilLayer:
    """Mot lop dat trong khoi nen (theo chieu sau)."""

    name: str
    z_top: float  # cao do dinh lop (m)
    z_bot: float  # cao do day lop (m), z_bot < z_top
    gamma_kNm3: float  # dung trong TU NHIEN/BAO HOA (gamma_sat) — dung cho *DENSITY
    E_kPa: float
    nu: float
    source: str = "assumed"  # 'lab_tests' | 'VST' | 'tvtk_cdm_json' | 'assumed'


@dataclass
class ColumnGroup:
    """Nhom tru CDM bo tri luoi vuong n_x x n_y."""

    D_m: float
    spacing_m: float
    n_x: int
    n_y: int
    z_top: float  # cao do dau tru (thuong = dinh lop dap)
    z_bot: float  # cao do mui tru (am hon z_top)
    Ec_kPa: float
    nu_c: float = 0.25
    gamma_kNm3: float = 18.0
    source: str = "assumed"


@dataclass
class LoadStage:
    """Mot giai doan dap tai (GD2..GDN) — dung cho chuoi *STEP tuan tu trong
    ccx_input.write_ccx_inp(). Tai lech tam theo cong thuc ung suat day mong lech
    tam (sigma = N/A + M*x/I, M=P*e, I=L*B^3/12):
    q(x) = q_avg_kPa * (1 + 12*e*(x-x_center)/B^2), B = domain theo truc ecc_axis.
    He so 12 (KHONG phai 6 — 6 chi dung khi danh gia TAI MEP x=B/2) — da kiem
    chung bang tich phan so, xem ccx_input._eccentric_pressure() va
    76-cdm3d-fem-gmsh-calculix.md muc 8d.
    """

    name: str
    q_avg_kPa: float
    eccentricity_m: float = 0.0  # + lech ve phia +truc, - lech ve phia -truc
    ecc_axis: str = "x"  # "x" hoac "y"
    load_footprint: str = "full"
    """'full' (mac dinh): tai phu toan bo domain, dung cong thuc lech tam o tren.
    'half_pos'/'half_neg': tai UNIFORM = q_avg_kPa CHI tren nua domain theo
    ecc_axis (pos>=0 / pos<=0 tinh tu tam), nua con lai = 0 (bac thang, khong
    phai gradient tuyen tinh) — dung khi tai thiet ke chi dap 1 vung gioi han
    (vd nua mien phia +X), KHONG dap ra het vung dem tinh toan (domain_buffer_m).
    Khi != 'full', eccentricity_m bi BO QUA (khong dung cong thuc trapezoidal)."""


@dataclass
class ModelParams:
    """Toan bo tham so mot kich ban mo hinh 3D."""

    zone_code: str
    soil_layers: list[SoilLayer]
    column: ColumnGroup
    q_surcharge_kPa: float = 0.0
    stages: list[LoadStage] = field(default_factory=list)
    domain_buffer_m: float = 3.6  # bien tu mep nhom tru ra bien mo hinh (truc X —
                                   # truc CO tai lech tam/half-footprint, xem LoadStage)
    domain_buffer_y_m: float | None = None  # None = dung domain_buffer_m (doi xung
                                             # nhu cu). Dat rieng de mo rong CHI truc Y
                                             # (truc KHONG co bien thien tai — ecc_axis
                                             # luon la "x") — vd kiem tra do nhay bien Y
                                             # ma khong lam thay doi truc X dang xet tai.
    domain_buffer_x_neg_m: float | None = None  # None = dung domain_buffer_m (doi
                                             # xung nhu cu). Dat rieng de mo rong CHI
                                             # phia -X (phia KHONG co tai khi
                                             # load_footprint="half_pos", vd GD5) —
                                             # KHONG anh huong phia +X (co tai).
    mesh_size_far_m: float = 2.0
    mesh_size_near_column_m: float = 0.3
    column_box_field_margin_m: float = 0.5
    water_table_elev: float | None = None  # cao do MNN (m) — None = khong xet (dung gamma_sat het)
    warnings: list[str] = field(default_factory=list)

    _GAMMA_W = 9.81  # kN/m3

    def effective_gamma_at(self, z: float) -> float:
        """Dung trong HIEU DUNG (gamma') tai cao do z — dung cho tinh sigma'v.
        gamma' = gamma_sat - gamma_w (Archimedes) khi z <= water_table_elev (duoi
        MNN); nguoc lai (tren MNN, hoac water_table_elev=None) tra ve gamma_kNm3
        (dung trong tu nhien/bao hoa cua lop, khong tru nuoc)."""
        layer = next((l for l in self.soil_layers if l.z_bot <= z <= l.z_top), None)
        if layer is None:
            raise ValueError(f"z={z} khong nam trong lop dat nao cua ModelParams")
        if self.water_table_elev is not None and z <= self.water_table_elev:
            return layer.gamma_kNm3 - self._GAMMA_W
        return layer.gamma_kNm3

    def sigma_v_eff_kPa(self, z: float) -> float:
        """Tich phan gamma hieu dung tu z_domain_top() xuong den z — ung suat
        thang dung HIEU DUNG sigma'v(z) (kPa), co xet muc nuoc ngam tung doan."""
        z_top = self.z_domain_top()
        if z >= z_top:
            return 0.0
        # tich phan tung doan theo ranh gioi lop VA water_table_elev (neu nam
        # giua khoang [z, z_top]) de gamma hieu dung dung tai moi doan nho
        breakpoints = sorted({z_top, z, *(l.z_top for l in self.soil_layers),
                               *(l.z_bot for l in self.soil_layers),
                               *([self.water_table_elev] if self.water_table_elev is not None else [])},
                              reverse=True)
        breakpoints = [b for b in breakpoints if z <= b <= z_top]
        sigma = 0.0
        for z_hi, z_lo in zip(breakpoints, breakpoints[1:]):
            z_mid = (z_hi + z_lo) / 2.0
            gamma = self.effective_gamma_at(z_mid)
            sigma += gamma * (z_hi - z_lo)
        return sigma

    def footprint_x_m(self) -> float:
        return (self.column.n_x - 1) * self.column.spacing_m + self.column.D_m

    def footprint_y_m(self) -> float:
        return (self.column.n_y - 1) * self.column.spacing_m + self.column.D_m

    def domain_x_m(self) -> float:
        return self.footprint_x_m() + 2 * self.domain_buffer_m

    def domain_y_m(self) -> float:
        buf_y = self.domain_buffer_y_m if self.domain_buffer_y_m is not None else self.domain_buffer_m
        return self.footprint_y_m() + 2 * buf_y

    def z_domain_top(self) -> float:
        return max(layer.z_top for layer in self.soil_layers)

    def z_domain_bot(self) -> float:
        """soil_layers PHAI da xep chong lien tuc (khong ho), lop cuoi cung
        (lop cung) PHAI da bao gom du sau qua mui tru — xem params_io.build_default_params()."""
        return min(layer.z_bot for layer in self.soil_layers)
