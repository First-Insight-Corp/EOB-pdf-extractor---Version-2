from PIL import Image
from PyPDF2 import PdfMerger
import os
import tempfile

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


def sanitize_filename(name: str) -> str:
    return name.replace(" ", "_")


def convert_images_to_pdf(image_paths: list[str], out_pdf: str) -> str:
    """Convert a list of image file paths into a single multi-page PDF.

    Approach: convert each image to a single-page PDF using Pillow into a
    temporary file, then merge them using PyPDF2.PdfMerger. This avoids
    edge-cases with multi-frame images and ensures one page per input image.
    """
    if not image_paths:
        raise ValueError("No images provided")

    temp_pdfs = []
    try:
        for path in image_paths:
            with Image.open(path) as img:
                # Ensure RGB for PDF
                if img.mode in ("RGBA", "LA") or (img.mode == "P"):
                    img_converted = img.convert("RGB")
                else:
                    img_converted = img.convert("RGB")

                fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                img_converted.save(tmp_pdf, "PDF", resolution=100.0)
                temp_pdfs.append(tmp_pdf)

        merger = PdfMerger()
        try:
            for p in temp_pdfs:
                merger.append(p)
            with open(out_pdf, "wb") as fh:
                merger.write(fh)
        finally:
            try:
                merger.close()
            except Exception:
                pass

    finally:
        for p in temp_pdfs:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    return out_pdf


def merge_pdfs(pdf_paths: list[str], out_pdf: str) -> str:
    """Merge multiple PDFs into a single PDF at out_pdf."""
    merger = PdfMerger()
    try:
        for p in pdf_paths:
            merger.append(p)
        with open(out_pdf, "wb") as fh:
            merger.write(fh)
    finally:
        try:
            merger.close()
        except Exception:
            pass
    return out_pdf
