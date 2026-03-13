from pdf_processor import PDFProcessor
import os

pdf_path = r"d:\8 - EOB agentic solution\Backups\050225 - full working backup\pdfs\VSP-20 Pages.pdf"
try:
    p = PDFProcessor(pdf_path)
    # Extract first few and last few pages
    pages = p.extract_text_for_pages([1, 2, 18, 19, 20])
    
    with open("temp_layout_analysis.txt", "w", encoding="utf-8") as f:
        for page in pages:
            f.write(f"=== PAGE {page['page_number']} ===\n")
            f.write(page['text'])
            f.write("\n" + "="*50 + "\n")
            
    print("Extraction successful. Output saved to temp_layout_analysis.txt")
except Exception as e:
    print(f"Error: {e}")
