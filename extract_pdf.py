import pdfplumber
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

filename = sys.argv[1]
with pdfplumber.open(filename) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            print(f'--- PAGE {i+1} ---')
            print(text)
