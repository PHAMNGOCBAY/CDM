import os
import sys
import io
import datetime
import chromadb
import requests
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLLAMA_MODEL = "gemma4:26b"  # Đúng tên model đã pull trong Ollama (trước đây ghi "gemma" -> không tồn tại, luôn lỗi)
OLLAMA_TIMEOUT_S = 180  # Model 26B cục bộ có thể mất vài chục giây tới vài phút, 10s cũ luôn timeout sớm

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'rag_qa')


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """Bọc dòng theo từ để không tràn khỏi bề rộng ảnh (không dùng textwrap vì font không đều chiều rộng)."""
    lines = []
    for raw_line in text.split("\n"):
        if raw_line == "":
            lines.append("")
            continue
        words = raw_line.split(" ")
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def export_result_to_image(question: str, context_text: str, ai_reply: str, out_path: str) -> None:
    """Vẽ câu hỏi + ngữ cảnh + câu trả lời AI thành 1 ảnh PNG, hỗ trợ tiếng Việt có dấu."""
    width = 1000
    margin = 30
    max_text_width = width - 2 * margin

    # Font hệ thống Windows có sẵn, hỗ trợ tiếng Việt có dấu.
    font_path = r"C:\Windows\Fonts\segoeui.ttf"
    font_bold_path = r"C:\Windows\Fonts\segoeuib.ttf"
    try:
        font_title = ImageFont.truetype(font_bold_path, 22)
        font_heading = ImageFont.truetype(font_bold_path, 17)
        font_body = ImageFont.truetype(font_path, 16)
    except OSError:
        font_title = font_heading = font_body = ImageFont.load_default()

    tmp_img = Image.new("RGB", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp_img)

    sections = [
        ("TRỢ LÝ ĐỊA CHẤT AI — RAG (ChromaDB + Ollama)", font_title),
        ("", font_body),
        ("Câu hỏi:", font_heading),
        *[(line, font_body) for line in wrap_text(question, font_body, max_text_width, tmp_draw)],
        ("", font_body),
        ("Dữ liệu địa chất liên quan:", font_heading),
        *[(line, font_body) for line in wrap_text(context_text, font_body, max_text_width, tmp_draw)],
        ("", font_body),
        ("Trả lời của AI:", font_heading),
        *[(line, font_body) for line in wrap_text(ai_reply, font_body, max_text_width, tmp_draw)],
    ]

    line_height = 24
    height = margin * 2 + sum(line_height + (10 if f in (font_title, font_heading) else 0) for _, f in sections)

    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    y = margin
    for text, font in sections:
        if font is font_heading or font is font_title:
            y += 6
            draw.line([(margin, y - 2), (width - margin, y - 2)], fill="#DDDDDD") if font is font_heading else None
        draw.text((margin, y), text, font=font, fill="#1A1A1A" if font is not font_title else "#0B5394")
        y += line_height

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


def main():
    print("=========================================")
    print("VÍ DỤ 2: RAG (AI TRỢ LÝ ĐỊA CHẤT)")
    print("=========================================")

    chroma_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
    if not os.path.exists(chroma_path):
        print(f"Lỗi: Không tìm thấy ChromaDB tại {chroma_path}.")
        return

    print("Đang tải ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(name="geology_layers")
    except Exception as e:
        print(f"Lỗi: Không tìm thấy collection 'geology_layers'. Chi tiết: {e}")
        return

    print("-" * 40)

    while True:
        question = input("\nNhập câu hỏi chuyên môn (hoặc 'exit'): ")
        if question.strip().lower() in ['exit', 'quit']:
            break

        if not question.strip():
            continue

        print(f"\n[Bước 1] Lấy Context từ ChromaDB cho câu hỏi: '{question}'...")
        results = collection.query(
            query_texts=[question],
            n_results=4
        )

        context_docs = results['documents'][0]
        context_text = "\n".join([f"- {doc}" for doc in context_docs])

        print(f"[Bước 1 Xong] Đã tìm thấy {len(context_docs)} lớp đất liên quan.")

        print("\n[Bước 2] Xây dựng Prompt cho LLM...")

        prompt = f"""Bạn là một kỹ sư địa kỹ thuật AI. Hãy trả lời câu hỏi sau dựa trên dữ liệu địa chất được cung cấp.

DỮ LIỆU ĐỊA CHẤT:
{context_text}

CÂU HỎI CỦA NGƯỜI DÙNG:
{question}

TRẢ LỜI:
"""
        print("\n--- PROMPT SẼ GỬI ĐẾN AI ---")
        print(prompt)
        print("----------------------------\n")

        print(f"[Bước 3] Đang gửi tới Local Ollama ({OLLAMA_MODEL})...")
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT_S
            )

            if response.status_code == 200:
                ai_reply = response.json().get("response", "")
                print(">>> AI TRẢ LỜI:\n")
                print(ai_reply)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = os.path.join(RESULTS_DIR, f"rag_qa_{timestamp}.png")
                try:
                    export_result_to_image(question, context_text, ai_reply, out_path)
                    print(f"\n[Bước 4] Đã xuất kết quả ra ảnh: {out_path}")
                except Exception as e:
                    print(f"\n[Lỗi] Không xuất được ảnh: {e}")
            else:
                print(f"Lỗi từ Ollama: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print("\n[LỖI] Không thể kết nối với Ollama Server (có thể server đang tắt hoặc bị timeout).")
            print(f"Chi tiết: {e}")
            print("\n*Ghi chú: Nếu Ollama không khả dụng, bạn có thể thay thế đoạn code 'requests.post' bằng API của OpenAI hoặc Gemini.*")

if __name__ == "__main__":
    main()
