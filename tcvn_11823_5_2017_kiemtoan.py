import math

class TCVN_11823_5_2017:
    """
    THIẾT KẾ CẦU ĐƯỜNG BỘ - PHẦN 5: KẾT CẤU BÊ TÔNG (TCVN 11823-5:2017)
    Kiểm toán kết cấu chịu uốn và cắt
    """
    def __init__(self, fc_prime, fy, b, h, c, phi_assumed, Mu, Qu):
        """
        Khởi tạo thông số đầu vào
        :param fc_prime: Cường độ bê tông (MPa)
        :param fy: Cường độ thép (MPa)
        :param b: Bề rộng tính toán (mm)
        :param h: Chiều dày bản (mm)
        :param c: Lớp bảo vệ bê tông (mm)
        :param phi_assumed: Đường kính thép giả thiết (mm)
        :param Mu: Mô men tính toán (kN.m)
        :param Qu: Lực cắt tính toán (kN)
        """
        self.fc_prime = fc_prime
        self.fy = fy
        self.b = b
        self.h = h
        self.c = c
        self.phi_assumed = phi_assumed
        self.Mu = Mu
        self.Qu = Qu
        
        # Chiều cao có ích d
        self.d = self.h - self.c - self.phi_assumed / 2.0
        
        # Hệ số sức kháng
        self.phi_f = 0.90 # uốn
        self.phi_v = 0.90 # cắt
        
        # Hệ số quy đổi khối ứng suất
        if self.fc_prime <= 28:
            self.beta_1 = 0.85
        else:
            self.beta_1 = max(0.65, 0.85 - 0.05 * (self.fc_prime - 28) / 7)
            
    def calculate_bending_reinforcement(self):
        """
        Tính diện tích cốt thép yêu cầu chịu uốn
        """
        # Hệ số sức kháng mô men danh định Rn (MPa)
        Rn = (self.Mu * 10**6) / (self.phi_f * self.b * self.d**2)
        
        # Hàm lượng cốt thép
        rho = (0.85 * self.fc_prime / self.fy) * (1 - math.sqrt(1 - 2 * Rn / (0.85 * self.fc_prime)))
        
        # Diện tích cốt thép yêu cầu (mm2)
        Ast_req = rho * self.b * self.d
        
        return {
            'Rn': Rn,
            'rho': rho,
            'Ast_req': Ast_req
        }
        
    def check_min_reinforcement(self):
        """
        Kiểm tra cốt thép tối thiểu
        """
        # Cường độ kéo khi uốn của bê tông fr (MPa)
        fr = 0.63 * math.sqrt(self.fc_prime)
        
        # Mô men nứt Mcr (kN.m)
        Mcr = fr * (self.b * self.h**2 / 6) / 10**6
        
        # Mô men tối thiểu để tính cốt thép (kiểm soát)
        M_min = min(1.2 * Mcr, 1.33 * self.Mu)
        
        # Tính lại Ast_min dựa trên M_min
        Rn_min = (M_min * 10**6) / (self.phi_f * self.b * self.d**2)
        rho_min = (0.85 * self.fc_prime / self.fy) * (1 - math.sqrt(1 - 2 * Rn_min / (0.85 * self.fc_prime)))
        Ast_min = rho_min * self.b * self.d
        
        return {
            'fr': fr,
            'Mcr': Mcr,
            '1.2_Mcr': 1.2 * Mcr,
            '1.33_Mu': 1.33 * self.Mu,
            'M_min_control': M_min,
            'Ast_min': Ast_min
        }
        
    def check_shear(self):
        """
        Kiểm toán khả năng chịu cắt
        """
        # Chiều cao chịu cắt có hiệu dv (mm)
        dv = max(0.9 * self.d, 0.72 * self.h)
        
        # Sức kháng cắt của bê tông - phương pháp đơn giản hóa
        beta_shear = 2.0
        lambda_shear = 1.0
        
        Vc = 0.083 * beta_shear * lambda_shear * math.sqrt(self.fc_prime) * self.b * dv / 1000 # kN
        phi_Vc = self.phi_v * Vc
        
        check_shear_ok = self.Qu < phi_Vc
        need_shear_reinforcement = self.Qu > 0.5 * phi_Vc
        
        return {
            'dv': dv,
            'Vc': Vc,
            'phi_Vc': phi_Vc,
            'check_shear_ok': check_shear_ok,
            'need_shear_reinforcement': need_shear_reinforcement
        }
        
    def design_summary(self):
        """
        Tổng hợp kết quả thiết kế
        """
        bending = self.calculate_bending_reinforcement()
        min_reinf = self.check_min_reinforcement()
        shear = self.check_shear()
        
        Ast_design = max(bending['Ast_req'], min_reinf['Ast_min'])
        
        return {
            'Ast_design': Ast_design,
            'bending': bending,
            'min_reinf': min_reinf,
            'shear': shear
        }

if __name__ == "__main__":
    # Chạy thử với dữ liệu từ bài toán mẫu
    calc = TCVN_11823_5_2017(
        fc_prime=30, fy=300, b=1000, h=200, c=40, phi_assumed=14, 
        Mu=9.15, Qu=15.80
    )
    summary = calc.design_summary()
    
    print("=== KẾT QUẢ KIỂM TOÁN TCVN 11823-5:2017 ===")
    print(f"Diện tích cốt thép tính toán: {summary['bending']['Ast_req']:.1f} mm2/m")
    print(f"Diện tích cốt thép tối thiểu: {summary['min_reinf']['Ast_min']:.1f} mm2/m")
    print(f"-> Diện tích cốt thép thiết kế: {summary['Ast_design']:.1f} mm2/m\n")
    
    print(f"Sức kháng cắt của bê tông (phi*Vc): {summary['shear']['phi_Vc']:.1f} kN")
    print(f"Lực cắt tính toán (Qu): {calc.Qu:.2f} kN")
    print(f"Bê tông đủ khả năng chịu cắt: {'Có' if summary['shear']['check_shear_ok'] else 'Không'}")
    print(f"Cần bố trí cốt đai: {'Có' if summary['shear']['need_shear_reinforcement'] else 'Không'}")
