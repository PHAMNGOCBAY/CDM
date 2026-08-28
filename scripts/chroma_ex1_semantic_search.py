import os
import sys
import io
import chromadb

# Ensure proper utf-8 encoding for Windows terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=========================================")
    print("VÍ DỤ 1: SEMANTIC SEARCH BẰNG CHROMADB")
    print("=========================================")
    
    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    if not os.path.exists(chroma_path):
        print(f"Lỗi: Không tìm thấy ChromaDB tại {chroma_path}. Vui lòng chạy sqlite_to_chroma.py trước.")
        return

    print("Đang tải ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)
    
    try:
        collection = client.get_collection(name="geology_layers")
    except Exception as e:
        print(f"Lỗi: Không tìm thấy collection 'geology_layers'. {e}")
        return

    print(f"Đã kết nối thành công. Collection hiện có {collection.count()} lớp đất.")
    print("-" * 40)
    
    while True:
        query = input("\nNhập truy vấn địa chất (hoặc gõ 'exit' để thoát): ")
        if query.strip().lower() in ['exit', 'quit']:
            break
            
        if not query.strip():
            continue
            
        print(f"\nĐang tìm kiếm cho: '{query}'...")
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if not results or not results['documents']:
            print("Không tìm thấy kết quả phù hợp.")
            continue
            
        print("\nKết quả tìm kiếm hàng đầu:")
        for i, (doc, meta, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
            print(f"\n[{i+1}] Distance: {dist:.4f}")
            print(f"    Text: {doc}")
            print(f"    Borehole: {meta.get('borehole_name')}, Lớp: {meta.get('symbol')}, Sâu: {meta.get('depth_bot_m')}m")

if __name__ == "__main__":
    main()
