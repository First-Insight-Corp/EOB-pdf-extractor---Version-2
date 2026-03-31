import google.generativeai as genai
from openai import OpenAI
from typing import List, Dict, Any, Optional, Union
import json
import logging
from pydantic import ValidationError, BaseModel
from config import config
from format_loader import FormatLoader
from agents.base_extraction_agent import BaseExtractionAgent
from agents.memory import GlobalLearningMemory
from logs_config import get_extraction_logger

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)

logger = get_extraction_logger()

class MultiModelAgent(BaseExtractionAgent):
    """
    Gemini-based extraction agent. Also supports Auditor/Critic loop and Pydantic validation.
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro", openai_api_key: str = None):
        """
        Initialize the multi-model agent.
        """
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        
        self.openai_key = openai_api_key or config.OPENAI_API_KEY
        self.openai_client = None
        if self.openai_key and self.openai_key != "YOUR_OPENAI_API_KEY":
            self.openai_client = OpenAI(api_key=self.openai_key)
            
        self.conversation_history = []
        self.extracted_claims = []
        self.processing_context = {}
        self.learning_memory = GlobalLearningMemory()
        logger.info(f"Initialized Multi-Model Agent with Gemini ({model_name}) and OpenAI ({config.OPENAI_MODEL if self.openai_client else 'None'})")
    
    def reset_memory(self, keep_learning: bool = True):
        """Reset agent memory for new task. optionally keep learned lessons."""
        self.conversation_history = []
        self.extracted_claims = []
        self.processing_context = {}
        if not keep_learning:
            self.learning_memory = GlobalLearningMemory()
        logger.info(f"Agent memory reset for new task (keep_learning={keep_learning})")
    
    def load_memory(self, format_name: str):
        self.learning_memory.load(format_name)
        
    def save_memory(self, format_name: str):
        self.learning_memory.save(format_name)
    
    def add_to_memory(self, role: str, content: str):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        logger.info(f"Added {role} message to memory (total: {len(self.conversation_history)})")
    
    def get_learning_context(self) -> str:
        return self.learning_memory.get_context_injection()

    def extract_batch(
        self,
        document_type: str,
        batch_text: str,
        schema_description: str,
        batch_json_schema: str = "",
        response_json_schema: str = "",
        image_b64_list: List[str] = None,
        is_continuation: bool = False,
        previous_context: str = "",
        improvement_instructions: Optional[str] = None,
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """BaseExtractionAgent interface: single extraction pass (no internal Auditor loop)."""
        result = self.extract_claims_from_batch(
            document_type=document_type,
            batch_content=batch_text,
            schema_description=schema_description,
            json_schema=batch_json_schema,
            response_json_schema=response_json_schema,
            image_b64_list=image_b64_list,
            is_continuation=is_continuation,
            previous_context=previous_context,
            improvement_instructions=improvement_instructions,
            previous_batch_text=previous_batch_text,
            previous_batch_json=previous_batch_json,
        )
        if "entities" in result and "claims" not in result:
            result["claims"] = result["entities"]
        return result

    def build_extraction_prompt(
        self, 
        document_type: str, 
        page_content: str,
        schema_description: str,
        json_schema: str = "",
        response_json_schema: str = "",
        is_continuation: bool = False,
        previous_context: str = "",
        improvement_instructions: Optional[str] = None,
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build comprehensive extraction prompt for Gemini.
        """
        
        continuation_instruction = ""
        if is_continuation:
            continuation_instruction = f"""
### CONTINUATION CONTEXT
IMPORTANT: This is a CONTINUATION of previous pages.

PENDING CONTEXT FROM PREVIOUS BATCH:
{previous_context}

CRITICAL INSTRUCTIONS FOR CONTINUATION:
1. THE FIRST ENTITY ON THIS PAGE MIGHT BE THE CONTINUATION OF THE LAST ENTITY FROM PREVIOUS PAGES.
2. Use the "PENDING CONTEXT" provided above to complete that entity.
3. If an entity is continued, do NOT create a new entry; MERGE the data into the existing entity structure using the same identifier/ID.
4. If the first entity on this page is NOT a continuation (e.g., it has its own header info), treat it as a new entity.
"""
        
        prompt = f"""You are an advanced AI specialized in 100% accurate industrial data extraction from complex medical remittance PDFs.
You have been provided with both IMAGES and OCR TEXT of the document pages.

### EXTRACTION PHILOSOPHY:
*   **ZERO DATA LOSS**: You must not skip a single character, line, or field present in the document.
*   **VISUAL-FIRST LOGIC**: The visual layout (lines, boxes, spacing) defines the hierarchy. The text content provides the values.
*   **STRUCTURAL RIGOR**: Every "Parent" entity (Claim/Patient) contains 1 or more "Child" entities (Service Lines). Never mix child items between different parents.

### STRUCTURAL HIERARCHY ANALYSIS:
1.  **IDENTIFY PARENT BLOCKS**: Scan the document for "Anchor Headers" (e.g., Patient Name, ID, Claim Number). These define the start of a new data block.
2.  **DETERMINE BOUNDARIES**: A block ends only when a new "Anchor Header" or a "Block Total" is encountered.
3.  **HIEARCHICAL NESTING**: All service lines, procedure codes, and amounts occurring between two Anchor Headers MUST be nested inside the *first* Anchor Header's object.

### VISUAL SCANNING RULES:
1.  **FULL-WIDTH SCAN**: For every row, scan from the extreme left margin to the extreme right margin. Do not ignore fields near the edges (e.g., "Message Codes" or "Modifiers").
2.  **MULTI-LINE RESOLUTION**: If a description or field spans multiple physical lines, concatenate them into a single string. Use visual vertical alignment to determine if text belongs to the same row.
3.  **TABLE GRID RECONSTRUCTION**: Mentally reconstruct the table grid. If a column is empty for one row but has values in others, ensure the alignment is maintained.
4.  **ASSOCIATIVE HEADERS**: Look at the text *above* or *to the left* of a value to confirm its field name (e.g., a "Units" field might be a small number directly left of a "Description").

### DATA INTEGRITY RULES:
1.  **ZERO-VALUE PERSISTENCE**: If a numeric field shows "0.00", "$0.00", or "0" in the document, you MUST return `0.0`. DO NOT return `null`. Every financial field in the schema that has a value must be populated.
2.  **CODE DELIMITERS**: Separate multiple codes in one cell with SPACES.
3.  **MERGE ENFORCEMENT**: If "PENDING CONTEXT" is provided, the VERY FIRST entity on the current page is likely a continuation. MERGE it into `partial_data`.
4.  **INHERITANCE**: Block-level fields apply to all items in that block until a new value is found.
5.  **LOGICAL ATTRIBUTE MATCHING**: When you encounter a row that summarizes a block or a document header, explicitly search the schema for the corresponding summary fields and map the values there. Do not just append summary rows to the main item list.

### TARGET DATA SCHEMAS:
1. **ENTITY SCHEMA** (For items in the 'entities' list):
{json_schema}

2. **RESPONSE/METADATA SCHEMA** (For global fields in the 'metadata' object):
{response_json_schema}

### DOCUMENT-SPECIFIC RULES:
{schema_description}

{self.learning_memory.get_context_injection()}

{continuation_instruction}
{f'''
### PREVIOUS BATCH CONTEXT (for data consistency)
To keep field names, structure, and formatting consistent across the document, use the following from the **immediately previous batch** as reference. Match the same key names, number formats, and nesting. Do not contradict or duplicate data that was already extracted in the previous batch.

**Previous batch text (end of previous pages):**
{previous_batch_text[-4000:] if previous_batch_text and len(previous_batch_text) > 4000 else (previous_batch_text or "")}

**Previous batch extracted JSON (structure and style to match):**
{json.dumps(previous_batch_json, indent=2, cls=SetEncoder) if previous_batch_json else "{}"}
''' if (previous_batch_text or previous_batch_json) else ""}
{f'''
### CRITICAL: IMPROVEMENT INSTRUCTIONS (from Auditor/Critic)
You must fix these issues in this re-extraction:
{improvement_instructions}
''' if improvement_instructions else ''}

RETURN FORMAT:
Return a valid JSON object matching the requested schema. Ensure 100% field coverage.

PAGE TEXT CONTENT (Character Reference):
{page_content}

Return your response in the following JSON format:
{{
    "entities_found": <total count of main data blocks processed>,
    "entities": [
        <array of structured objects matching the ENTITY SCHEMA provided above>
    ],
    "metadata": {{
        <key-value pairs matching the metadata fields in the RESPONSE/METADATA SCHEMA provided above. Include summary values and specialized tables here.>
    }},
    "has_incomplete_entity": <true/false - if the very last line of the batch is a partial object that continues into the next page>,
    "incomplete_entity_context": {{
        "entity_identifier": "<unique ID for merging>",
        "name": "<name for merging>",
        "partial_data": "<JSON object of extracted parts to enable seamless merging>"
    }},
    "processing_notes": "<summary of how structural hierarchy and layout transitions were resolved on these pages. Mention if specific fields were challenging to locate.>"
}}

RESPOND ONLY WITH VALID JSON. NO PREAMBLE. NO POST-TEXT.
"""
        return prompt
    
    def extract_claims_from_batch(
        self,
        document_type: str,
        batch_content: str,
        schema_description: str,
        json_schema: str = "",
        response_json_schema: str = "",
        image_b64_list: List[str] = None,
        is_continuation: bool = False,
        previous_context: str = "",
        improvement_instructions: Optional[str] = None,
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract claims from a batch of pages using text and optional images.
        Includes retry logic for robustness.
        """
        import time
        max_retries = 3
        retry_delay = 2
        
        last_error = None
        for attempt in range(max_retries):
            try:
                prompt = self.build_extraction_prompt(
                    document_type,
                    batch_content,
                    schema_description,
                    json_schema,
                    response_json_schema,
                    is_continuation,
                    previous_context,
                    improvement_instructions,
                    previous_batch_text,
                    previous_batch_json,
                )
                
                self.add_to_memory("user", f"Extract claims from batch. Continuation: {is_continuation} (Attempt {attempt+1})")
                
                # Prepare multimodal parts
                parts = [prompt]
                if image_b64_list:
                    import base64
                    for img_b64 in image_b64_list:
                        parts.append({
                            "mime_type": "image/png",
                            "data": base64.b64decode(img_b64)
                        })
                
                logger.info(f"Sending batch to Gemini (Attempt {attempt+1}/{max_retries})")
                
                response = self.model.generate_content(parts)
                response_text = response.text
                
                # Capture token usage
                usage_metadata = {
                    "model_name": self.model_name
                }
                try:
                    usage = response.usage_metadata
                    usage_metadata.update({
                        "input_tokens": usage.prompt_token_count,
                        "output_tokens": usage.candidates_token_count,
                        "total_tokens": usage.total_token_count
                    })
                except AttributeError:
                    logger.warning("Gemini response missing usage_metadata")
                
                self.add_to_memory("assistant", response_text[:500] + "...")
                
                result = json.loads(response_text)
                
                # Include usage metadata in result
                result["usage_metadata"] = usage_metadata
                
                # Update processing context (handle both generic and legacy keys)
                has_incomplete = result.get('has_incomplete_entity', result.get('has_incomplete_claim', False))
                if has_incomplete:
                    self.processing_context['incomplete_claim_context'] = result.get('incomplete_entity_context', result.get('incomplete_claim_context', {}))
                else:
                    self.processing_context['incomplete_claim_context'] = None
                    
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Batch extraction attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        
        logger.error(f"All {max_retries} attempts failed for batch extraction")
        raise last_error

    def executive_react_extraction(
        self,
        document_type: str,
        batch_text: str,
        schema_description: str,
        json_schema: str,
        response_json_schema: str,
        image_b64_list: List[str] = None,
        is_continuation: bool = False,
        previous_context: str = "",
        is_last_batch: bool = False,
        max_internal_loops: int = 3
    ) -> Dict[str, Any]:
        """
        Ultimate High-Intelligence Extraction Loop.
        Implements a Thought -> Action -> Audit -> Correction cycle.
        """
        logger.info("Initializing Ultimate Executive ReAct Loop...")
        
        # 1. INITIAL EXTRACTION (ACTION)
        result = self.extract_claims_from_batch(
            document_type=document_type,
            batch_content=batch_text,
            schema_description=schema_description,
            json_schema=json_schema,
            response_json_schema=response_json_schema,
            image_b64_list=image_b64_list,
            is_continuation=is_continuation,
            previous_context=previous_context
        )
        
        # 2. ITERATIVE AUDIT & REASONING (REACTION)
        loop_count = 0
        while loop_count < max_internal_loops:
            logger.info(f"ReAct Loop {loop_count + 1}/{max_internal_loops}: Auditing Extraction...")
            
            issues = self.agent_verify_extraction(
                extracted_result=result,
                batch_content=batch_text,
                schema_description=schema_description,
                image_b64_list=image_b64_list,
                is_last_batch=is_last_batch
            )
            
            if not issues:
                logger.info("ReAct Loop: 100% Accuracy Verified by Auditor.")
                break
                
            logger.warning(f"ReAct Loop: Auditor identified {len(issues)} issues. Triggering Self-Correction...")
            
            # 3. SELF-CORRECTION (ADAPTATION)
            refined_result = self.refine_extraction(
                original_result=result,
                issues=issues,
                batch_content=batch_text,
                json_schema=json_schema,
                response_json_schema=response_json_schema,
                schema_description=schema_description,
                image_b64_list=image_b64_list
            )
            
            # 4. MERGE & RE-AUDIT
            result = self.merge_results(result, refined_result)
            
            # 5. UPDATE PERSISTENT STATE (Memory)
            # Find latest doctor to persist across page boundaries
            entities = result.get('entities', result.get('claims', []))
            if entities:
                for entity in reversed(entities):
                    if entity.get('treating_doctor'):
                        self.learning_memory.active_state['current_doctor'] = entity['treating_doctor']
                        break
            
            loop_count += 1
            
        if loop_count == max_internal_loops and issues:
            logger.warning("ReAct Loop: Maximum loops reached. Returning highest-confidence result.")
            
        return result

    def process_full_document(
        self,
        document_type: str,
        page_batches: List[Dict[str, Any]],
        schema_description: str
    ) -> List[Dict[str, Any]]:
        """
        Process entire document.
        page_batches should now be a list of dicts: {'text': str, 'images': List[str]}
        """
        all_claims = []
        previous_context = ""
        
        logger.info(f"Processing {len(page_batches)} batches for {document_type}")
        
        for batch_idx, batch in enumerate(page_batches):
            logger.info(f"--- Batch {batch_idx + 1}/{len(page_batches)} ---")
            
            is_continuation = batch_idx > 0 and bool(previous_context)
            
            result = self.extract_claims_from_batch(
                document_type=document_type,
                batch_content=batch['text'],
                schema_description=schema_description,
                image_b64_list=batch.get('images', []),
                is_continuation=is_continuation,
                previous_context=previous_context
            )
            
            # Extract result from the batch_result (assuming it might be nested)
            # If result is already the direct JSON, this will just return it.
            extracted_data = result.get('vsp_remittance_page', result)
            entities = extracted_data.get('entities', extracted_data.get('claims', []))
            metadata = extracted_data.get('metadata', {})
            
            # --- CONTEXT MANAGEMENT FOR NEXT BATCH ---
            # 1. Incomplete Claim Context (Standard)
            has_incomplete = result.get('has_incomplete_entity', result.get('has_incomplete_claim', False))
            if has_incomplete:
                previous_context = result.get('incomplete_entity_context', result.get('incomplete_claim_context', ""))
            else:
                previous_context = ""

            # 2. Persistent Doctor Context (New Fix)
            # Find the last doctor mentioned in this batch to pass to the next
            last_doctor = None
            if entities:
                # Look at the last few claims to find a doctor
                for claim in reversed(entities):
                    if claim.get('treating_doctor'):
                        last_doctor = claim.get('treating_doctor')
                        break
            
            if last_doctor:
                # Append to previous_context or create new context
                doctor_context = f" [PREVIOUS_BATCH_CONTEXT: The last active treating doctor was '{last_doctor}'. If no new doctor is explicitly named on the new page, continue using '{last_doctor}'.]"
                previous_context += doctor_context
                logger.info(f"Passing persistent doctor context to next batch: {last_doctor}")

            # Merge entities
            all_claims.extend(entities)
            logger.info(f"Batch {batch_idx + 1}: Extracted {len(entities)} items")
                
        logger.info(f"Total items extracted: {len(all_claims)}")
        return all_claims

    def agent_verify_extraction(
        self, 
        extracted_result: Dict[str, Any], 
        batch_content: str,
        schema_description: str,
        image_b64_list: List[str] = None,
        is_last_batch: bool = False
    ) -> List[str]:
        """
        Use Gemini as a Quality Auditor to dynamically verify the extraction 
        against the source PDF (text and images).
        """
        logger.info("Starting Dynamic Agent-Based Verification...")
        
        audit_prompt = f"""
You are a High-Precision Medical Claims Quality Auditor. 
Your task is to compare a JSON extraction against the source PDF (Text & Images) and identify ANY discrepancies, missing data, or errors.

### SCHEMA RULES & EXPECTATIONS:
{schema_description}

### SOURCE CONTENT (TEXT):
{batch_content}

### EXTRACTION TO AUDIT (JSON):
{json.dumps(extracted_result, indent=2, cls=SetEncoder)}

### AUDIT INSTRUCTIONS:
1. **Multimodal Cross-Check**: Compare the JSON fields against the visual evidence in the images and the OCR text.
2. **Missing Entities**: Did the extraction skip any patient names, claims, or service lines visible in the document?
3. **Data Accuracy**: Are fields like `service_date`, `procedure_code`, `billed_amount`, and `patient_account_number` 100% accurate?
4. **MANDATORY HEADER CHECK (Page 1)**: You MUST verify `check_number`, `check_date`, and `practice_name`. If these are `null` in the JSON but visible on the first page, flag as 'MISSING_DOCUMENT_HEADER'.
5. **Is Last Batch**: {f"CRITICAL: This is the LAST PAGE. Search specifically for the 'In-Office Finishing' (IOF) table AND the 'Total VSP Check' amount (e.g., $1,182.50)." if is_last_batch else "Ensure all data on these pages is captured."}
6. **Procedure Codes**: Verify that `procedure_code` (e.g., V2781, 92014) is captured for every line item.
7. **Zero Tolerance for Nulls**: If `claim_totals` is null for any claim, or if `patient_account_number` is missing, flag it as a CRITICAL_ERROR.
8. **Doctor Continuity**: If a doctor was active on the previous page and is not restated here, ensure the extraction continues to use that doctor. If it's missing, flag it.

### RETURN FORMAT:
Return a JSON object with two keys:
1. `issues`: A list of strings. Each string SHOULD include a "Proof of Evidence" (e.g., "The claim for Jane Doe on page 2 row 4 has billed amount $100 but extracted as $10").
2. `lessons`: A list of strings representing ADAPTIVE LESSONS (e.g., "The Account Number is always located 2 lines below the Patient Name in a small font"). These will be used to improve future batches.

If 100% accurate and no new lessons identified, return: {{"issues": [], "lessons": []}}.

Example Output:
{{
  "issues": ["Missing service date for SMITH, JOHN (Visible on Page 1 above Service Description)"],
  "lessons": ["The Doctor name is inherited from the blue header row at the top of each claim block."]
}}

RESPOND ONLY WITH VALID JSON.
"""
        try:
            parts = [audit_prompt]
            if image_b64_list:
                import base64
                for img_b64 in image_b64_list:
                    parts.append({
                        "mime_type": "image/png",
                        "data": base64.b64decode(img_b64)
                    })
            
            response = self.model.generate_content(parts)
            response_text = response.text.strip()
            
            # Clean JSON formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[-1].split("```")[0].strip()
            
            audit_result = json.loads(response_text)
            
            # Auditor now returns a dict: {"issues": [], "lessons": []}
            if isinstance(audit_result, list):
                # Backwards compatibility
                audit_result = {"issues": audit_result, "lessons": []}
            
            issues = audit_result.get('issues', [])
            lessons = audit_result.get('lessons', [])
            
            # Record lessons and failures in Global Memory
            for lesson in lessons:
                self.learning_memory.add_lesson(lesson)
            
            for issue in issues:
                # Ensure issue is a string for analysis
                issue_text = str(issue)
                if isinstance(issue, dict):
                    # Try to extract a description or similar field if it's a dict
                    issue_text = issue.get('description', issue.get('issue', str(issue)))
                
                # Extract field name from issue description if possible (e.g. "service_date missing")
                for field in ['service_date', 'procedure_code', 'check_number', 'patient_account_number']:
                    if field in issue_text.lower():
                        self.learning_memory.record_failure(field)
            
            logger.info(f"Dynamic Audit complete. Found {len(issues)} issues and {len(lessons)} new lessons.")
            return issues
            
        except Exception as e:
            logger.error(f"Dynamic Verification failed: {e}")
            return [] # Fallback to empty if verification itself fails

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of current memory state"""
        return {
            "conversation_turns": len(self.conversation_history),
            "claims_in_memory": len(self.extracted_claims),
            "processing_context": self.processing_context
        }

    def verify_extraction(self, result: Dict[str, Any], page_numbers: List[int], is_last_batch: bool = False) -> List[str]:
        """
        Verify the extracted data against structural and logical rules.
        Returns a list of issue descriptions (if any).
        """
        issues = []
        entities = result.get('entities', [])
        metadata = result.get('metadata', {})
        
        # 1. IOF Integrity Check (Dynamic Last Page Detection)
        # Trigger only for the end of document
        if is_last_batch:
            iof_data = metadata.get('in_office_finishing', [])
            if not iof_data:
                # We mention explicitly to search for the header in the refinement prompt later
                issues.append("MISSING_IOF_DATA: This is the last batch, but no In-Office Finishing table was extracted.")
        
        if not entities:
            return issues

        # 2. Global Null Check & Pattern Validation
        field_stats = {}
        total_claims = len(entities)
        claims_with_no_services = 0
        
        for entity in entities:
            # Check for null fields
            for key, value in entity.items():
                if value is None:
                    field_stats[key] = field_stats.get(key, 0) + 1
            
            # Check for Empty Services
            services = entity.get('services', [])
            if not services:
                claims_with_no_services += 1

            # Pattern Validation: Patient Account Number
            acct_num = entity.get('patient_account_number')
            if acct_num:
                 # Clean up non-numeric formatting if any
                 clean_acct = str(acct_num).replace('-', '').replace(' ', '')
                 if not clean_acct.isdigit():
                     # Log only if completely non-numeric
                     pass

        # Flag fields with > 40% null rate (excluding optional ones like modifiers)
        critical_fields = ['treating_doctor', 'patient_name', 'insured_id']
        for field in critical_fields:
            null_count = field_stats.get(field, 0)
            if null_count / total_claims > 0.4:
                 issues.append(f"HIGH_NULL_RATE_{field.upper()}: {field} is missing in {null_count}/{total_claims} claims.")

        # STRICTER CHECK FOR SERVICE DATE (Threshold 0.0 - Zero Tolerance)
        sd_null = field_stats.get('service_date', 0)
        if sd_null > 0:
             issues.append(f"HIGH_NULL_RATE_SERVICE_DATE: service_date is missing in {sd_null}/{total_claims} claims.")

        # Check for widespread empty services
        if claims_with_no_services / total_claims > 0.1:
            issues.append(f"EMPTY_SERVICES: {claims_with_no_services}/{total_claims} claims have 0 service lines.")

        # 3. Account Number Integrity
        null_acct = field_stats.get('patient_account_number', 0)
        if null_acct / total_claims > 0.4:
            issues.append(f"MISSING_ACCOUNT_NUMBERS: patient_account_number missing in {null_acct}/{total_claims} claims.")

        # 4. Claim Number Duplication Check
        claim_nums = [e.get('claim_number') for e in entities if e.get('claim_number')]
        if claim_nums:
            duplicates = len(claim_nums) - len(set(claim_nums))
            if duplicates / len(claim_nums) > 0.5:
                 issues.append(f"DUPLICATE_CLAIM_NUMBERS: High duplication rate detected in claim_number.")

        return issues

    def refine_extraction(
        self, 
        original_result: Dict[str, Any], 
        issues: List[str],
        batch_content: str,
        json_schema: str = "",
        response_json_schema: str = "",
        schema_description: str = "",
        image_b64_list: List[str] = None
    ) -> Dict[str, Any]:
        """
        Send a targeted repair prompt to fix specific verification issues.
        """
        logger.info(f"Starting Self-Correction for issues: {issues}")
        
        # specific instructions based on issues
        repair_instructions = []
        if any("MISSING_DOCUMENT_HEADER" in i for i in issues):
            repair_instructions.append("- **MISSING DOCUMENT HEADER**: The `check_number`, `check_date`, and `practice_name` are missing. These are located at the VERY TOP of the first page. Locate them and map them correctly to the metadata object.")

        if any("MISSING_IOF_DATA" in i for i in issues):
            repair_instructions.append("- **MISSING IOF TABLE**: Navigate to the **LAST PAGE** of the PDF. Explicitly search for the table with header **'In-Office Finishing'** (or 'IOF'). Extract this table **COMPLETELY** into `metadata.in_office_finishing`.")
        
        if any("MISSING_ACCOUNT_NUMBERS" in i for i in issues):
            repair_instructions.append("- **MISSING ACCOUNT NUMBERS**: You missed the patient account number for many claims. Look vertically BELOW the Patient Name line. The number immediately below the name is the Account Number. It can be SHORT (5 digits) or LONG (10 digits). Do not filter by length.")
        
        if any("HIGH_NULL_RATE_TREATING_DOCTOR" in i for i in issues):
            repair_instructions.append("- **MISSING DOCTOR**: The Doctor's name appears at the top of the page OR at the start of a claim block. You **MUST** apply this name to every claim listed below it until a NEW 'Doctor:' header appears.")

        if any("HIGH_NULL_RATE_SERVICE_DATE" in i for i in issues):
            repair_instructions.append("- **MISSING SERVICE DATES**: The Service Date is often found in the **FIRST ROW** of the service table (left side). If missing there, check the **SECOND ROW** or the **HEADER LINE** immediately above the table. Extract this date and apply it to the `service_date` field for the entire claim block.")

        if any("EMPTY_SERVICES" in i for i in issues):
            repair_instructions.append("- **MISSING SERVICE LINES**: You found the patients but returned 0 service lines! The service lines are the rows BETWEEN the Claim Number (Identifier) and the Totals row. Look for CPT codes (e.g., 92014, V2100) and dollar amounts. EXTRACT EVERY ROW as a service item.")

        if not repair_instructions:
             repair_instructions.append("- Review the extracted data and fix any missing or null fields based on the document content.")

        repair_prompt = f"""
You are refining a previous extraction that had errors. Your goal is 100% accuracy.

### TARGET DATA SCHEMAS (REQUIRED):
1. **ENTITY SCHEMA**:
{json_schema}

2. **RESPONSE/METADATA SCHEMA**:
{response_json_schema}

### DOCUMENT-SPECIFIC RULES:
{schema_description}

### CRITIQUE & FEEDBACK FROM QUALITY ANALYZER:
I have analyzed your previous extraction and found several CRITICAL data integrity errors. You MUST fix these while preserving all other correct data.

**IDENTIFIED FAILURES:**
{chr(10).join(repair_instructions)}

**TASK:**
1. Re-examine the provided text AND images with specific focus on these failures.
2. Provide a **NEW, COMPLETE, AND CORRECTED JSON RESPONSE** that follows the schemas perfectly.
3. **DO NOT LOSE DATA**: Ensure all fields like `procedure_code`, `service_date`, `check_date`, and `practice_name` are populated correctly according to the document.
4. If a field was correct in the original extraction, keep it. If it was missing or wrong, FIX IT.

RETURN ONLY THE CORRECTED VALID JSON. NO PREAMBLE.
"""
        
        # Prepare multimodal content for refinement
        parts = [f"ORIGINAL CONTENT:\n{batch_content}", repair_prompt]
        if image_b64_list:
            import base64
            for img_b64 in image_b64_list:
                parts.append({
                    "mime_type": "image/png",
                    "data": base64.b64decode(img_b64)
                })
        
        try:
             logger.info(f"Sending critique to model for batch refinement...")
             response = self.model.generate_content(parts)
             response_text = response.text.strip()
             
             # Clean up JSON formatting
             if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0].strip()
             elif "```" in response_text:
                response_text = response_text.split("```")[-1].split("```")[0].strip()
             
             refined_json = json.loads(response_text)
             logger.info(f"Critique-driven refinement successful. Merging results...")
             return refined_json
             
        except Exception as e:
            logger.error(f"Refinement failed during critique loop: {e}")
            return original_result # Fallback to original if repair fails

    def merge_results(self, original: Dict[str, Any], refined: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge refined data into original result.
        Prioritize refined data if it has more items or fewer nulls.
        """
        merged = original.copy()
        
        # 1. Merge Metadata (IOF check)
        orig_meta = original.get('metadata', {})
        ref_meta = refined.get('metadata', {})
        
        if len(ref_meta.get('in_office_finishing', [])) > len(orig_meta.get('in_office_finishing', [])):
            merged['metadata'] = ref_meta
            logger.info("Merged refined metadata (IOF found)")
        
        # 2. Merge Entities
        # Simple strategy: if refined has more entities, take it. 
        # Or if refined has fewer null account numbers, take it.
        orig_entities = original.get('entities', [])
        ref_entities = refined.get('entities', [])
        
        if len(ref_entities) >= len(orig_entities):
             # check quality
             orig_nulls = sum(1 for e in orig_entities if not e.get('patient_account_number'))
             ref_nulls = sum(1 for e in ref_entities if not e.get('patient_account_number'))
             
             if ref_nulls < orig_nulls:
                 merged['entities'] = ref_entities
                 logger.info(f"Merged refined entities (Improved Acct# coverage: {orig_nulls} -> {ref_nulls} nulls)")
        
        return merged

    def gpt4_extraction(self, prompt: str, system_prompt: str = "") -> str:
        """
        Secondary extraction using GPT-4o for majority voting.
        """
        if not self.openai_client:
            logger.warning("OpenAI client not configured. Skipping GPT-4 extraction.")
            return ""

        try:
            logger.info("Requesting GPT-4o for cross-validation...")
            response = self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt or "You are an expert medical data extractor. Return JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT-4 extraction failed: {e}")
            return ""

    def majority_vote(self, results: List[Dict[str, Any]], critical_fields: List[str]) -> Dict[str, Any]:
        """
        Implementation of Majority Voting (Gemini + GPT-4).
        If both disagree on a critical field, flags it for the Critic.
        """
        if len(results) < 2:
            return results[0] if results else {}

        winner = results[0].copy() # Default to Gemini
        gemini_res = results[0]
        gpt4_res = results[1]

        # Simplified voting: if GPT-4 found something Gemini missed in critical fields, prefer GPT-4
        # or if they both found it, compare values.
        # This is a 'soft' version of majority voting since we have 2 models.
        # If we had 3 (Claude), it would be traditional majority.
        
        logger.info(f"Performing Multi-Model Validation on {len(critical_fields)} fields...")
        
        g_entities = gemini_res.get('entities', gemini_res.get('claims', []))
        o_entities = gpt4_res.get('entities', gpt4_res.get('claims', []))

        # Direct entity-by-entity comparison is complex if indices don't match.
        # For now, we use GPT-4 to 'witness' and 'verify' claim numbers.
        return winner # placeholder for more complex logic

    def pydantic_validator_critic(
        self, 
        data: Dict[str, Any], 
        model_class: Any,
        batch_content: str,
        max_retries: int = 4
    ) -> Dict[str, Any]:
        """
        Pydantic Validator + Critic Agent loop.
        Retries up to 4 times with progressive strategies.
        """
        retries = 0
        current_data = data
        
        while retries < max_retries:
            try:
                # 1. Pydantic Validator
                validated_model = model_class.model_validate(current_data)
                logger.info(f"Pydantic Validation PASSED on attempt {retries + 1}")
                return validated_model.model_dump()
            except ValidationError as e:
                retries += 1
                logger.warning(f"Pydantic Validation FAILED on attempt {retries}: {e}")
                
                if retries >= max_retries:
                    logger.error("Max retries reached for Critic Agent. Returning last known state.")
                    return current_data

                # 2. Critic Agent (Action)
                # Progressive strategies: 
                # 1. Show raw error 
                # 2. Add 'formatting rules'
                # 3. Request field-level focus
                errors = e.errors()
                error_summary = "\n".join([f"- {err['loc']}: {err['msg']}" for err in errors])
                
                logger.info(f"Critic Agent triggering retry {retries} with strategy: Error-Correction")
                
                correction_prompt = f"""
The previous extraction failed Pydantic validation. You must fix these specific errors:
{error_summary}

Original Content Context:
{batch_content[:2000]}...

Ensure the output is 100% valid JSON matching the schema.
"""
                # Use Gemini as the Critic for now
                correction_res = self.model.generate_content(correction_prompt)
                try:
                    res_text = correction_res.text.strip()
                    if "```json" in res_text:
                        res_text = res_text.split("```json")[-1].split("```")[0].strip()
                    current_data = json.loads(res_text)
                except:
                    logger.error("Critic Agent failed to parse corrected JSON. Retrying...")
                    continue
        
        return current_data
