import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import sqlite3
import os
import re

file_path = r'G:\My Drive\202605-TRUNG TAM HCM\CDM\TTHC\Qu. E50-Công viên hồ Trung Tâm. 2026(R28-1).xlsx'
db_path = r'G:\My Drive\AI-SUC TAI COC THEO DAT NEN\data\cdm_new.sqlite'

# Remove old db if exists to avoid appending duplicates
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS cdm_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_name TEXT,
    loai_xi_mang TEXT,
    ho_khoan TEXT,
    ham_luong TEXT,
    do_sau TEXT,
    tuoi_mau TEXT,
    thoi_so TEXT,
    qu_kPa REAL,
    e50_MPa REAL
)
""")

xls = pd.ExcelFile(file_path)

def extract_value(df, keyword, max_rows=15):
    keyword = keyword.lower()
    for r in range(min(max_rows, len(df))):
        for c in range(len(df.columns)):
            val = str(df.iloc[r, c]).lower()
            if keyword in val:
                for next_c in range(c+1, len(df.columns)):
                    next_val = df.iloc[r, next_c]
                    if pd.notna(next_val) and str(next_val).strip() != '':
                        return str(next_val).strip()
    return None

def extract_results(df):
    results = {}
    qu_row_idx = -1
    e50_row_idx = -1
    
    # Search from bottom up
    for r in range(len(df)-1, max(0, len(df)-20), -1):
        for c in range(len(df.columns)):
            val = str(df.iloc[r, c]).lower()
            if 'qu =' in val or 'qu=' in val:
                qu_row_idx = r
            if 'e50 =' in val or 'e50=' in val:
                e50_row_idx = r
                
    if qu_row_idx != -1 and e50_row_idx != -1:
        # Columns for Thỏi 1, Thỏi 2, Thỏi 3 are roughly at 0, 8, 15
        for thoi, col_idx in [('Thỏi số 1', 0), ('Thỏi số 2', 8), ('Thỏi số 3', 15)]:
            if col_idx < len(df.columns):
                # Try to find qu value
                qu_val_str = str(df.iloc[qu_row_idx, col_idx])
                if pd.isna(df.iloc[qu_row_idx, col_idx]) or str(df.iloc[qu_row_idx, col_idx]).strip() == '':
                    qu_val_str = str(df.iloc[qu_row_idx, col_idx+1]) if col_idx+1 < len(df.columns) else ""
                
                # Try to find e50 value
                e50_val_str = str(df.iloc[e50_row_idx, col_idx])
                if pd.isna(df.iloc[e50_row_idx, col_idx]) or str(df.iloc[e50_row_idx, col_idx]).strip() == '':
                    e50_val_str = str(df.iloc[e50_row_idx, col_idx+1]) if col_idx+1 < len(df.columns) else ""
                
                # Parse numeric
                qu_match = re.search(r'=\s*([\d.]+)', qu_val_str) or re.search(r'([\d.]+)', qu_val_str.replace('qu', '').replace('QU', ''))
                e50_match = re.search(r'=\s*([\d.]+)', e50_val_str) or re.search(r'([\d.]+)', e50_val_str.replace('E50', '').replace('e50', ''))
                
                if qu_match and e50_match:
                    results[thoi] = {
                        'qu': float(qu_match.group(1)),
                        'e50': float(e50_match.group(1))
                    }
    return results

total_inserted = 0

for sheet in xls.sheet_names:
    df = pd.read_excel(file_path, sheet_name=sheet, header=None)
    
    loai_xi_mang = extract_value(df, 'loại xi măng')
    ho_khoan = extract_value(df, 'hố khoan')
    ham_luong = extract_value(df, 'hàm lượng xi măng')
    do_sau = extract_value(df, 'độ sâu')
    tuoi_mau = extract_value(df, 'tuổi mẫu')
    
    results = extract_results(df)
    
    for thoi, vals in results.items():
        cursor.execute('''
            INSERT INTO cdm_tests (sheet_name, loai_xi_mang, ho_khoan, ham_luong, do_sau, tuoi_mau, thoi_so, qu_kPa, e50_MPa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sheet, loai_xi_mang, ho_khoan, ham_luong, do_sau, tuoi_mau, thoi, vals['qu'], vals['e50']))
        total_inserted += 1

conn.commit()
conn.close()

print(f"Đã trích xuất và lưu {total_inserted} bản ghi vào data/cdm_new.sqlite")
