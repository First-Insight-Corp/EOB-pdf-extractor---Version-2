# PDF Claims Extraction API

Extract structured insurance claims data from multi-page PDFs (e.g. VSP, EyeMed) using AI. Supports complex tables via **Azure Document Intelligence** and a multi-agent pipeline (**Extraction → Auditor → Critic**) for high-accuracy output.

## Quick start

1. **Environment**  
   Copy `.env.example` to `.env` and set:
   - `EXTRACTION_AGENT=gemini` or `claude`
   - For Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL`
   - For Claude: `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
   - Optional: `AZURE_DI_KEY`, `AZURE_DI_ENDPOINT` for table-aware extraction

2. **Install and run**
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Or: `python main.py`

3. **Process a PDF**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/process-pdf" \
     -F "file=@your_document.pdf" \
     -F "document_type=vsp"
   ```

## Documentation

- **ARCHITECTURE.md** — Full system design: components, data flow, config, and how to add new formats.

## Main features

- **Switchable extraction agent**: Gemini or Claude via `EXTRACTION_AGENT` in `.env`
- **Table-aware text**: Azure Document Intelligence preserves table structure; fallback to PyMuPDF
- **Feedback loop**: Auditor compares extraction to source; Critic produces improvement instructions; Extraction Agent re-runs until issues are resolved (configurable max loops)
- **Dynamic formats**: New document types by adding a module under `formats/` (see ARCHITECTURE.md)

## Project layout (essential)

- `main.py` — FastAPI app and pipeline orchestration
- `config.py` — Configuration from environment
- `pdf_processor.py` — PDF text (Azure DI + PyMuPDF) and images
- `format_loader.py` — Load format modules and build responses
- `formats/` — One module per document type (vsp, eyemed, …)
- `agents/` — Extraction (Gemini/Claude), Auditor, Critic, factory

See **ARCHITECTURE.md** for details.
