import pdfplumber
import re
import sqlite3
import sys

# Windows console encoding fix
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r'G:\My Drive\202605-TRUNG TAM HCM\CDM\TTHC\Qu. E50-Công viên hồ Trung Tâm. 2026(R28-1).pdf'
db_path = 'data/TTHC.sqlite'

def parse_pdf():
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            
            bh_match = re.search(r'Hố khoan:\s*(\w+)', text)
            dosage_match = re.search(r'Hàm lượng xi măng\s*\(kg/m3\):\s*(\d+)', text)
            sample_match = re.search(r'Số hiệu thí nghiệm:\s*([\w\-]+)', text)
            age_match = re.search(r'Tuổi mẫu\s*\(ngày\):\s*(\d+)', text)
            
            qu_matches = re.findall(r'=\s*([\d\.]+)\s*kPa', text)
            e50_matches = re.findall(r'=\s*([\d\.]+)\s*MPa', text)
            
            if bh_match and sample_match and len(qu_matches) == 3 and len(e50_matches) == 3:
                qu_vals = [float(x) for x in qu_matches]
                e50_vals = [float(x) for x in e50_matches]
                
                avg_qu = sum(qu_vals) / len(qu_vals)
                avg_e50 = sum(e50_vals) / len(e50_vals)
                
                res = {
                    'page': i + 1,
                    'borehole': bh_match.group(1),
                    'sample_id': sample_match.group(1),
                    'dosage': float(dosage_match.group(1)) if dosage_match else None,
                    'age': int(age_match.group(1)) if age_match else None,
                    'qu_avg': avg_qu,
                    'e50_avg': avg_e50,
                    'qu_vals': qu_vals,
                    'e50_vals': e50_vals
                }
                results.append(res)
            else:
                print(f'Failed to parse complete data on page {i+1}')
    return results

def update_db(data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name FROM boreholes')
    bh_map = {name: id for id, name in cursor.fetchall()}
    
    inserted_count = 0
    
    # Clear old data if re-running
    cursor.execute('DELETE FROM cdm_specimens')
    
    for row in data:
        bh_id = bh_map.get(row['borehole'])
        if not bh_id:
            cursor.execute('SELECT id FROM boreholes WHERE name = ? COLLATE NOCASE', (row['borehole'],))
            res = cursor.fetchone()
            if res:
                bh_id = res[0]
            else:
                cursor.execute('SELECT id FROM boreholes WHERE name = ? COLLATE NOCASE', ('BXN-CV-' + row['borehole'],))
                res = cursor.fetchone()
                if res:
                    bh_id = res[0]
                else:
                    print(f"Warning: Borehole {row['borehole']} not found in DB.")
                    continue
                
        # Insert 3 individual specimens
        for specimen_idx in range(3):
            cursor.execute('''
                INSERT INTO cdm_specimens (borehole_id, sample_id, dosage_kgm3, age_days, specimen_no, qu_kPa, e50_MPa)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (bh_id, row['sample_id'], row['dosage'], row['age'], specimen_idx + 1, row['qu_vals'][specimen_idx], row['e50_vals'][specimen_idx]))
            inserted_count += 1
            
    conn.commit()
    conn.close()
    print(f"Database updated: {inserted_count} individual specimens inserted into cdm_specimens.")

if __name__ == '__main__':
    data = parse_pdf()
    print(f'Successfully parsed {len(data)} records from PDF.')
    for d in data[:3]:
        print(f"Page {d['page']}: BH={d['borehole']}, Sample={d['sample_id']}, Dosage={d['dosage']}, Age={d['age']}, qu_avg={d['qu_avg']:.1f}, E50_avg={d['e50_avg']:.1f}")
    
    update_db(data)
