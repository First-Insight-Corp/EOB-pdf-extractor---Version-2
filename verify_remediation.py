import logging
import json
import base64
from agents.gemini_agent import GeminiAgent
from config import config
from pdf_processor import PDFProcessor
from format_loader import FormatLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_remediation():
    pdf_path = r"d:\8 - EOB agentic solution\Backups\050225 - full working backup\pdfs\VSP_26Page (1).pdf"
    doc_type = "vsp"
    
    config.validate()
    format_path = config.get_format_file(doc_type)
    format_components = FormatLoader.load_format(format_path)
    schema_description = FormatLoader.get_schema_description(format_components)
    
    processor = PDFProcessor(pdf_path)
    agent = GeminiAgent(api_key=config.GEMINI_API_KEY, model_name=config.GEMINI_MODEL)
    
    # Process First Two Batches to test Doctor inheritance
    # Batch 1 (1-5)
    pages1 = [1, 2, 3, 4, 5]
    text1 = processor.extract_text_for_pages(pages1)
    batch_text1 = "\n\n".join([f"=== PAGE {p['page_number']} ===\n{p['text']}" for p in text1])
    images1 = processor.extract_images_from_pages(dpi=200, specific_pages=pages1)
    
    print("--- STEP 1: Processing Batch 1 (Pages 1-5) ---")
    result1 = agent.executive_react_extraction(
        document_type=doc_type.upper(),
        batch_text=batch_text1,
        schema_description=schema_description,
        json_schema=format_components.get('json_schema', ""),
        response_json_schema=format_components.get('response_json_schema', ""),
        image_b64_list=images1,
        is_continuation=False,
        previous_context="",
        is_last_batch=False
    )
    
    # Check doctor in Batch 1
    last_doc = agent.learning_memory.active_state.get('current_doctor')
    print(f"Active Doctor after Batch 1: {last_doc}")
    
    # Batch 2 (6-10) - Test Inheritance
    pages2 = [6, 7, 8, 9, 10]
    text2 = processor.extract_text_for_pages(pages2)
    batch_text2 = "\n\n".join([f"=== PAGE {p['page_number']} ===\n{p['text']}" for p in text2])
    images2 = processor.extract_images_from_pages(dpi=200, specific_pages=pages2)
    
    print("\n--- STEP 2: Processing Batch 2 (Pages 6-10) with State Inheritance ---")
    result2 = agent.executive_react_extraction(
        document_type=doc_type.upper(),
        batch_text=batch_text2,
        schema_description=schema_description,
        json_schema=format_components.get('json_schema', ""),
        response_json_schema=format_components.get('response_json_schema', ""),
        image_b64_list=images2,
        is_continuation=True,
        previous_context="", # State is now internal
        is_last_batch=False
    )
    
    # Verify inheritance in Batch 2
    claims2 = result2.get('entities', result2.get('claims', []))
    inherited_docs = [c.get('treating_doctor') for c in claims2 if c.get('treating_doctor') == last_doc]
    print(f"Batch 2 Claims: {len(claims2)}, Inherited '{last_doc}': {len(inherited_docs)}")
    
    if len(inherited_docs) > 0:
        print("SUCCESS: Doctor inheritance via stateful memory verified.")
    else:
        print("FAILURE: Doctor inheritance failed.")

if __name__ == "__main__":
    test_remediation()
