import os
import sys
import io
import sqlite3
import chromadb
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_borehole_elevations(db_path):
    """Lấy danh sách hố khoan và cao độ từ SQLite"""
    conn = sqlite3.connect(db_path)
    # Lấy 10 hố khoan đầu tiên để làm ví dụ
    query = "SELECT name, elevation_m FROM boreholes WHERE elevation_m IS NOT NULL LIMIT 10"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def main():
    print("==========================================================")
    print("VÍ DỤ 5: HYBRID RAG - DỰ BÁO ĐỘ LÚN KẾT HỢP TOÁN HỌC & AI")
    print("==========================================================")
    
    base_dir = os.path.dirname(__file__)
    sqlite_path = os.path.join(base_dir, '..', 'data', 'TTHC.sqlite')
    chroma_path = os.path.join(base_dir, '..', 'data', 'chroma_db')
    
    print("[1] Đang lấy dữ liệu Cao độ hố khoan từ SQLite...")
    df_bh = get_borehole_elevations(sqlite_path)
    
    print("[2] Đang kết nối ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name="geology_layers")
    
    DESIGN_ELEVATION = 2.70 # m
    print(f"\n=> YÊU CẦU: Tính lún với Cao độ thiết kế = +{DESIGN_ELEVATION}m\n")
    
    results_list = []
    
    for index, row in df_bh.iterrows():
        bh_name = row['name']
        elevation = row['elevation_m']
        
        # Tính chiều cao đắp
        h_fill = DESIGN_ELEVATION - elevation
        if h_fill <= 0:
            h_fill = 0
            
        # Tìm các lớp đất yếu (bùn sét) của hố khoan này qua ChromaDB
        # Sử dụng ngữ nghĩa "đất yếu, bùn sét, trạng thái chảy"
        search_query = "bùn sét, đất yếu, sét pha chảy, lún nhiều"
        
        try:
            chroma_res = collection.query(
                query_texts=[search_query],
                where={"borehole_name": bh_name},
                n_results=3
            )
        except Exception:
            continue
            
        soft_soil_thickness = 0.0
        soft_layers_desc = []
        
        if chroma_res and chroma_res['documents'] and len(chroma_res['documents'][0]) > 0:
            docs = chroma_res['documents'][0]
            metas = chroma_res['metadatas'][0]
            distances = chroma_res['distances'][0]
            
            for doc, meta, dist in zip(docs, metas, distances):
                # Chỉ lấy các lớp có distance < 1.0 (nghĩa là thực sự giống ngữ nghĩa 'đất yếu')
                if dist < 1.0:
                    thickness = float(meta.get('thickness_m', 0))
                    soft_soil_thickness += thickness
                    soft_layers_desc.append(f"Lớp {meta.get('symbol')} ({thickness}m)")
                    
        # Công thức dự báo lún KINH NGHIỆM sơ bộ (chỉ mang tính ví dụ RAG):
        # S = 0.1 * H_soft * (H_fill / 2.0)
        # Nghĩa là: nếu đắp 2m thì độ lún bằng 10% bề dày đất yếu.
        if h_fill > 0 and soft_soil_thickness > 0:
            settlement_m = 0.1 * soft_soil_thickness * (h_fill / 2.0)
            settlement_cm = settlement_m * 100
        else:
            settlement_cm = 0.0
            
        results_list.append({
            "Hố khoan": bh_name,
            "Cao độ (m)": round(elevation, 2),
            "Đất đắp (m)": round(h_fill, 2),
            "Đất yếu (m)": round(soft_soil_thickness, 2),
            "Độ lún (cm)": round(settlement_cm, 1),
            "Ghi chú (từ Chroma)": ", ".join(soft_layers_desc) if soft_layers_desc else "Không có đất yếu"
        })

    # In bảng kết quả
    print("-" * 90)
    print(f"{'HỐ KHOAN':<15} | {'CAO ĐỘ':<8} | {'ĐẤT ĐẮP':<8} | {'ĐẤT YẾU':<8} | {'ĐỘ LÚN':<8} | {'CHI TIẾT LỚP YẾU (CHROMA)'}")
    print("-" * 90)
    for r in results_list:
        print(f"{r['Hố khoan']:<15} | {r['Cao độ (m)']:<8} | {r['Đất đắp (m)']:<8} | {r['Đất yếu (m)']:<8} | {r['Độ lún (cm)']:<8} | {r['Ghi chú (từ Chroma)']}")
    print("-" * 90)
    
    print("\n[3] TẠO PROMPT TỰ ĐỘNG CHO AI TRỢ LÝ TƯ VẤN:")
    sample_result = results_list[0]
    prompt = f"""Dưới đây là số liệu tính toán độ lún tự động:
- Hố khoan: {sample_result['Hố khoan']}
- Chiều cao đắp: {sample_result['Đất đắp (m)']} mét
- Tổng bề dày đất yếu phát hiện qua ChromaDB: {sample_result['Đất yếu (m)']} mét ({sample_result['Ghi chú (từ Chroma)']}).
- Độ lún dự báo: {sample_result['Độ lún (cm)']} cm.

Vui lòng viết 1 đoạn nhận xét rủi ro lún cho hố khoan này và đề xuất sơ bộ biện pháp xử lý (nếu lún > 30cm thì đề xuất cọc xi măng đất)."""
    
    print(f"\n{prompt}\n")
    print("=> AI (Gemini/Ollama) sẽ đọc đoạn Prompt này và sinh ra một báo cáo phân tích rất chuyên nghiệp mà không bị sai số toán học!")

if __name__ == "__main__":
    main()
