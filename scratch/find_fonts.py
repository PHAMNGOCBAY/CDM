import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('app_cdm.py', encoding='utf-8') as f:
    lines = f.readlines()

keywords = ['font_size', 'fontsize', 'title_font', 'label_font', 'tick_font',
            'axis_font', 'CTkFont', 'Consolas', 'Arial', 'Calibri',
            'font=', '"font"', 'size=1', 'size=2', 'FONT', 'font(']

results = []
for i, line in enumerate(lines):
    for kw in keywords:
        if kw.lower() in line.lower():
            results.append((i+1, line.rstrip()))
            break

for ln, text in results[:150]:
    print(f'{ln}: {text}')

print(f'\nTotal: {len(results)} lines')
