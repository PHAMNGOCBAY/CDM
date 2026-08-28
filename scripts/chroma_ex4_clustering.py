import os
import sys
import io
import chromadb
from sklearn.cluster import KMeans
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=========================================")
    print("VÍ DỤ 4: PHÂN VÙNG ĐỊA CHẤT BẰNG CLUSTERING")
    print("=========================================")
    
    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name="geology_layers")
    
    print("Đang tải toàn bộ dữ liệu vector từ ChromaDB...")
    # Lấy toàn bộ dữ liệu bao gồm cả embeddings
    results = collection.get(include=['embeddings', 'documents', 'metadatas'])
    
    embeddings = results['embeddings']
    documents = results['documents']
    metadatas = results['metadatas']
    
    if embeddings is None or len(embeddings) == 0:
        print("Không có dữ liệu.")
        return
        
    num_clusters = min(4, len(embeddings))
    print(f"Đã tải {len(embeddings)} vector. Bắt đầu phân cụm (K-Means) thành {num_clusters} nhóm...")
    
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings)
    
    print("\n--- KẾT QUẢ PHÂN CỤM (ZONING) ---")
    
    # Tổ chức kết quả theo từng cụm
    clusters = defaultdict(list)
    for i, label in enumerate(cluster_labels):
        clusters[label].append({
            'doc': documents[i],
            'meta': metadatas[i]
        })
        
    for label in range(num_clusters):
        items = clusters[label]
        print(f"\n>> CỤM {label + 1} (Có {len(items)} lớp đất):")
        
        # In ra 3 lớp đại diện cho cụm này
        sample_size = min(3, len(items))
        for i in range(sample_size):
            item = items[i]
            print(f"  - {item['meta'].get('borehole_name')}, Lớp {item['meta'].get('symbol')}: {item['doc'][:100]}...")

if __name__ == "__main__":
    main()
