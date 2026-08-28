import os
import sys
import chromadb
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import numpy as np

def main():
    print("=========================================")
    print("XUẤT BIỂU ĐỒ PHÂN CỤM ĐỊA CHẤT (CLUSTERING)")
    print("=========================================")
    
    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name="geology_layers")
    
    print("Đang tải dữ liệu vector từ ChromaDB...")
    results = collection.get(include=['embeddings', 'metadatas'])
    
    embeddings = results['embeddings']
    metadatas = results['metadatas']
    
    if embeddings is None or len(embeddings) == 0:
        print("Lỗi: Không có dữ liệu embedding.")
        return
        
    embeddings_array = np.array(embeddings)
    num_clusters = min(4, len(embeddings))
    
    print(f"Bắt đầu phân cụm K-Means thành {num_clusters} nhóm...")
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings_array)
    
    print("Đang giảm chiều dữ liệu (PCA/t-SNE) xuống 2D để vẽ biểu đồ...")
    # Sử dụng t-SNE để hiển thị phân cụm tốt hơn
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    coords_2d = tsne.fit_transform(embeddings_array)
    
    # Chuẩn bị vẽ biểu đồ
    plt.figure(figsize=(12, 8))
    
    # Định nghĩa màu và nhãn cho các cụm
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    cluster_names = [
        "Cụm 1 (Sét cứng / Đất san lấp)",
        "Cụm 2 (Bùn sét chảy)",
        "Cụm 3 (Cát lẫn sét xốp/chặt)",
        "Cụm 4 (Sét rất dẻo/chảy)"
    ]
    
    for i in range(num_clusters):
        idx = cluster_labels == i
        plt.scatter(
            coords_2d[idx, 0], 
            coords_2d[idx, 1], 
            c=colors[i], 
            label=cluster_names[i] if i < len(cluster_names) else f"Cụm {i+1}",
            alpha=0.7,
            s=50,
            edgecolors='w',
            linewidths=0.5
        )
    
    plt.title('Bản đồ Phân cụm Địa chất Dựa trên Ý nghĩa Ngữ nghĩa (ChromaDB + t-SNE)', fontsize=14, pad=20)
    plt.xlabel('Thành phần t-SNE 1', fontsize=12)
    plt.ylabel('Thành phần t-SNE 2', fontsize=12)
    plt.legend(title="Các phân vùng địa chất", fontsize=10, title_fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.3)
    
    # Thêm background color nhẹ để trông đẹp hơn
    plt.gca().set_facecolor('#f8f9fa')
    
    # Tạo thư mục images nếu chưa có
    images_dir = os.path.join(os.path.dirname(__file__), '..', 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    out_file = os.path.join(images_dir, 'chroma_clustering_result.png')
    
    print(f"Đang lưu biểu đồ chất lượng cao (300 DPI) ra file: {out_file}...")
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Hoàn tất! Đã xuất ảnh biểu đồ.")

if __name__ == "__main__":
    main()
