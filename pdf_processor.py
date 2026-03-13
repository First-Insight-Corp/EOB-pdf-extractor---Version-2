import fitz  # PyMuPDF
from PIL import Image
import io
import base64
from typing import List, Dict, Tuple, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    """
    Comprehensive PDF processor that extracts text and images from PDFs.
    Uses PyMuPDF for robust, self-contained rendering.
    """
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = None
        self.total_pages = 0
        self.text_content = []
        self.page_images = []
        self._azure_di_cache: Dict[str, Any] = {}  # cached Azure DI result for structured extraction
        
    def _open_doc(self):
        if self.doc is None:
            self.doc = fitz.open(self.pdf_path)
            self.total_pages = len(self.doc)
            
    def close(self):
        """Close the PDF document and release resources"""
        if self.doc:
            self.doc.close()
            self.doc = None
            logger.info("PDF document closed")

    def get_total_pages(self) -> int:
        """Get total number of pages in PDF"""
        try:
            self._open_doc()
            logger.info(f"PDF has {self.total_pages} pages")
            return self.total_pages
        except Exception as e:
            logger.error(f"Error reading PDF page count: {str(e)}")
            raise
    
    def extract_text_for_pages(self, page_numbers: List[int]) -> List[Dict[str, Any]]:
        """
        Extract text specifically for requested page numbers (1-indexed).
        """
        try:
            self._open_doc()
            results = []
            for page_num in page_numbers:
                if 1 <= page_num <= self.total_pages:
                    page = self.doc[page_num - 1]
                    text = page.get_text()
                    results.append({
                        'page_number': page_num,
                        'text': text,
                        'char_count': len(text)
                    })
                    logger.info(f"Extracted text from page {page_num}")
            return results
        except Exception as e:
            logger.error(f"Error extracting specific pages text: {str(e)}")
            raise

    def extract_text_by_page(self) -> List[Dict[str, str]]:
        """
        Extract text from each page of the PDF.
        """
        try:
            self._open_doc()
            self.text_content = []
            
            for page_num in range(self.total_pages):
                page = self.doc[page_num]
                text = page.get_text()
                
                self.text_content.append({
                    'page_number': page_num + 1,
                    'text': text,
                    'char_count': len(text)
                })
                logger.info(f"Extracted text from page {page_num + 1}: {len(text)} characters")
            
            return self.text_content
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    def extract_images_from_pages(self, dpi: int = 200, specific_pages: List[int] = None) -> List[str]:
        """
        Convert PDF pages to images using PyMuPDF and return as base64 encoded strings.
        """
        try:
            self._open_doc()
            logger.info(f"Converting PDF pages to images with DPI: {dpi}")
            
            base64_images = []
            pages_to_process = specific_pages if specific_pages else range(1, self.total_pages + 1)
            
            # DPI to Matrix scale factor (72 is default PDF DPI)
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in pages_to_process:
                # fitz is 0-indexed
                page = self.doc[page_num - 1]
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PNG bytes
                img_data = pix.tobytes("png")
                img_str = base64.b64encode(img_data).decode()
                base64_images.append(img_str)
                
                logger.info(f"Converted page {page_num} to image")
            
            self.page_images = base64_images
            return base64_images
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            raise
    
    def get_page_batch(self, batch_size: int = 10) -> List[List[Dict[str, str]]]:
        """
        Split pages into batches for processing large PDFs.
        """
        if not self.text_content:
            self.extract_text_by_page()
        
        batches = []
        for i in range(0, len(self.text_content), batch_size):
            batch = self.text_content[i:i + batch_size]
            batches.append(batch)
            logger.info(f"Created batch {len(batches)} with {len(batch)} pages")
        
        return batches
    
    def get_full_text(self) -> str:
        """Get all text content as a single string"""
        if not self.text_content:
            self.extract_text_by_page()
        
        return "\n\n--- PAGE BREAK ---\n\n".join([
            f"=== PAGE {page['page_number']} ===\n{page['text']}" 
            for page in self.text_content
        ])
    
    def analyze_document_structure(self) -> Dict:
        """
        Analyze the PDF structure to understand content distribution.
        """
        if not self.text_content:
            self.extract_text_by_page()
        
        analysis = {
            'total_pages': self.total_pages,
            'total_characters': sum(page['char_count'] for page in self.text_content),
            'avg_chars_per_page': sum(page['char_count'] for page in self.text_content) / self.total_pages if self.total_pages > 0 else 0,
            'pages_with_content': sum(1 for page in self.text_content if page['char_count'] > 100),
            'pages_details': []
        }
        
        for page in self.text_content:
            analysis['pages_details'].append({
                'page': page['page_number'],
                'char_count': page['char_count'],
                'has_substantial_content': page['char_count'] > 100
            })
        
        return analysis

    def pre_validate(self) -> bool:
        """
        Check if PDF has extractable text.
        """
        self._open_doc()
        total_text = ""
        for page in self.doc:
            total_text += page.get_text()
        
        has_text = len(total_text.strip()) > 0
        if not has_text:
            logger.warning("PDF appears to have no extractable text (likely scanned image).")
        return has_text

    def extract_with_azure_di(self, api_key: str, endpoint: str) -> Dict[str, Any]:
        """
        Use Azure Document Intelligence to extract layout and tables.
        Result is cached so batch methods can reuse it without re-calling the API.
        """
        if not api_key or (api_key.strip() in ("", "YOUR_AZURE_DI_KEY")):
            logger.warning("Azure Document Intelligence Key is missing.")
            return {"error": "Azure DI Key missing", "tables": [], "paragraphs": [], "raw_result": None}

        if self._azure_di_cache.get("result"):
            logger.info("Using cached Azure DI result.")
            return self._azure_di_cache

        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential

            document_analysis_client = DocumentAnalysisClient(
                endpoint=endpoint.rstrip("/"), credential=AzureKeyCredential(api_key)
            )

            with open(self.pdf_path, "rb") as f:
                poller = document_analysis_client.begin_analyze_document(
                    "prebuilt-layout", document=f
                )
            result = poller.result()

            logger.info("Azure Document Intelligence analysis complete.")

            # Build page-indexed structures for table-aware text assembly
            tables_by_page: Dict[int, List[Any]] = {}
            paragraphs_by_page: Dict[int, List[Any]] = {}

            for t in result.tables:
                page_num = 1
                if t.bounding_regions:
                    page_num = t.bounding_regions[0].page_number
                tables_by_page.setdefault(page_num, []).append(t)

            for p in result.paragraphs:
                page_num = 1
                if p.bounding_regions:
                    page_num = p.bounding_regions[0].page_number
                paragraphs_by_page.setdefault(page_num, []).append(p)

            out = {
                "error": None,
                "tables": result.tables,
                "paragraphs": result.paragraphs,
                "tables_by_page": tables_by_page,
                "paragraphs_by_page": paragraphs_by_page,
                "raw_result": result,
                "pages": [p.to_dict() for p in result.pages] if hasattr(result, "pages") else [],
            }
            self._azure_di_cache = out
            return out
        except Exception as e:
            logger.error(f"Azure DI extraction failed: {e}")
            return {"error": str(e), "tables": [], "paragraphs": [], "tables_by_page": {}, "paragraphs_by_page": {}, "raw_result": None}

    def _table_to_structured_text(self, table: Any) -> str:
        """Render a single Azure DI table as structured text (grid) so structure is preserved."""
        try:
            row_count = getattr(table, "row_count", 0) or 0
            column_count = getattr(table, "column_count", 0) or 0
            cells = getattr(table, "cells", []) or []
            if not cells and hasattr(table, "to_dict"):
                d = table.to_dict()
                row_count = d.get("row_count", 0)
                column_count = d.get("column_count", 0)
                cells = d.get("cells", [])

            grid: Dict[Tuple[int, int], str] = {}
            for c in cells:
                if hasattr(c, "row_index"):
                    r, col = c.row_index, c.column_index
                    content = (getattr(c, "content", None) or "").strip()
                else:
                    r, col = c.get("row_index", 0), c.get("column_index", 0)
                    content = (c.get("content") or "").strip()
                grid[(r, col)] = content or ""

            lines = []
            for r in range(row_count):
                row_cells = [grid.get((r, c), "") for c in range(column_count)]
                lines.append(" | ".join(row_cells))
            return "[TABLE]\n" + "\n".join(lines) + "\n[/TABLE]"
        except Exception as e:
            logger.warning(f"Table render failed: {e}")
            return "[TABLE]\n(parse error)\n[/TABLE]"

    def get_structured_text_for_pages(
        self,
        page_numbers: List[int],
        api_key: str = "",
        endpoint: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Get text for the given page range with table structure preserved.
        Uses Azure Document Intelligence when credentials are provided and successful;
        otherwise falls back to PyMuPDF.
        Returns list of {"page_number", "text", "char_count", "source": "azure_di"|"pymupdf"}.
        """
        results = []
        use_azure = bool(api_key and endpoint and api_key.strip() not in ("", "YOUR_AZURE_DI_KEY"))

        if use_azure:
            azure_result = self.extract_with_azure_di(api_key, endpoint)
            if not azure_result.get("error") and azure_result.get("raw_result"):
                tables_by_page = azure_result.get("tables_by_page") or {}
                paragraphs_by_page = azure_result.get("paragraphs_by_page") or {}
                for page_num in page_numbers:
                    parts = []
                    for p in paragraphs_by_page.get(page_num, []):
                        content = getattr(p, "content", None) or (p.get("content") if isinstance(p, dict) else "")
                        if content:
                            parts.append(content.strip())
                    for t in tables_by_page.get(page_num, []):
                        parts.append(self._table_to_structured_text(t))
                    text = "\n\n".join(parts)
                    if not text.strip():
                        # Fallback to PyMuPDF for this page if Azure left it empty
                        fallback = self.extract_text_for_pages([page_num])
                        text = fallback[0]["text"] if fallback else ""
                    results.append({
                        "page_number": page_num,
                        "text": text,
                        "char_count": len(text),
                        "source": "azure_di",
                    })
                if results:
                    return results
            logger.warning("Azure DI failed or empty; falling back to PyMuPDF for batch.")
        # Fallback: PyMuPDF
        fallback_list = self.extract_text_for_pages(page_numbers)
        for p in fallback_list:
            p["source"] = "pymupdf"
            results.append(p)
        return results

    def split_pdf(self, start_page: int, end_page: int, output_path: str) -> str:
        """
        Extract a range of pages (1-indexed, inclusive) into a new PDF file.
        Returns the output path.
        """
        try:
            self._open_doc()
            new_doc = fitz.open()
            # fitz is 0-indexed, end_page is inclusive
            new_doc.insert_pdf(self.doc, from_page=start_page - 1, to_page=end_page - 1)
            new_doc.save(output_path)
            new_doc.close()
            logger.info(f"Successfully split PDF: pages {start_page}-{end_page} to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error splitting PDF: {e}")
            raise

    @staticmethod
    def section_builder(text: str) -> List[Dict[str, str]]:
        """
        Generic section builder that returns the full text as one section.
        The actual document-specific sectioning is now handled by format modules.
        """
        return [{"type": "content", "text": text}]
