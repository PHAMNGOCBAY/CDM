import sqlite3
import os
import chromadb
from chromadb.utils import embedding_functions

def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'TTHC.sqlite')
    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    
    if not os.path.exists(db_path):
        print(f"Lỗi: Không tìm thấy cơ sở dữ liệu SQLite tại {db_path}")
        return

    print("Kết nối tới SQLite...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        l.id as layer_id, 
        b.id as borehole_id, 
        b.name as borehole_name, 
        l.symbol, 
        l.description, 
        l.depth_top_m, 
        l.depth_bot_m, 
        l.thickness_m
    FROM layers l 
    JOIN boreholes b ON l.borehole_id = b.id
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Lỗi truy vấn: {e}")
        return
        
    print(f"Tìm thấy {len(rows)} lớp đất. Đang khởi tạo ChromaDB...")
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=chroma_path)
    
    # We will use the default embedding function provided by ChromaDB 
    # (all-MiniLM-L6-v2) for simplicity, which will be auto-downloaded if not present.
    # Note: For better Vietnamese support in production, a multilingual model 
    # like 'paraphrase-multilingual-MiniLM-L12-v2' is recommended.
    
    collection_name = "geology_layers"
    # Create or get collection
    try:
        collection = client.get_or_create_collection(name=collection_name)
    except Exception as e:
        print(f"Lỗi tạo collection: {e}")
        return

    documents = []
    metadatas = []
    ids = []
    
    for row in rows:
        layer_id, borehole_id, borehole_name, symbol, description, depth_top_m, depth_bot_m, thickness_m = row
        
        # Fallbacks for NULL values
        symbol = symbol or ""
        description = description or ""
        depth_top_m = depth_top_m if depth_top_m is not None else 0.0
        depth_bot_m = depth_bot_m if depth_bot_m is not None else 0.0
        thickness_m = thickness_m if thickness_m is not None else 0.0
        
        doc_text = (
            f"Hố khoan {borehole_name}, Lớp {symbol}: {description}. "
            f"Độ sâu từ {depth_top_m:.2f}m đến {depth_bot_m:.2f}m (dày {thickness_m:.2f}m)."
        )
        
        doc_id = f"bh_{borehole_id}_layer_{layer_id}"
        
        documents.append(doc_text)
        ids.append(doc_id)
        metadatas.append({
            "borehole_id": borehole_id,
            "layer_id": layer_id,
            "borehole_name": borehole_name,
            "symbol": symbol,
            "depth_top_m": depth_top_m,
            "depth_bot_m": depth_bot_m,
            "thickness_m": thickness_m
        })
    
    if len(documents) > 0:
        print(f"Đang thêm {len(documents)} documents vào ChromaDB (Quá trình này có thể mất chút thời gian để tải model embedding lần đầu)...")
        # Add in batches if necessary, but for typical borehole data sizes (< 10000) a single add is fine.
        # Max batch size for Chroma is typically 5461, so we should batch just in case.
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
        print("Đã thêm dữ liệu thành công!")
    else:
        print("Không có dữ liệu để thêm.")
        
    conn.close()

    # --- Test Query ---
    print("\n--- Thực hiện test truy vấn (Semantic Search) ---")
    test_query = "lớp bùn sét hoặc sét pha màu xám đen"
    print(f"Truy vấn: '{test_query}'")
    
    results = collection.query(
        query_texts=[test_query],
        n_results=3
    )
    
    if results and results['documents']:
        for i, (doc, meta, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
            print(f"\nKết quả {i+1} (Distance: {dist:.4f}):")
            print(f"  Document: {doc}")
            print(f"  Metadata: {meta}")

if __name__ == "__main__":
    main()
