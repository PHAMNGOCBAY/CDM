import os
import streamlit as st
import chromadb
import requests
import json

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Geology AI Assistant",
    page_icon="🌍",
    layout="wide"
)

# --- KHỞI TẠO CHROMADB ---
@st.cache_resource
def get_chroma_collection():
    try:
        # Đường dẫn tuyệt đối đến thư mục chứa db
        current_dir = os.path.dirname(os.path.abspath(__file__))
        chroma_path = os.path.join(current_dir, '..', 'data', 'chroma_db')
        
        client = chromadb.PersistentClient(path=chroma_path)
        return client.get_collection(name="geology_layers")
    except Exception as e:
        st.error(f"Lỗi khởi tạo ChromaDB: {e}")
        return None

collection = get_chroma_collection()

# --- GIAO DIỆN CHÍNH ---
st.title("🤖 Trợ lý Kỹ sư Địa chất (RAG)")
st.markdown("Bạn có thể đặt câu hỏi về điều kiện địa chất, tính chất các lớp đất, hoặc thông tin các hố khoan tại khu vực công trình.")

# Khởi tạo trạng thái lịch sử chat
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Thêm câu chào mừng
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Xin chào! Mình là trợ lý AI. Mình đã được nạp dữ liệu về 383 lớp đất từ dự án. Bạn cần hỏi gì nào?"
    })

# Khôi phục lịch sử chat trên màn hình
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- XỬ LÝ KHUNG NHẬP CHAT ---
if prompt := st.chat_input("VD: Ở đây có lớp đất yếu nào dày trên 20m không?"):
    
    # 1. Hiển thị câu hỏi của user
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Xử lý câu trả lời của AI
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        if collection is None:
            full_response = "Lỗi: Không thể kết nối đến cơ sở dữ liệu Vector (ChromaDB). Vui lòng kiểm tra lại đường dẫn."
            message_placeholder.markdown(full_response)
        else:
            with st.spinner("Đang tra cứu dữ liệu địa chất..."):
                # --- BƯỚC 2.1: Truy vấn ChromaDB (Retrieval) ---
                results = collection.query(
                    query_texts=[prompt],
                    n_results=4
                )
                
                context_docs = results['documents'][0] if results and results['documents'] else []
                context_text = "\n".join([f"- {doc}" for doc in context_docs])
                
            with st.spinner("Đang tổng hợp câu trả lời..."):
                # --- BƯỚC 2.2: Gọi LLM (Generation) ---
                llm_prompt = f"""Bạn là một kỹ sư địa kỹ thuật tư vấn cho người dùng. Hãy trả lời câu hỏi dựa trên DỮ LIỆU ĐỊA CHẤT sau. Nếu dữ liệu không đủ, hãy nói bạn không biết.

DỮ LIỆU ĐỊA CHẤT:
{context_text}

CÂU HỎI:
{prompt}
"""
                try:
                    # Gửi tới Local Ollama
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "gemma",
                            "prompt": llm_prompt,
                            "stream": False
                        },
                        timeout=12
                    )
                    
                    if response.status_code == 200:
                        full_response = response.json().get("response", "Lỗi: Model trả về rỗng.")
                    else:
                        raise Exception(f"HTTP {response.status_code}")
                
                except requests.exceptions.RequestException as e:
                    # FALLBACK: Nếu Ollama tắt/lỗi, trả về kết quả thô từ ChromaDB
                    full_response = (
                        "⚠️ **Lỗi kết nối AI (Ollama Server đang tắt hoặc bị timeout).**\n\n"
                        "Tuy nhiên, hệ thống đã tra cứu thành công các dữ liệu liên quan nhất dành cho bạn:\n\n"
                        + context_text + "\n\n"
                        "*(Vui lòng khởi động lại Ollama hoặc liên hệ quản trị hệ thống để tích hợp Gemini API để được trả lời tự nhiên hơn).* \n"
                    )

            # Hiển thị kết quả ra màn hình
            message_placeholder.markdown(full_response)
        
        # Lưu vào lịch sử
        st.session_state.messages.append({"role": "assistant", "content": full_response})
