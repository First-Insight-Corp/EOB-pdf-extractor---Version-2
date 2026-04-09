from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import ast
import os
import json
import shutil
import time
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Literal, Optional, Tuple, Any
import logging
import uuid
from pydantic import BaseModel

# Import logging configuration FIRST, before other modules
from logs_config import setup_logging, get_logger, log_api_request, log_pdf_processing, log_extraction_step, log_chunk_processing, log_db_operation

# Setup centralized logging
logger = setup_logging(app_name="Main_API")

from pdf_processor import PDFProcessor
from config import config
from format_loader import FormatLoader
from agents.agent_factory import get_extraction_agent, get_auditor_agent, get_critic_agent
from agents.extraction_graph import build_extraction_graph, run_extraction_workflow
from agents.token_logger import TokenLogger
from agents.format_generator_agent import FormatGeneratorAgent
from cost_calculator import get_cost_breakdown

# Initialize FastAPI app
app = FastAPI(
    title="PDF Claims Extraction API",
    description="Extract structured insurance claims data using Background Tasks",
    version="1.1.0"
)


class KnowledgeUpdateRequest(BaseModel):
    lessons: Optional[list] = None
    layout_patterns: Optional[dict] = None


class DocumentFormatUpdateRequest(BaseModel):
    python_code: str

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


@app.get("/api/v1/formats")
async def list_formats(refresh: bool = False):
    """Return all currently supported document formats."""
    try:
        if refresh:
            config.SUPPORTED_FORMATS = config.get_supported_formats()

        return {
            "total_formats": len(config.SUPPORTED_FORMATS),
            "formats": config.SUPPORTED_FORMATS,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error listing formats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/document-formats")
async def list_document_formats(include_code: bool = Query(False)):
    """List template records from document_formats table."""
    try:
        from db import db, DocumentFormat

        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        session = db.get_session()
        rows = session.query(DocumentFormat).order_by(DocumentFormat.updated_at.desc()).all()

        formats = []
        for row in rows:
            item = {
                "id": row.id,
                "short_name": row.short_name,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            if include_code:
                item["python_code"] = row.python_code
            formats.append(item)

        session.close()
        return {
            "total_formats": len(formats),
            "formats": formats,
        }
    except Exception as e:
        logger.error(f"Error listing document formats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/document-formats/{format_id}")
async def update_document_format(format_id: int, payload: DocumentFormatUpdateRequest):
    """Update template python code in DB and local formats/*.py file."""
    session = None
    try:
        from db import db, DocumentFormat

        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        updated_code = (payload.python_code or "").strip()
        if not updated_code:
            raise HTTPException(status_code=400, detail="python_code cannot be empty")

        try:
            ast.parse(updated_code)
        except SyntaxError as parse_err:
            raise HTTPException(status_code=400, detail=f"Invalid Python code: {parse_err.msg}")

        session = db.get_session()
        record = session.query(DocumentFormat).filter_by(id=format_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Template with ID {format_id} not found")

        format_path = config.get_format_file(record.short_name)
        os.makedirs(config.FORMATS_DIR, exist_ok=True)
        with open(format_path, "w", encoding="utf-8") as f:
            f.write(updated_code)

        record.python_code = updated_code
        record.updated_at = datetime.utcnow()
        session.commit()

        config.SUPPORTED_FORMATS = config.get_supported_formats()
        log_db_operation("UPDATE", "DocumentFormat", "Success", f"ID {format_id}")

        updated_payload = {
            "id": record.id,
            "short_name": record.short_name,
            "python_code": record.python_code,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

        return {
            "status": "success",
            "message": f"Template {record.short_name} updated successfully",
            "format": updated_payload,
            "format_raw_text": record.python_code,
        }
    except HTTPException:
        if session:
            session.rollback()
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Error updating template {format_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if session:
            session.close()


def run_background_extraction(
    processed_file_id: int,
    file_path: str,
    doc_type_lower: str,
    original_filename: str,
    saved_filename: str,
    request_id: str,
    file_size: int,
):
    """Background extraction worker that updates DB status and final response."""
    start_time = time.time()
    pdf_processor = PDFProcessor(file_path)

    try:
        format_path = config.get_format_file(doc_type_lower)
        format_components = FormatLoader.load_format(format_path)
        schema_description = FormatLoader.get_schema_description(format_components)
        log_extraction_step("Format Loading", "Success", request_id, format_path)

        total_pages = pdf_processor.get_total_pages()
        log_pdf_processing(saved_filename, doc_type_lower, total_pages, request_id)
        if total_pages == 0:
            raise ValueError("PDF appears to be empty")

        if not pdf_processor.pre_validate():
            logger.warning(f"[{request_id}] Pre-validation: PDF has no extractable text. Continuing with OCR.")

        extraction_agent = get_extraction_agent()
        extraction_agent.load_memory(doc_type_lower)
        extraction_agent.reset_memory(keep_learning=True)
        auditor = get_auditor_agent()
        critic = get_critic_agent()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

        CHUNK_SIZE = config.MAX_PAGES_PER_CHUNK

        if total_pages > CHUNK_SIZE:
            chunks = []
            for start in range(1, total_pages + 1, CHUNK_SIZE):
                end = min(start + CHUNK_SIZE - 1, total_pages)
                chunks.append((start, end))

            total_batches = 0
            for chunk_idx, (start, end) in enumerate(chunks):
                chunk_filename = f"chunk_{chunk_idx+1}_{saved_filename}"
                chunk_path = os.path.join(config.UPLOAD_DIR, chunk_filename)
                log_chunk_processing(chunk_idx + 1, len(chunks), start, end, request_id)
                pdf_processor.split_pdf(start, end, chunk_path)
                extraction_agent.reset_memory(keep_learning=True)

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
                        previous_context=previous_context,
                        pdf_filename=saved_filename,
                        start_page_offset=start - 1,
                        processed_file_id=processed_file_id,
                        request_id=request_id,
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
                    if chunk_metadata:
                        for k, v in chunk_metadata.items():
                            if isinstance(v, list):
                                if k not in aggregated_metadata or not isinstance(aggregated_metadata[k], list):
                                    aggregated_metadata[k] = []
                                aggregated_metadata[k].extend(v)
                            elif v:
                                aggregated_metadata[k] = v

                    previous_context = chunk_ctx
                    total_batches += chunk_batches

                    map_data_fn = format_components.get("map_extracted_data")
                    full_data = map_data_fn(extracted_claims, aggregated_metadata) if map_data_fn else {"claims": extracted_claims, **aggregated_metadata}
                    current_response = FormatLoader.create_response(
                        format_components=format_components,
                        full_data=full_data,
                        document_type=doc_type_lower.upper(),
                    )
                    with open(response_path, "w") as f:
                        json.dump(current_response, f, indent=2)
                finally:
                    chunk_processor.close()
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
        else:
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
                processed_file_id=processed_file_id,
                request_id=request_id,
            )
            total_input_tokens += single_in
            total_output_tokens += single_out
            llm_usage_breakdown = single_llm
            total_iterations = single_loops
            total_role_usage = single_role_usage

        if not extracted_claims:
            raise ValueError("No claims could be extracted from the PDF. Please verify the document format.")

        map_data_fn = format_components.get("map_extracted_data")
        full_data = map_data_fn(extracted_claims, aggregated_metadata) if map_data_fn else {"claims": extracted_claims, **aggregated_metadata}
        structured_response = FormatLoader.create_response(
            format_components=format_components,
            full_data=full_data,
            document_type=doc_type_lower.upper(),
        )

        with open(response_path, "w") as f:
            json.dump(structured_response, f, indent=2)

        extraction_agent.save_memory(doc_type_lower)
        TokenLogger.log_total(
            saved_filename,
            total_input_tokens,
            total_output_tokens,
            total_pages=total_pages,
            llm_usage_breakdown=llm_usage_breakdown,
        )

        from db import db, ProcessedFile

        if db:
            session = db.get_session()
            try:
                processed_entry = session.query(ProcessedFile).get(processed_file_id)
                if processed_entry:
                    llm_used_str = " | ".join(list(llm_usage_breakdown.keys()))
                    
                    # Calculate cost breakdown
                    token_breakdown = {
                        "total": {"input": total_input_tokens, "output": total_output_tokens},
                        "by_role": total_role_usage,
                    }
                    cost_breakdown = get_cost_breakdown(token_breakdown)
                    total_cost = cost_breakdown.get("total", 0.0)
                    
                    processed_entry.request_logs = {
                        "status": "success",
                        "time_taken_to_process": round(time.time() - start_time, 2),
                        "no_of_pages": total_pages,
                        "no_of_iterations": total_iterations,
                        "llm_used": llm_used_str,
                        "no_of_tokens": {
                            "total": {"input": total_input_tokens, "output": total_output_tokens},
                            "by_role": total_role_usage,
                        },
                        "file_size": file_size,
                        "request_id": request_id,
                        "original_filename": original_filename,
                        "saved_filename": saved_filename,
                        "response_file": os.path.basename(response_path),
                        "batches_processed": total_batches,
                        "cost_breakdown": cost_breakdown,
                    }
                    processed_entry.total_cost = total_cost
                    processed_entry.cost_breakdown = cost_breakdown
                    processed_entry.final_response = structured_response
                    processed_entry.final_response_raw_text = json.dumps(structured_response, indent=2)
                    session.commit()
                    logger.info(f"[{request_id}] Total processing cost: ${total_cost:.4f}")
            finally:
                session.close()
    except Exception as e:
        logger.error(f"Background task failed for {request_id}: {e}", exc_info=True)
        from db import db, ProcessedFile

        if db:
            session = db.get_session()
            try:
                processed_entry = session.query(ProcessedFile).get(processed_file_id)
                if processed_entry:
                    # Even on failure, calculate cost for partial processing
                    cost_breakdown = None
                    total_cost = 0.0
                    
                    if total_input_tokens > 0 or total_output_tokens > 0:
                        token_breakdown = {
                            "total": {"input": total_input_tokens, "output": total_output_tokens},
                            "by_role": total_role_usage,
                        }
                        cost_breakdown = get_cost_breakdown(token_breakdown)
                        total_cost = cost_breakdown.get("total", 0.0)
                    
                    processed_entry.request_logs = {
                        "status": "failed",
                        "request_id": request_id,
                        "original_filename": original_filename,
                        "saved_filename": saved_filename,
                        "error": str(e),
                        "partial_cost": total_cost if total_cost > 0 else None,
                        "cost_breakdown": cost_breakdown,
                    }
                    processed_entry.total_cost = total_cost
                    processed_entry.cost_breakdown = cost_breakdown
                    session.commit()
                    if total_cost > 0:
                        logger.info(f"[{request_id}] Partial processing cost (failed): ${total_cost:.4f}")
            finally:
                session.close()
    finally:
        pdf_processor.close()
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/v1/process-pdf")
async def process_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form(...),
):
    try:
        get_extraction_agent()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    request_id = str(uuid.uuid4())
    doc_type_lower = document_type.lower().strip()

    if doc_type_lower not in config.SUPPORTED_FORMATS:
        logger.info(f"Format '{doc_type_lower}' not in cache, refreshing from DB/Disk...")
        config.SUPPORTED_FORMATS = config.get_supported_formats()
        if doc_type_lower not in config.SUPPORTED_FORMATS:
            raise HTTPException(status_code=400, detail=f"Unsupported document type. Supported formats: {config.SUPPORTED_FORMATS}")

    log_api_request("/api/v1/process-pdf", "POST", request_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = file.filename.replace(" ", "_")
    saved_filename = f"{timestamp}_{original_filename}"
    file_path = os.path.join(config.UPLOAD_DIR, saved_filename)

    current_processed_file_id = None
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        from db import db, ProcessedFile, DocumentFormat

        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        session = db.get_session()
        try:
            fmt = session.query(DocumentFormat).filter_by(short_name=doc_type_lower).first()
            processed_entry = ProcessedFile(
                template_id=fmt.id if fmt else None,
                file_path=saved_filename,
                file_type="pdf",
                request_logs={
                    "status": "processing",
                    "request_id": request_id,
                    "original_filename": original_filename,
                    "saved_filename": saved_filename,
                },
            )
            session.add(processed_entry)
            session.commit()
            current_processed_file_id = processed_entry.processed_file_id
            log_db_operation("INSERT", "ProcessedFile", "Success", request_id)
        finally:
            session.close()

        background_tasks.add_task(
            run_background_extraction,
            current_processed_file_id,
            file_path,
            doc_type_lower,
            original_filename,
            saved_filename,
            request_id,
            file_size,
        )

        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "processed_id": current_processed_file_id,
                "message": "Processing started. Use the GET response endpoint to fetch results.",
                "check_status_url": f"/api/v1/response/{current_processed_file_id}",
            },
        )
    except HTTPException:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Error queuing PDF processing: {str(e)}")


@app.get("/api/v1/responses")
async def list_responses(
    include_raw_text: bool = Query(False),
    include_metrics: bool = Query(False),
    include_raw_request_logs: bool = Query(False),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=500),
):
    """List all saved response files from Database"""
    try:
        from db import db, ProcessedFile, DocumentFormat, ExtractionTokenLog
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")
            
        session = db.get_session()
        # Fetch completed extractions (those with final_response or request logs)
        base_query = session.query(ProcessedFile, DocumentFormat.short_name).\
            join(DocumentFormat, ProcessedFile.template_id == DocumentFormat.id, isouter=True)

        total_rows = base_query.count()
        if page and page_size:
            offset = (page - 1) * page_size
            results = base_query.order_by(ProcessedFile.date_time.desc()).offset(offset).limit(page_size).all()
        else:
            results = base_query.order_by(ProcessedFile.date_time.desc()).all()

        token_logs_by_file_id = defaultdict(list)
        if include_metrics:
            processed_ids = [record.processed_file_id for record, _ in results]
            if processed_ids:
                token_rows = session.query(ExtractionTokenLog).filter(
                    ExtractionTokenLog.processed_file_id.in_(processed_ids)
                ).all()
                for token_row in token_rows:
                    token_logs_by_file_id[token_row.processed_file_id].append(token_row)
        
        response_list = []
        for record, fmt_name in results:
            if not record.final_response and not record.request_logs:
                continue
                
            request_logs = record.request_logs if isinstance(record.request_logs, dict) else {}
            no_of_tokens = request_logs.get("no_of_tokens", {}) if isinstance(request_logs.get("no_of_tokens", {}), dict) else {}
            total_tokens = no_of_tokens.get("total", {}) if isinstance(no_of_tokens.get("total", {}), dict) else {}

            response_item = {
                "processed_id": record.processed_file_id,
                "document_type": (fmt_name or "unknown").upper(),
                "timestamp": record.date_time.isoformat(),
                "status": request_logs.get("status", "unknown"),
                "request_id": request_logs.get("request_id", "N/A"),
                "pages": request_logs.get("no_of_pages", 0),
                "response_file": request_logs.get("response_file"),
                "total_cost": record.total_cost or 0.0,
            }

            if include_metrics:
                input_tokens = int(total_tokens.get("input", 0) or 0)
                output_tokens = int(total_tokens.get("output", 0) or 0)
                by_role = no_of_tokens.get("by_role", {}) if isinstance(no_of_tokens.get("by_role", {}), dict) else {}
                llm_used = request_logs.get("llm_used")
                metrics_source = "request_logs"

                # Fallback for historical rows where token/time metadata was not fully persisted in request_logs.
                if input_tokens == 0 and output_tokens == 0:
                    fallback_rows = token_logs_by_file_id.get(record.processed_file_id, [])
                    if fallback_rows:
                        fallback_by_role = {"extractor": {}, "auditor": {}, "critic": {}}
                        fallback_input = 0
                        fallback_output = 0
                        models_seen = set()

                        for token_row in fallback_rows:
                            step = (token_row.step or "").lower()
                            if "auditor" in step:
                                role = "auditor"
                            elif "critic" in step:
                                role = "critic"
                            else:
                                role = "extractor"

                            model_name = token_row.model_name or "unknown-model"
                            models_seen.add(model_name)

                            if model_name not in fallback_by_role[role]:
                                fallback_by_role[role][model_name] = {"input": 0, "output": 0}

                            row_input = int(token_row.input_tokens or 0)
                            row_output = int(token_row.output_tokens or 0)
                            fallback_by_role[role][model_name]["input"] += row_input
                            fallback_by_role[role][model_name]["output"] += row_output
                            fallback_input += row_input
                            fallback_output += row_output

                        input_tokens = fallback_input
                        output_tokens = fallback_output
                        by_role = fallback_by_role
                        if not llm_used and models_seen:
                            llm_used = " | ".join(sorted(models_seen))
                        metrics_source = "token_logs_fallback"
                    else:
                        metrics_source = "none"

                response_item["request_logs_summary"] = {
                    "time_taken_to_process": request_logs.get("time_taken_to_process"),
                    "no_of_pages": request_logs.get("no_of_pages", 0),
                    "no_of_iterations": request_logs.get("no_of_iterations", 0),
                    "batches_processed": request_logs.get("batches_processed", 0),
                    "llm_used": llm_used,
                    "file_size": request_logs.get("file_size"),
                    "original_filename": request_logs.get("original_filename"),
                    "saved_filename": request_logs.get("saved_filename"),
                    "response_file": request_logs.get("response_file"),
                    "error": request_logs.get("error"),
                    "metrics_source": metrics_source,
                    "no_of_tokens": {
                        "total": {
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                        },
                        "by_role": by_role,
                    },
                    "cost": {
                        "total": record.total_cost or 0.0,
                        "currency": "USD",
                        "breakdown": request_logs.get("cost_breakdown") or record.cost_breakdown,
                    }
                }

            if include_raw_request_logs:
                response_item["request_logs"] = request_logs

            if include_raw_text:
                response_item["response_raw_text"] = record.final_response_raw_text or (
                    json.dumps(record.final_response, indent=2) if record.final_response else None
                )

            response_list.append(response_item)
        
        session.close()
        return {
            "page": page,
            "page_size": page_size,
            "total_records": total_rows,
            "total_responses": len(response_list),
            "responses": response_list
        }
    except Exception as e:
        logger.error(f"Error listing responses from DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/token-details")
async def list_token_details(
    include_raw_request_logs: bool = Query(True),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=500),
):
    """List token and runtime metrics sourced from processed_files.request_logs."""
    try:
        from db import db, ProcessedFile, DocumentFormat
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        session = db.get_session()

        base_query = session.query(ProcessedFile, DocumentFormat.short_name).\
            join(DocumentFormat, ProcessedFile.template_id == DocumentFormat.id, isouter=True)

        total_rows = base_query.count()
        if page and page_size:
            offset = (page - 1) * page_size
            results = base_query.order_by(ProcessedFile.date_time.desc()).offset(offset).limit(page_size).all()
        else:
            results = base_query.order_by(ProcessedFile.date_time.desc()).all()

        response_list = []
        for record, fmt_name in results:
            request_logs = record.request_logs if isinstance(record.request_logs, dict) else {}
            if not request_logs:
                continue

            no_of_tokens = request_logs.get("no_of_tokens", {}) if isinstance(request_logs.get("no_of_tokens", {}), dict) else {}
            total_tokens = no_of_tokens.get("total", {}) if isinstance(no_of_tokens.get("total", {}), dict) else {}
            input_tokens = int(total_tokens.get("input", 0) or 0)
            output_tokens = int(total_tokens.get("output", 0) or 0)

            item = {
                "processed_id": record.processed_file_id,
                "document_type": (fmt_name or "unknown").upper(),
                "timestamp": record.date_time.isoformat() if record.date_time else None,
                "status": request_logs.get("status", "unknown"),
                "request_id": request_logs.get("request_id", "N/A"),
                "pages": request_logs.get("no_of_pages", 0),
                "response_file": request_logs.get("response_file"),
                "request_logs_summary": {
                    "time_taken_to_process": request_logs.get("time_taken_to_process"),
                    "no_of_pages": request_logs.get("no_of_pages", 0),
                    "no_of_iterations": request_logs.get("no_of_iterations", 0),
                    "batches_processed": request_logs.get("batches_processed", 0),
                    "llm_used": request_logs.get("llm_used"),
                    "file_size": request_logs.get("file_size"),
                    "original_filename": request_logs.get("original_filename"),
                    "saved_filename": request_logs.get("saved_filename"),
                    "response_file": request_logs.get("response_file"),
                    "error": request_logs.get("error"),
                    "metrics_source": "request_logs",
                    "no_of_tokens": {
                        "total": {
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                        },
                        "by_role": no_of_tokens.get("by_role", {}),
                    },
                },
            }

            if include_raw_request_logs:
                item["request_logs"] = request_logs

            response_list.append(item)

        session.close()

        return {
            "page": page,
            "page_size": page_size,
            "total_records": total_rows,
            "total_responses": len(response_list),
            "responses": response_list,
        }
    except Exception as e:
        logger.error(f"Error listing token details from DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/knowledge")
async def list_learning_knowledge():
    """List learning knowledge records from Database"""
    try:
        from db import db, LearningKnowledge
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        session = db.get_session()
        records = session.query(LearningKnowledge).order_by(LearningKnowledge.updated_at.desc()).all()

        knowledge_items = []
        for record in records:
            knowledge_payload = {
                "id": record.id,
                "format_name": record.format_name,
                "lessons": record.lessons or [],
                "layout_patterns": record.layout_patterns or {},
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            }

            knowledge_items.append(
                {
                    **knowledge_payload,
                    "knowledge_raw_text": json.dumps(knowledge_payload, indent=2),
                }
            )

        session.close()
        return {
            "total_knowledge_records": len(knowledge_items),
            "knowledge": knowledge_items,
        }
    except Exception as e:
        logger.error(f"Error listing learning knowledge from DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/knowledge/{knowledge_id}")
async def update_learning_knowledge(knowledge_id: int, payload: KnowledgeUpdateRequest):
    """Update learning knowledge lessons and layout patterns for a template"""
    try:
        from db import db, LearningKnowledge
        from datetime import datetime
        lessons = payload.lessons
        layout_patterns = payload.layout_patterns
        
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")
        
        if lessons is None and layout_patterns is None:
            raise HTTPException(status_code=400, detail="At least one field (lessons or layout_patterns) must be provided")
        
        session = db.get_session()
        
        # Find the knowledge record
        record = session.query(LearningKnowledge).filter_by(id=knowledge_id).first()
        if not record:
            session.close()
            raise HTTPException(status_code=404, detail=f"Knowledge record with ID {knowledge_id} not found")
        
        # Update fields
        if lessons is not None:
            record.lessons = lessons
        if layout_patterns is not None:
            record.layout_patterns = layout_patterns
        
        record.updated_at = datetime.utcnow()
        session.commit()
        
        log_db_operation("UPDATE", "LearningKnowledge", "Success", f"ID {knowledge_id}")
        logger.info(f"Updated knowledge record ID {knowledge_id} for {record.format_name}")
        
        # Prepare response
        updated_payload = {
            "id": record.id,
            "format_name": record.format_name,
            "lessons": record.lessons or [],
            "layout_patterns": record.layout_patterns or {},
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
        
        session.close()
        
        return {
            "status": "success",
            "message": f"Knowledge record {knowledge_id} updated successfully",
            "knowledge": updated_payload,
            "knowledge_raw_text": json.dumps(updated_payload, indent=2)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating knowledge record {knowledge_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/response/{processed_id}")
async def get_response(
    processed_id: int,
    wait_for_completion: bool = Query(True),
    timeout_seconds: Optional[int] = Query(None, ge=1, le=1800),
    poll_interval_seconds: float = Query(2.0, ge=0.5, le=10.0),
):
    """Get final response by Processed ID; optionally wait until extraction completes."""
    try:
        from db import db, ProcessedFile
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        start_time = time.time()

        while True:
            session = db.get_session()
            try:
                record = session.query(ProcessedFile).get(processed_id)
            finally:
                session.close()

            if not record:
                raise HTTPException(status_code=404, detail="Job not found")

            status = record.request_logs.get("status") if isinstance(record.request_logs, dict) else "unknown"

            if status == "failed":
                return {
                    "status": "failed",
                    "processed_id": processed_id,
                    "error": record.request_logs.get("error") if isinstance(record.request_logs, dict) else "Unknown error",
                }

            # Return as soon as final output exists, even if status propagation lags.
            if record.final_response:
                raw_text = record.final_response_raw_text or json.dumps(record.final_response, indent=2)
                try:
                    return JSONResponse(content=json.loads(raw_text))
                except Exception:
                    return JSONResponse(content={"response_raw_text": raw_text})

            if not wait_for_completion:
                return {
                    "status": "processing",
                    "processed_id": processed_id,
                    "message": "The AI is still extracting data. Please retry shortly.",
                }

            if timeout_seconds is not None and (time.time() - start_time) >= timeout_seconds:
                return {
                    "status": "processing",
                    "processed_id": processed_id,
                    "message": f"Still processing after {timeout_seconds} seconds. Retry this endpoint.",
                }

            await asyncio.sleep(poll_interval_seconds)
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
    response_json_schema = format_components.get("response_json_schema", "")
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


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
