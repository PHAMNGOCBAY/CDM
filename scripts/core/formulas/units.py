"""Symbols SymPy dùng chung — đặt MỘT LẦN để tránh tạo Symbol mới cùng tên ở nhiều file."""
import sympy as sp

# Tải trọng và hình học
q = sp.Symbol("q", positive=True)
H = sp.Symbol("H", positive=True)
H_i = sp.Symbol("H_i", positive=True)
L = sp.Symbol("L", positive=True)
P = sp.Symbol("P", positive=True)

# CDM
a = sp.Symbol("a", positive=True)
k = sp.Symbol("k", positive=True)
C_c_col = sp.Symbol("C_{c.col}", positive=True)
qu = sp.Symbol("q_u", positive=True)
D = sp.Symbol("D", positive=True)
s = sp.Symbol("s", positive=True)

# Mô đun
E_c = sp.Symbol("E_c", positive=True)
E_s = sp.Symbol("E_s", positive=True)
E_oed = sp.Symbol("E_{oed}", positive=True)

# Đất
S_u = sp.Symbol("S_u", positive=True)
c_u = sp.Symbol("c_u", positive=True)
mu = sp.Symbol("mu", positive=True)
I_p = sp.Symbol("I_p", positive=True)
e_0 = sp.Symbol("e_0", positive=True)
C_c = sp.Symbol("C_c", positive=True)
C_s = sp.Symbol("C_s", positive=True)
sigma_v0 = sp.Symbol(r"\sigma'_{v0}", positive=True)
sigma_vf = sp.Symbol(r"\sigma'_{vf}", positive=True)
P_C = sp.Symbol("P_C", positive=True)
a_12 = sp.Symbol("a_{1-2}", positive=True)

# Cọc
alpha = sp.Symbol("alpha", positive=True)
A_p = sp.Symbol("A_p", positive=True)

# Hệ số
KPA_PER_KGF_CM2 = sp.Float("98.0665")  # chuyển đổi kgf/cm² → kPa
