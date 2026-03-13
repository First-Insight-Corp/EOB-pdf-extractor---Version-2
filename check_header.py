import fitz
import sys

def check_pdf(pdf_path):
    print(f"Checking {pdf_path}")
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text()
    lines = text.split('\n')
    for i, line in enumerate(lines[:30]):
        print(f"{i+1}: {line}")

if __name__ == "__main__":
    check_pdf(r"d:\8 - EOB agentic solution\Backups\050225 - full working backup\pdfs\VSP - 4pages.pdf")
