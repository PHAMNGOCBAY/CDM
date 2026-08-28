import math
from dataclasses import dataclass

@dataclass
class WallGeometry:
    h_stem: float
    b_top: float
    b_bot: float
    h_slab: float
    b_toe: float
    b_heel: float

    @property
    def total_height(self) -> float:
        return self.h_stem + self.h_slab

    @property
    def total_width(self) -> float:
        return self.b_toe + self.b_bot + self.b_heel

@dataclass
class MaterialProps:
    gamma_c: float = 24.0
    f_c: float = 25.0

@dataclass
class SoilProps:
    gamma: float
    phi: float
    c: float = 0.0
    bearing_cap: float = 250.0
    friction_factor: float = 0.5

class LWallCalculator:
    def __init__(self, geom: WallGeometry, mat: MaterialProps, soil_ret: SoilProps, soil_base: SoilProps, surcharge: float):
        self.geom = geom
        self.mat = mat
        self.soil_ret = soil_ret
        self.soil_base = soil_base
        self.q = surcharge

    def calc_earth_pressure(self):
        phi_rad = math.radians(self.soil_ret.phi)
        ka = math.tan(math.radians(45) - phi_rad / 2) ** 2
        H = self.geom.total_height
        
        pa_soil = ka * self.soil_ret.gamma * H
        pa_surcharge = ka * self.q
        
        force_soil = 0.5 * pa_soil * H
        force_surcharge = pa_surcharge * H
        
        moment_soil = force_soil * (H / 3)
        moment_surcharge = force_surcharge * (H / 2)
        
        return {
            "ka": ka,
            "force_soil": force_soil,
            "force_surcharge": force_surcharge,
            "total_active_force": force_soil + force_surcharge,
            "overturning_moment": moment_soil + moment_surcharge
        }

    def calc_weights_and_resisting_moment(self):
        # 1. Stem (thân tường)
        stem_rect_area = self.geom.b_top * self.geom.h_stem
        stem_tri_area = 0.5 * (self.geom.b_bot - self.geom.b_top) * self.geom.h_stem
        
        w_stem_rect = stem_rect_area * self.mat.gamma_c
        x_stem_rect = self.geom.b_toe + (self.geom.b_bot - self.geom.b_top) + self.geom.b_top / 2
        
        w_stem_tri = stem_tri_area * self.mat.gamma_c
        x_stem_tri = self.geom.b_toe + 2/3 * (self.geom.b_bot - self.geom.b_top)

        # 2. Base slab (bản móng)
        w_slab = self.geom.total_width * self.geom.h_slab * self.mat.gamma_c
        x_slab = self.geom.total_width / 2
        
        # 3. Soil over heel (đất đè gót)
        w_soil_heel = self.geom.b_heel * self.geom.h_stem * self.soil_ret.gamma
        x_soil_heel = self.geom.b_toe + self.geom.b_bot + self.geom.b_heel / 2
        
        # 4. Surcharge over heel
        w_surcharge = self.q * self.geom.b_heel
        x_surcharge = x_soil_heel

        total_weight = w_stem_rect + w_stem_tri + w_slab + w_soil_heel + w_surcharge
        resisting_moment = (
            w_stem_rect * x_stem_rect +
            w_stem_tri * x_stem_tri +
            w_slab * x_slab +
            w_soil_heel * x_soil_heel +
            w_surcharge * x_surcharge
        )
        
        return {
            "total_weight": total_weight,
            "resisting_moment": resisting_moment,
            "components": {
                "stem_rect": (w_stem_rect, x_stem_rect),
                "stem_tri": (w_stem_tri, x_stem_tri),
                "slab": (w_slab, x_slab),
                "soil_heel": (w_soil_heel, x_soil_heel),
                "surcharge": (w_surcharge, x_surcharge)
            }
        }

    def check_stability(self):
        ep = self.calc_earth_pressure()
        wm = self.calc_weights_and_resisting_moment()
        
        # Overturning
        fs_overturning = wm["resisting_moment"] / ep["overturning_moment"] if ep["overturning_moment"] > 0 else float('inf')
        
        # Sliding
        resisting_force = wm["total_weight"] * self.soil_base.friction_factor + self.soil_base.c * self.geom.total_width
        fs_sliding = resisting_force / ep["total_active_force"] if ep["total_active_force"] > 0 else float('inf')
        
        # Bearing Capacity
        net_moment = wm["resisting_moment"] - ep["overturning_moment"]
        eccentricity = self.geom.total_width / 2 - (net_moment / wm["total_weight"])
        
        B = self.geom.total_width
        if eccentricity <= B / 6:
            p_max = (wm["total_weight"] / B) * (1 + 6 * eccentricity / B)
            p_min = (wm["total_weight"] / B) * (1 - 6 * eccentricity / B)
        else:
            # Not fully supported
            L_eff = 3 * (B / 2 - eccentricity)
            p_max = (2 * wm["total_weight"]) / L_eff
            p_min = 0.0
            
        fs_bearing = self.soil_base.bearing_cap / p_max if p_max > 0 else float('inf')
        
        return {
            "fs_overturning": fs_overturning,
            "fs_sliding": fs_sliding,
            "eccentricity": eccentricity,
            "p_max": p_max,
            "p_min": p_min,
            "fs_bearing": fs_bearing
        }

if __name__ == "__main__":
    geom = WallGeometry(4.0, 0.4, 0.6, 0.6, 0.8, 1.6)
    mat = MaterialProps()
    soil_ret = SoilProps(gamma=18.0, phi=30.0)
    soil_base = SoilProps(gamma=19.0, phi=32.0, c=10.0, bearing_cap=250.0, friction_factor=0.5)
    
    calc = LWallCalculator(geom, mat, soil_ret, soil_base, surcharge=10.0)
    res = calc.check_stability()
    print("Stability Results:")
    for k, v in res.items():
        print(f"{k}: {v:.3f}")
