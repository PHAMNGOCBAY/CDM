"""cdm3d.run_ccx — Goi solver CalculiX (ccx.exe) qua subprocess.

CalculiX LA BINARY BIEN DICH SAN — khong cai duoc qua pip/conda tren Windows.
Tai thu cong ban Windows precompiled (vd tu trang chinh thuc calculix.de, hoac
build tu github.com/calculix/CalculiX) roi tro CDM3D_CCX_EXE toi file ccx*.exe.
Xem huong dan chi tiet trong 76-cdm3d-fem-gmsh-calculix.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class CcxNotFoundError(RuntimeError):
    pass


_KNOWN_INSTALL_PATHS = [
    # ccx_static.exe: khong phu thuoc DLL ngoai (spooles+pastix static-link) —
    # uu tien hon ccx_dynamic.exe (can mkl_rt.2.dll khong di kem ban cai)
    r"C:\CalculiX\calculix_2.23_4win\ccx_static.exe",
]


def find_ccx_exe() -> str | None:
    env_path = os.environ.get("CDM3D_CCX_EXE")
    if env_path and Path(env_path).exists():
        return env_path
    for name in ("ccx", "ccx.exe", "ccx_2.22.exe", "ccx_2.21.exe", "ccx_static.exe"):
        found = shutil.which(name)
        if found:
            return found
    for path in _KNOWN_INSTALL_PATHS:
        if Path(path).exists():
            return path
    return None


def solve(inp_path: Path, ccx_exe: str | None = None, timeout_s: int = 3600) -> Path:
    """Chay `ccx <jobname>` (khong co duoi .inp) trong thu muc chua file .inp.
    Tra ve duong dan file .frd ket qua (cung ten voi .inp). Nem CcxNotFoundError
    ro rang neu khong tim thay binary — KHONG lang le bo qua."""
    inp_path = Path(inp_path)
    exe = ccx_exe or find_ccx_exe()
    if exe is None:
        raise CcxNotFoundError(
            "Khong tim thay ccx.exe (solver CalculiX). Dat bien moi truong "
            "CDM3D_CCX_EXE tro toi file thuc thi, hoac them vao PATH he thong. "
            "Xem huong dan tai ve trong 76-cdm3d-fem-gmsh-calculix.md."
        )
    job_name = inp_path.stem
    log_path = inp_path.with_suffix(".ccx_log.txt")
    try:
        result = subprocess.run(
            [exe, job_name], cwd=str(inp_path.parent),
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        log_path.write_text((e.stdout or "") + "\n" + (e.stderr or ""), encoding="utf-8", errors="replace")
        raise RuntimeError(f"CalculiX vuot qua timeout {timeout_s}s. Xem log: {log_path}") from e
    log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8", errors="replace")
    frd_path = inp_path.with_suffix(".frd")
    if result.returncode != 0 or not frd_path.exists():
        raise RuntimeError(
            f"CalculiX ket thuc voi loi (return code {result.returncode}). "
            f"Xem log: {log_path}"
        )
    return frd_path
