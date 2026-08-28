import os
import sys
import io
import chromadb

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=========================================")
    print("VÍ DỤ 3: TÌM KIẾM TƯƠNG ĐỒNG (SIMILARITY SEARCH)")
    print("=========================================")
    
    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name="geology_layers")
    
    # Lấy 1 document ngẫu nhiên làm gốc (ví dụ: Lớp đầu tiên của hố khoan đầu tiên)
    # Ta dùng query '.peek(1)' để lấy 1 item bất kỳ
    peek_res = collection.peek(1)
    if not peek_res['ids']:
        print("Không có dữ liệu trong ChromaDB.")
        return
        
    source_id = peek_res['ids'][0]
    source_doc = peek_res['documents'][0]
    source_meta = peek_res['metadatas'][0]
    
    print(f"\n[LỚP ĐẤT GỐC] ID: {source_id}")
    print(f"Mô tả: {source_doc}")
    
    print("\nĐang tìm kiếm các lớp đất có đặc tính tương đồng nhất ở các hố khoan khác...")
    
    results = collection.query(
        query_texts=[source_doc],
        n_results=6  # Lấy 6 kết quả, vì kết quả đầu tiên thường chính là lớp gốc
    )
    
    print("\n--- KẾT QUẢ TƯƠNG ĐỒNG ---")
    for i, (doc, meta, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
        if meta.get('borehole_id') == source_meta.get('borehole_id'):
            continue # Bỏ qua các lớp cùng hố khoan với lớp gốc
            
        print(f"\n[Độ lệch: {dist:.4f}] Hố khoan: {meta.get('borehole_name')}, Lớp: {meta.get('symbol')}")
        print(f"    Text: {doc}")

if __name__ == "__main__":
    main()
