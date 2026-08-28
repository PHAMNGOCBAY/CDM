from docling.document_converter import DocumentConverter

pdf_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\ccx_2.20.pdf"
md_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\ccx_2.20.md"
json_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\ccx_2.20.json"

print("Initializing DocumentConverter...")
converter = DocumentConverter()

print(f"Processing file: {pdf_path}")
result = converter.convert(pdf_path)

print(f"Exporting to Markdown: {md_path}")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(result.document.export_to_markdown())

print(f"Exporting to JSON: {json_path}")
with open(json_path, "w", encoding="utf-8") as f:
    # `export_to_dict` can be serialized to JSON, or `export_to_json` if supported directly by docling
    # As of recent docling versions, export_to_dict() is common. Let's use json module just in case.
    import json
    f.write(json.dumps(result.document.export_to_dict(), ensure_ascii=False, indent=2))

print("Done!")
