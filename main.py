from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import shutil
import time
from datetime import datetime
from typing import Literal, Optional, Tuple, Any
import logging
import uuid

from pdf_processor import PDFProcessor
from config import config
from format_loader import FormatLoader
from agents.agent_factory import get_extraction_agent, get_auditor_agent, get_critic_agent
from agents.extraction_graph import build_extraction_graph, run_extraction_workflow
from agents.token_logger import TokenLogger
from agents.format_generator_agent import FormatGeneratorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF Claims Extraction API",
    description="Extract structured insurance claims data from VSP and EyeMed PDFs using AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Validate configuration and setup directories
try:
    config.validate()
    logger.info("Configuration validated successfully")
except Exception as e:
    logger.error(f"Configuration validation failed: {str(e)}")
    raise


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "PDF Claims Extraction API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "process_pdf": "/api/v1/process-pdf",
            "list_responses": "/api/v1/responses"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestration": "LangGraph",
        "extraction_agent": config.EXTRACTION_AGENT,
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "claude_configured": bool(config.ANTHROPIC_API_KEY),
        "azure_di_configured": bool(config.AZURE_DI_KEY and config.AZURE_DI_ENDPOINT),
        "supported_formats": config.SUPPORTED_FORMATS,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/process-pdf")
async def process_pdf(
    file: UploadFile = File(..., description="PDF file to process"),
    document_type: str = Form(..., description="Document format (e.g. vsp, eyemed). Any format in formats/ folder is supported."),
):
    """
    Process PDF and extract structured claims data.
    
    Args:
        file: PDF file upload
        document_type: Type of document (vsp or eyemed)
    
    Returns:
        Structured JSON response with extracted claims
    """
    start_time = time.time()
    try:
        get_extraction_agent()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Validate document type (dynamic: any format module in formats/ is supported)
    doc_type_lower = document_type.lower().strip()
    if doc_type_lower not in config.SUPPORTED_FORMATS:
        # Try refreshing formats (picks up manually added files and syncs to DB)
        logger.info(f"Format '{doc_type_lower}' not in cache, refreshing from DB/Disk...")
        config.SUPPORTED_FORMATS = config.get_supported_formats()
        
        if doc_type_lower not in config.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported document type. Supported formats: {config.SUPPORTED_FORMATS}"
            )
    
    # Generate unique identification for this request
    request_id = str(uuid.uuid4())
    logger.info(f"Generated new request_id: {request_id}")

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = file.filename.replace(" ", "_")
    saved_filename = f"{timestamp}_{original_filename}"
    file_path = os.path.join(config.UPLOAD_DIR, saved_filename)
    
    try:
        # Save uploaded file
        logger.info(f"Saving uploaded file: {saved_filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Processing {doc_type_lower.upper()} PDF: {saved_filename} (size: {file_size} bytes)")
        
        # Step 1: Load format file for the document type (dynamic; no hardcoded structures)
        try:
            format_path = config.get_format_file(doc_type_lower)
            format_components = FormatLoader.load_format(format_path)
            schema_description = FormatLoader.get_schema_description(format_components)
            logger.info(f"Loaded format file: {format_path}")
        except FileNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading format file: {str(e)}"
            )
        
        # Step 2: Initialize PDF Processor
        pdf_processor = PDFProcessor(file_path)
        
        # Step 3: Get total pages and Pre-validate
        total_pages = pdf_processor.get_total_pages()
        logger.info(f"PDF has {total_pages} pages")
        
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF appears to be empty")
        
        if not pdf_processor.pre_validate():
            logger.warning("Pre-validation: PDF has no extractable text. Continuing with OCR.")

        # Step 4: Extraction Agent (Gemini or Claude from .env EXTRACTION_AGENT)
        extraction_agent = get_extraction_agent()
        extraction_agent.load_memory(doc_type_lower)
        extraction_agent.reset_memory(keep_learning=True)
        auditor = get_auditor_agent()
        critic = get_critic_agent()
        
        # Step 5: Early DB entry for linking logs
        current_processed_file_id = None
        try:
            from db import db, ProcessedFile, DocumentFormat
            if db:
                session = db.get_session()
                fmt = session.query(DocumentFormat).filter_by(short_name=doc_type_lower).first()
                template_id = fmt.id if fmt else None
                
                # Initial placeholder record
                processed_entry = ProcessedFile(
                    template_id=template_id,
                    file_path=None,
                    file_type="pdf",
                    request_logs={"status": "processing"}
                )
                session.add(processed_entry)
                session.commit()
                current_processed_file_id = processed_entry.processed_file_id
                session.close()
                logger.info(f"Created early DB log entry with ID: {current_processed_file_id}")
        except Exception as e:
            logger.error(f"Failed to create early DB log entry: {e}")

        # Step 6: Setup incremental response saving
        response_filename = f"{timestamp}_{doc_type_lower}_{original_filename.replace('.pdf', '')}_response.json"
        response_path = os.path.join(config.RESPONSE_DIR, response_filename)
        
        extracted_claims = []
        aggregated_metadata = {}
        previous_context = ""
        
        total_input_tokens = 0
        total_output_tokens = 0
        llm_usage_breakdown = {}
        total_iterations = 0
        total_role_usage = {"extractor": {}, "auditor": {}, "critic": {}}
        
        # CHUNKED PROCESSING STRATEGY FOR LARGE PDFS
        # Threshold for splitting into independent chunks to maintain 99% accuracy
        CHUNK_SIZE = config.MAX_PAGES_PER_CHUNK
        
        if total_pages > CHUNK_SIZE:
            logger.info(f"Large document detected ({total_pages} pages). Using Chunked Extraction strategy (size: {CHUNK_SIZE}).")
            
            chunks = []
            for start in range(1, total_pages + 1, CHUNK_SIZE):
                end = min(start + CHUNK_SIZE - 1, total_pages)
                chunks.append((start, end))
            
            total_batches_counter = 0
            for chunk_idx, (start, end) in enumerate(chunks):
                chunk_filename = f"chunk_{chunk_idx+1}_{saved_filename}"
                chunk_path = os.path.join(config.UPLOAD_DIR, chunk_filename)
                
                logger.info(f">>> PROCESSING CHUNK {chunk_idx+1}/{len(chunks)}: Pages {start}-{end}")
                pdf_processor.split_pdf(start, end, chunk_path)
                
                # We only carry over the 'previous_context' for claim continuity
                extraction_agent.reset_memory(keep_learning=True) # Clear history but KEEP lessons
                
                chunk_processor = PDFProcessor(chunk_path)
                try:
                    chunk_claims, chunk_metadata, chunk_ctx, chunk_batches, chunk_in, chunk_out, chunk_llm, chunk_loops, chunk_role_usage = run_extraction_pipeline(
                        pdf_processor=chunk_processor,
                        extraction_agent=extraction_agent,
                        auditor=auditor,
                        critic=critic,
                        format_components=format_components,
                        doc_type_lower=doc_type_lower,
                        schema_description=schema_description,
                        previous_context=previous_context, # carry over from end of last chunk
                        pdf_filename=saved_filename,
                        start_page_offset=start - 1,
                        processed_file_id=current_processed_file_id,
                        request_id=request_id
                    )
                    total_input_tokens += chunk_in
                    total_output_tokens += chunk_out
                    for model, usage in chunk_llm.items():
                        if model not in llm_usage_breakdown:
                            llm_usage_breakdown[model] = {"input": 0, "output": 0}
                        llm_usage_breakdown[model]["input"] += usage["input"]
                        llm_usage_breakdown[model]["output"] += usage["output"]
                    
                    total_iterations += chunk_loops
                    for role, usage in chunk_role_usage.items():
                        for model, counts in usage.items():
                            if model not in total_role_usage[role]:
                                total_role_usage[role][model] = {"input": 0, "output": 0}
                            total_role_usage[role][model]["input"] += counts["input"]
                            total_role_usage[role][model]["output"] += counts["output"]
                    
                    extracted_claims.extend(chunk_claims)
                    # Merge metadata
                    if chunk_metadata:
                        for k, v in chunk_metadata.items():
                            if isinstance(v, list):
                                if k not in aggregated_metadata or not isinstance(aggregated_metadata[k], list):
                                    aggregated_metadata[k] = []
                                aggregated_metadata[k].extend(v)
                            elif v:
                                aggregated_metadata[k] = v
                    
                    previous_context = chunk_ctx # update for NEXT chunk
                    total_batches_counter += chunk_batches
                    
                    # Progressive persistence
                    try:
                        map_data_fn = format_components.get("map_extracted_data")
                        full_data = map_data_fn(extracted_claims, aggregated_metadata) if map_data_fn else {"claims": extracted_claims, **aggregated_metadata}
                        current_response = FormatLoader.create_response(format_components=format_components, full_data=full_data, document_type=doc_type_lower.upper())
                        with open(response_path, "w") as f:
                            json.dump(current_response, f, indent=2)
                        logger.info(f"Chunk {chunk_idx+1} progress saved.")
                    except Exception as e:
                        logger.error(f"Failed to save progress for chunk {chunk_idx+1}: {e}")
                        
                finally:
                    chunk_processor.close()
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
            
            total_batches = total_batches_counter
        else:
            # Single document processing
            extracted_claims, aggregated_metadata, _, total_batches, single_in, single_out, single_llm, single_loops, single_role_usage = run_extraction_pipeline(
                pdf_processor=pdf_processor,
                extraction_agent=extraction_agent,
                auditor=auditor,
                critic=critic,
                format_components=format_components,
                doc_type_lower=doc_type_lower,
                schema_description=schema_description,
                previous_context="",
                pdf_filename=saved_filename,
                response_path=response_path,
                processed_file_id=current_processed_file_id,
                request_id=request_id
            )
            total_input_tokens += single_in
            total_output_tokens += single_out
            for model, usage in single_llm.items():
                if model not in llm_usage_breakdown:
                    llm_usage_breakdown[model] = {"input": 0, "output": 0}
                llm_usage_breakdown[model]["input"] += usage["input"]
                llm_usage_breakdown[model]["output"] += usage["output"]
            total_iterations = single_loops
            total_role_usage = single_role_usage
        
        # Calculate time taken
        time_taken = time.time() - start_time
        # Finalize processing
        extraction_agent.save_memory(doc_type_lower)
        TokenLogger.log_total(saved_filename, total_input_tokens, total_output_tokens, total_pages=total_pages, llm_usage_breakdown=llm_usage_breakdown)
        
        if not extracted_claims:
            logger.warning("No claims were extracted from the document")
            raise HTTPException(
                status_code=422,
                detail="No claims could be extracted from the PDF. Please verify the document format."
            )
        
        # Final response (format-driven; new formats work by adding a module under formats/)
        map_data_fn = format_components.get("map_extracted_data")
        full_data = map_data_fn(extracted_claims, aggregated_metadata) if map_data_fn else {"claims": extracted_claims, **aggregated_metadata}
        structured_response = FormatLoader.create_response(
            format_components=format_components,
            full_data=full_data,
            document_type=doc_type_lower.upper()
        )
        
        memory_summary = getattr(extraction_agent, "get_memory_summary", lambda: {"conversation_turns": 0})()
        
        # Step 9: Explicitly close PDF to release file handle
        pdf_processor.close()
        
        # Step 10: Cleanup uploaded file safely
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up uploaded file: {saved_filename}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {saved_filename}: {e}")
        
        # Step 11: Update MySQL processed_files with final metrics
        try:
            from db import db, ProcessedFile, DocumentFormat
            if db and current_processed_file_id:
                session = db.get_session()
                processed_entry = session.query(ProcessedFile).get(current_processed_file_id)
                if processed_entry:
                    # Combine LLMs used string
                    llms_list = list(llm_usage_breakdown.keys())
                    llm_used_str = " | ".join(llms_list)
                    
                    # Accuracy is placeholder for now or can be derived if Auditor has a score
                    accuracy = 100.0 # Placeholder
                    
                    request_logs = {
                        "no_of_iterations": total_iterations,
                        "accuracy_percentage": accuracy,
                        "llm_used": llm_used_str,
                        "no_of_tokens": {
                            "total": {"input": total_input_tokens, "output": total_output_tokens},
                            "by_role": total_role_usage
                        },
                        "time_taken_to_process": round(time_taken, 2),
                        "no_of_pages": total_pages,
                        "file_size": file_size,
                        "status": "success"
                    }
                    
                    processed_entry.request_logs = request_logs
                    processed_entry.final_response = structured_response
                    session.commit()
                session.close()
                logger.info(f"Updated processing metrics and final response in MySQL for ID: {current_processed_file_id}")
        except Exception as e:
            logger.error(f"Failed to update execution log in MySQL: {e}")
        
        # Return response
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Successfully processed {total_pages} pages and extracted {len(extracted_claims)} claims",
                "document_info": {
                    "filename": original_filename,
                    "type": doc_type_lower.upper(),
                    "total_pages": total_pages,
                    "batches_processed": total_batches
                },
                "data": structured_response,
                "response_file": response_filename,
                "processing_metadata": {
                    "conversation_turns": memory_summary['conversation_turns'],
                    "claims_extracted": len(extracted_claims),
                    "timestamp": datetime.now().isoformat()
                }
            },
            status_code=200
        )
        
    except HTTPException:
        # Ensure processor is closed even on HTTP exceptions if it exists
        if 'pdf_processor' in locals():
            pdf_processor.close()
        raise
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        
        # Safe cleanup on error
        if 'pdf_processor' in locals():
            try:
                pdf_processor.close()
            except:
                pass
                
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_err:
                logger.warning(f"Cleanup failed after error: {cleanup_err}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )


@app.get("/api/v1/responses")
async def list_responses():
    """List all saved response files from Database"""
    try:
        from db import db, ProcessedFile, DocumentFormat
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")
            
        session = db.get_session()
        # Fetch completed extractions (those with final_response or success status)
        results = session.query(ProcessedFile, DocumentFormat.short_name).\
            join(DocumentFormat, ProcessedFile.template_id == DocumentFormat.id, isouter=True).\
            order_by(ProcessedFile.date_time.desc()).all()
        
        response_list = []
        for record, fmt_name in results:
            if not record.final_response and not record.request_logs:
                continue
                
            response_list.append({
                "processed_id": record.processed_file_id,
                "document_type": (fmt_name or "unknown").upper(),
                "timestamp": record.date_time.isoformat(),
                "status": record.request_logs.get("status", "unknown") if isinstance(record.request_logs, dict) else "unknown",
                "request_id": record.request_logs.get("request_id", "N/A") if isinstance(record.request_logs, dict) else "N/A",
                "pages": record.request_logs.get("no_of_pages", 0) if isinstance(record.request_logs, dict) else 0
            })
        
        session.close()
        return {
            "total_responses": len(response_list),
            "responses": response_list
        }
    except Exception as e:
        logger.error(f"Error listing responses from DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/response/{processed_id}")
async def get_response(processed_id: int):
    """Get a specific response from Database by Processed ID"""
    try:
        from db import db, ProcessedFile
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")
            
        session = db.get_session()
        record = session.query(ProcessedFile).get(processed_id)
        session.close()
        
        if not record:
            raise HTTPException(status_code=404, detail="Response not found in database")
            
        if not record.final_response:
            raise HTTPException(status_code=404, detail="Extraction results not found for this record")
        
        return JSONResponse(content=record.final_response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading response from DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def run_extraction_pipeline(
    pdf_processor: PDFProcessor,
    extraction_agent: Any,
    auditor: Any,
    critic: Any,
    format_components: dict,
    doc_type_lower: str,
    schema_description: str,
    previous_context: str = "",
    pdf_filename: str = "",
    response_path: Optional[str] = None,
    start_page_offset: int = 0,
    processed_file_id: Optional[int] = None,
    request_id: Optional[str] = None
) -> Tuple[list, dict, str, int, int, int, dict, int, dict]:
    """
    Standard extraction logic for one PDF (Full or Chunk).
    Returns (claims, metadata, final_context, total_batches).
    """
    total_pages = pdf_processor.get_total_pages()
    batch_size = config.MAX_PAGES_PER_BATCH
    total_batches = (total_pages + batch_size - 1) // batch_size
    
    extracted_claims = []
    aggregated_metadata = {}
    current_previous_context = previous_context
    last_batch_text: Optional[str] = None
    last_batch_json: Optional[dict] = None
    total_input = 0
    total_output = 0
    llm_usage = {}
    total_loops = 0
    role_usage = {"extractor": {}, "auditor": {}, "critic": {}}
    
    batch_json_schema = format_components.get("batch_json_schema", "")
    response_json_schema = format_components.get("batch_json_schema", "")
    target_model = format_components.get("BatchModel")
    max_loops = getattr(config, "MAX_AUDITOR_CRITIC_LOOPS", 4)
    compiled_graph = build_extraction_graph(extraction_agent, auditor, critic)

    for i in range(0, total_pages, batch_size):
        batch_num = i // batch_size + 1
        current_batch_pages = list(range(i + 1, min(i + batch_size + 1, total_pages + 1)))
        is_last_batch = batch_num == total_batches
        
        # Adjusted for display logging
        disp_pages = [p + start_page_offset for p in current_batch_pages]
        logger.info(f"--- Sub-Batch {batch_num}/{total_batches} (Global Pages: {disp_pages}) ---")
        
        batch_content_list = pdf_processor.get_structured_text_for_pages(
            current_batch_pages,
            api_key=config.AZURE_DI_KEY,
            endpoint=config.AZURE_DI_ENDPOINT,
        )
        batch_text = "\n\n".join([f"=== PAGE {p['page_number'] + start_page_offset} ===\n{p['text']}" for p in batch_content_list])
        
        try:
            batch_images = pdf_processor.extract_images_from_pages(dpi=config.PDF_DPI, specific_pages=current_batch_pages)
        except Exception:
            batch_images = []
        
        is_continuation = (batch_num > 1 or bool(previous_context)) and bool(current_previous_context)
        
        pages_str = f"{min(current_batch_pages) + start_page_offset}-{max(current_batch_pages) + start_page_offset}"
        
        try:
            result, usage_in, usage_out, batch_llm, loop_count, batch_role_usage = run_extraction_workflow(
                compiled_graph,
                batch_text=batch_text,
                schema_description=schema_description,
                batch_json_schema=batch_json_schema,
                response_json_schema=response_json_schema,
                document_type=doc_type_lower.upper(),
                is_last_batch=is_last_batch,
                image_b64_list=batch_images,
                is_continuation=is_continuation,
                previous_context=current_previous_context,
                pdf_filename=pdf_filename,
                pages_str=pages_str,
                max_loops=max_loops,
                previous_batch_text=last_batch_text,
                previous_batch_json=last_batch_json,
                processed_file_id=processed_file_id,
                request_id=request_id
            )
            total_loops += loop_count
            for role, usage in batch_role_usage.items():
                for model, counts in usage.items():
                    if model not in role_usage[role]:
                        role_usage[role][model] = {"input": 0, "output": 0}
                    role_usage[role][model]["input"] += counts["input"]
                    role_usage[role][model]["output"] += counts["output"]
            total_input += usage_in
            total_output += usage_out
            for model, usage in batch_llm.items():
                if model not in llm_usage:
                    llm_usage[model] = {"input": 0, "output": 0}
                llm_usage[model]["input"] += usage["input"]
                llm_usage[model]["output"] += usage["output"]
            
            if target_model and result:
                if hasattr(extraction_agent, "pydantic_validator_critic"):
                    result = extraction_agent.pydantic_validator_critic(
                        data=result, model_class=target_model, batch_content=batch_text, max_retries=4
                    )
                else:
                    try:
                        validated = target_model.model_validate(result)
                        result = validated.model_dump()
                    except Exception: pass
        except Exception as e:
            logger.error(f"Pipeline failed at sub-batch {batch_num}: {e}")
            raise e
        
        batch_claims = result.get("claims") or result.get("entities") or []
        batch_metadata = result.get("metadata", {}) if isinstance(result.get("metadata"), dict) else {}
        
        if batch_claims:
            extracted_claims.extend(batch_claims)
        
        if batch_metadata:
            for k, v in batch_metadata.items():
                if isinstance(v, list):
                    if k not in aggregated_metadata or not isinstance(aggregated_metadata[k], list):
                        aggregated_metadata[k] = []
                    aggregated_metadata[k].extend(v)
                elif v:
                    aggregated_metadata[k] = v
        
        has_incomplete = result.get('has_incomplete_entity', result.get('has_incomplete_claim', False))
        if has_incomplete:
            incomplete_ctx = result.get('incomplete_entity_context', result.get('incomplete_claim_context', {}))
            current_previous_context = json.dumps(incomplete_ctx)
        else:
            current_previous_context = ""
            
        last_batch_text = batch_text
        last_batch_json = result
        
        if response_path:
            try:
                map_data_fn = format_components.get("map_extracted_data")
                full_data = map_data_fn(extracted_claims, aggregated_metadata) if map_data_fn else {"claims": extracted_claims, **aggregated_metadata}
                current_response = FormatLoader.create_response(format_components=format_components, full_data=full_data, document_type=doc_type_lower.upper())
                with open(response_path, "w") as f:
                    json.dump(current_response, f, indent=2)
            except Exception as e:
                logger.error(f"Incremental save failed: {e}")

    return extracted_claims, aggregated_metadata, current_previous_context, total_batches, total_input, total_output, llm_usage, total_loops, role_usage


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)


@app.post("/api/v1/generate-format")
async def generate_format_endpoint(
    short_name: str = Form(...),
    pdf_file: UploadFile = File(...),
    use_azure_di: bool = Form(False)
):
    """
    Generate a new Pydantic format file based on a sample PDF.
    
    This endpoint analyzes a new PDF format and auto-generates a Pydantic format file.
    It supports switching between Claude and Gemini providers and can use Azure Document 
    Intelligence for improved structural accuracy.
    """
    temp_path = os.path.join(config.UPLOAD_DIR, f"temp_gen_{pdf_file.filename}")
    pdf_processor = None
    try:
        with open(temp_path, "wb") as f:
            f.write(await pdf_file.read())
        
        pdf_processor = PDFProcessor(temp_path)
        total_pages = pdf_processor.get_total_pages()
        pages_to_use = list(range(1, min(4, total_pages + 1)))
        
        # 1. Get images (up to first 3 pages)
        images = pdf_processor.extract_images_from_pages(dpi=200, specific_pages=pages_to_use)
        
        # 2. Optionally get Azure DI for structural context
        azure_text = ""
        if use_azure_di and config.AZURE_DI_KEY:
            logger.info(f"Extracting Azure DI context for format generation (Pages: {pages_to_use})...")
            structured_pages = pdf_processor.get_structured_text_for_pages(
                pages_to_use,
                api_key=config.AZURE_DI_KEY,
                endpoint=config.AZURE_DI_ENDPOINT
            )
            azure_text = "\n\n".join([f"=== PAGE {p['page_number']} ===\n{p['text']}" for p in structured_pages])

        # 3. Initialize agent
        generator = FormatGeneratorAgent(
            anthropic_key=config.ANTHROPIC_API_KEY,
            gemini_key=config.GEMINI_API_KEY
        )
        
        # 4. Generate code
        code = generator.generate_format(
            pdf_images=images,
            short_name=short_name,
            provider=config.FORMAT_GEN_AGENT,
            model_name=config.FORMAT_GEN_MODEL,
            azure_text=azure_text
        )
        
        # 5. Save and validate
        saved_path = generator.save_format(code, short_name)
        
        return {
            "status": "success",
            "message": f"Format generated and saved to {saved_path}",
            "short_name": short_name,
            "provider_used": config.FORMAT_GEN_AGENT,
            "model_used": config.FORMAT_GEN_MODEL,
            "azure_di_used": bool(azure_text)
        }
    except Exception as e:
        logger.error(f"Format generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if pdf_processor:
            try:
                pdf_processor.close()
            except Exception:
                pass
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_path}: {e}")
