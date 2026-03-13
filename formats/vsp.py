from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator

class ServiceLineItem(BaseModel):
    """
    Represents an individual line item for a medical service or material.
    """
    
    procedure_code: Optional[str] = Field(
        None, 
        description="The CPT/HCPCS code (e.g., 'V2520', '92014'). If the row describes an enhancement/coverage but has no code, leave as null."
    )
    units: Optional[int] = Field(
        None, 
        description="Number of units (e.g., '1', '12'). Usually appears immediately to the left of the Description text."
    )
    description: Optional[str] = Field(
        None, 
        description="The full text description of the service (e.g., '12 Contact Lenses', 'Exam - Comp'). Capture the complete string."
    )
    modifiers: Optional[str] = Field(
        None, 
        description="Any 2 or 3 character modifiers like 'Rev', 'RT', or 'LT' associated with the procedure."
    )
    billed_amount: Optional[float] = Field(
        None, 
        description="Value from the 'Billed Amount' column. Ensure negative signs are captured for reversals."
    )
    total_compensation: Optional[float] = Field(
        None, 
        description="Value from the 'Total Compensation' column."
    )
    copay: Optional[float] = Field(
        None, 
        description="Value from the 'CoPay' column. Represents patient responsibility."
    )
    patient_pay: Optional[float] = Field(
        None, 
        description="Value from the 'Patient Pay Materials' column."
    )
    plan_provided_materials: Optional[float] = Field(
        None, 
        description="Value from the 'Plan Provided Materials' column. Explicitly capture '0.00' as a float."
    )
    provider_payment: Optional[float] = Field(
        None, 
        description="Value from the 'Provider Payment' column. This is the actual amount VSP is paying the provider."
    )
    message_codes: Optional[str] = Field(
        None, 
        description="All alphanumeric codes (e.g., '1C', '7K', 'OP') found in the far-right column. Separate multiple codes with a space."
    )

    @field_validator("modifiers", "message_codes", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v

class Claim(BaseModel):
    """
    Represents a full claim for a single patient, including all service lines and totals.
    """
    treating_doctor: Optional[str] = Field(
        None, 
        description="The doctor's name. CRITICAL INHERITANCE: 1. Check the PAGE HEADER first (lines 1-10 of the page). 2. Check for lines starting with 'Doctor:' within the text. 3. If found, apply this name to ALL claims on the page unless a new 'Doctor:' line appears. 4. Scan BACKWARDS from the current claim to find the most recent doctor. MANDATORY: This field must be populated for 100% of claims."
    )
    plan_name: Optional[str] = Field(
        None, 
        description="The plan type (e.g., 'CHOICE', 'SIG PLAN', 'ADVTG'). Appears in the top-left portion of each patient header row."
    )
    insured_id: Optional[str] = Field(
        None, 
        description="The primary identification number (e.g., 'NCC25633557', 'XXXXX7137'). usually appears in the header row."
    )
    patient_name: Optional[str] = Field(
        None, 
        description="The full name of the patient, typically in 'LAST, FIRST' format."
    )
    patient_account_number: Optional[str] = Field(
        None, 
        description="The patient account number. CRITICAL POSITIONING: This value is located IMMEDIATELY BELOW the Patient Name. It can be SHORT (5 digits like '65049') or LONG (10 digits). Do NOT judge by length. Judge by POSITION: The line directly under 'Patient Name' is the Account Number."
    )
    claim_number: Optional[str] = Field(
        None, 
        description="The claim reference number. CRITICAL POSITIONING: This value is located BELOW the Patient Account Number (which is below the name). It can be SHORT or LONG. If a third line exists under the patient name, it is likely the Claim Number."
    )
    service_date: Optional[str] = Field(
        None, 
        description="The date of service in MM/DD/YY format. CRITICAL: This is a CLAIM-LEVEL field appearing ONCE in the blue header row at the far-right position (the RIGHTMOST field in the horizontal header), typically after the claim number. This SAME date applies to ALL service lines and totals within this claim block. MANDATORY: 100% required—never return null if the header row exists."
    )
    header_message_code: Optional[str] = Field(
        None, 
        description="Any specialized message codes (e.g., 'IF', 'EO') listed at the top of the individual claim block."
    )

    @field_validator("header_message_code", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v
    services: List[ServiceLineItem] = Field(
        default_factory=list, 
        description="A list containing every individual service or material line item within this claim."
    )
    claim_totals: Optional[ServiceLineItem] = Field(
        None, 
        description="The summary 'Totals' row for this patient. Mapping: The row labeled 'Totals' (e.g., 'ABOUD, NASER totals $64.50') at the bottom of the patient block MUST be mapped here, not added to the services list."
    )

class ClaimModel(Claim):
    """Standardized naming for the main repeating entity."""
    pass

class IOFItem(BaseModel):
    """
    Represents an entry in the 'In-Office Finishing' table.
    """
    service_date: Optional[str] = Field(None, description="Date of service in MM/DD/YY format.")
    patient_name: Optional[str] = Field(None, description="Full name of the patient.")
    patient_account_number: Optional[str] = Field(None, description="The 'Pt Acct #' value.")
    authorization_number: Optional[str] = Field(None, description="The 'Auth #' value.")
    description: Optional[str] = Field(None, description="Complete description of the service or material.")
    amount: Optional[float] = Field(None, description="The payment amount for this line item.")

class VSPRemittancePage(BaseModel):
    """
    The top-level model representing a single VSP Remittance document.
    """
    check_number: Optional[str] = Field(
        None, 
        description="The unique 'Check #' found at the top header of the document."
    )
    check_date: Optional[str] = Field(
        None, 
        description="The 'Date:' listed in the document header."
    )
    practice_name: Optional[str] = Field(
        None, 
        description="The name of the practice (e.g., 'STEVEN B RICHLIN OD APC'). Found in the top left header area."
    )
    claims: List[Claim] = Field(
        ..., 
        description="A comprehensive list of every patient claim extracted from the document."
    )
    in_office_finishing: List[IOFItem] = Field(
        default_factory=list, 
        description="Entries from the 'In-Office Finishing (IOF)' table, usually found on the final pages."
    )
    marchon_advantage_savings: Optional[float] = Field(
        None, 
        description="The 'MARCHON ADVANTAGE SAVINGS' total if listed in the final summary."
    )
    total_vsp_check: Optional[float] = Field(
        None, 
        description="The final 'Total VSP Check' amount. This is the global document total found in the final summary section (usually Page 52+)."
    )

class DocumentSummary(BaseModel):
    """
    Global totals for the entire document, usually found on the first or last page.
    """
    total_claims_in_document: Optional[int] = Field(None, description="The 'Total Number of Claims' listed in the summary section.")
    total_remittance_amount: Optional[float] = Field(None, description="The 'Total Check Amount' or total provider payment for the entire document.")

class ResponseModel(BaseModel):
    vsp_remittance_page: VSPRemittancePage
    document_summary: Optional[DocumentSummary] = Field(None, description="Global document-level totals for verification.")

class BatchModel(BaseModel):
    """Model for validating a single batch of claims"""
    claims: List[Claim] = Field(..., description="List of claims found in this batch")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Batch-level metadata")

def map_extracted_data(extracted_claims: List[dict], aggregated_metadata: dict) -> dict:
    """
    Standard function to map generic extraction results into the specific VSP hierarchy.
    """
    # Handle potentially nested metadata from LLM
    vsp_page = aggregated_metadata.get('vsp_remittance_page', {})
    if not isinstance(vsp_page, dict):
        vsp_page = {}
    
    # Merge nested and flat metadata (flat takes precedence for simple fields)
    merged_meta = {**vsp_page, **aggregated_metadata}
    
    return {
        "vsp_remittance_page": {
            "check_number": merged_meta.get('check_number'),
            "check_date": merged_meta.get('check_date'),
            "practice_name": merged_meta.get('practice_name'),
            "claims": extracted_claims,
            "in_office_finishing": merged_meta.get('in_office_finishing') or [],
            "marchon_advantage_savings": merged_meta.get('marchon_advantage_savings'),
            "total_vsp_check": merged_meta.get('total_vsp_check') or merged_meta.get('Total_VSP_Check')
        },
        "document_summary": merged_meta.get('document_summary')
    }

# Define schema description for AI extraction
SCHEMA_DESCRIPTION = """
### HIERARCHICAL ANALYSIS METHODOLOGY:
**CRITICAL**: Study each page's visual hierarchy in detail before extraction:
1. **Scan for Section Markers**: Check PAGE HEADER (top 10 lines) for "Doctor:" or "Practice Name".
2. **Identify Claim Blocks**: Blue/shaded header rows mark the start of each patient claim.
3. **Analyze Vertical Stacking**: 
   - **Line 1 (Header)**: Plan | Insured ID | Patient Name | Service Date
   - **Line 2 (Below Header)**: Patient Account Number (IMMEDIATELY below Name)
   - **Line 3 (Below Acct#)**: Claim Number (if present)
4. **Apply Inheritance**: Doctor name from Page Header applies to ALL claims on that page.

### VSP DOCUMENT STRUCTURE & VISUAL CUES:
1.  **DOCUMENT-LEVEL HEADER (PAGE 1 ONLY)**:
    - **Location**: Top 20 lines of the first page.
    - **Check Number**: Explicitly labeled as 'Check #' or 'Check Number'. (e.g., '98466196'). Map to `check_number`.
    - **Check Date**: Labeled as 'Date:' (e.g., '11/20/25'). Map to `check_date`.
    - **Practice Name**: The large text at the top, usually near the practice address (e.g., 'BUNCH FAMILY EYE CARE'). Map to `practice_name`.
    - **CRITICAL**: Do NOT ignore the top of Page 1. These values are global for the entire document.

2.  **PAGE HEADER (Every Page)**: Often contains 'Doctor:' name.
2.  **PATIENT CLAIM BLOCKS**:
    *   **Header Row (Blue/Shaded)**: 
        - **Left**: Plan Name
        - **Center**: Insured ID, Patient Name
        - **Service Date Retrieval**: 
            - **MANDATORY**: Every claim block MUST have a `service_date`.
            - Look at the **FIRST ROW** of the service table (left side). 
            - If not found there, check the **SECOND ROW** or the **HEADER LINE** immediately above the table.
            - Apply this date to the `service_date` field for the entire claim block.
    *   **Line Below Name**: This is explicitly the **Patient Account Number**. It can be SHORT (5 digits) or LONG (10 digits). TRUST THE POSITION.
    *   **Line Below Account#**: This is the **Claim Number**.
    *   **Doctor Inheritance**: The Doctor's name appears at the top of the page OR at the start of a claim block. You **MUST** apply this name to every claim listed below it until a NEW 'Doctor:' header appears. Look at the PAGE HEADER for the primary doctor.

3.  **SERVICE LINE ITEMS (The "Body" of the Claim)**:
    *   **Location**: These rows appear vertically BETWEEN the "Claim Number" and the "Totals" row.
    *   **Content**: They contain **Procedure Codes** (CPT/HCPCS codes like '92014', 'V2100', 'V2781'), Descriptions, and Amounts.
    *   **CRITICAL**: You MUST extract the `procedure_code` for every service line that has one. It is usually the FIRST field on the left of the service line.
    *   **Extraction Rule**: You MUST extract every single row of data between the Header and the Totals. Do not stop until you see "Totals".
    *   **Common Failure Warning**: Do NOT skip these rows. The Patient/Account/Claim IDs are just the *setup*. The Service Lines are the *data*. 

4.  **TOTALS ROW**: The row labeled 'Totals' at the bottom of a patient block. **MANDATORY**: Map this row to the `claim_totals` field in the Claim object. Do NOT put it in the `services` list.

5.  **FINAL DOCUMENT SUMMARY (Last Page)**:
    *   **Location**: The very end of the document (last page).
    *   **Content**: "Total VSP Check" amount.
    *   **Mapping**: Map this to the `total_vsp_check` field in metadata. Do NOT leave this null. If the document ends, find the final total.

### IDENTIFIER DISAMBIGUATION & THE 10-DIGIT RULE (CRITICAL):
VSP documents have specific stacking rules. You MUST follow this logic to avoid field swapping:
1. **Patient Name** is the primary anchor.
2. **THE 10-DIGIT RULE**: Any identifier that is exactly **10 digits** (e.g., '1767767000') is historically a **CLAIM NUMBER**. 
3. **MAPPING PRIORITY**:
   - If you see a name followed by ONE number: If it is 10 digits, map it to `claim_number`.
   - If you see a name followed by TWO numbers: The first is `patient_account_number`, the second (usually 10 digits) is `claim_number`.
4. **POSITIONAL CUES**:
   - Line 1: Patient Name
   - Line 2: Patient Account Number
   - Line 3: Claim Number (PRIORITIZE THIS for 10-digit numbers)

**Correct Mapping Examples:**
*   **Case A (Short Acct, Long Claim):**
    Name: SMITH, JOHN
    Row 2: 65049     -> `patient_account_number`
    Row 3: 1767767000 -> `claim_number`
*   **Case B (10-Digit Claim Only):**
    Name: DOE, JANE
    Row 2: 1767767000 -> `claim_number` (Map to claim_number because it is 10 digits)
    `patient_account_number`: null

### IN-OFFICE FINISHING (IOF) - VISUAL EXTRACTION ONLY:
**🚨🚨🚨 ABSOLUTE CRITICAL 🚨🚨🚨**
**LOCATION**: Navigate to the **LAST PAGE** of the PDF.
1. **Search**: Explicitly search for the table with header **'In-Office Finishing'** (or "IOF") on the last page.
2. **Visual Scan**: Look for columns like "Service Date", "Patient Name", "Pt Acct #", "Auth #", "Description", "Amount".
3. **Extraction**: Extract this table **COMPLETELY**.
4. **Placement**: Place the results in `metadata.in_office_finishing`.
5. **Zero Tolerance**: Do not return an empty list if there are table rows visible on the last page.

### ZERO DATA LOSS RULES:
*   **Doctors**: If 'treating_doctor' is null, re-scan the Page Header or block header. Apply to all claims below. (Refer to LESSONS/CONTEXT provided in the prompt).
*   **Service Date**: Always present in the first row of services. Apply to all service lines in the claim.
*   **Account Numbers**: Every claim must have one. Look below the name. (MANDATORY: Do not return null).
*   **Claim Totals**: Every claim MUST have a `claim_totals` object. If missing, retrieve from the 'Totals' row at the end of the patient block.
*   **Final Global Total**: SEARCH THE LAST PAGE for "Total VSP Check". Map exactly to `total_vsp_check`. Do not leave as null if it exists visually.
"""

def section_builder(text: str) -> List[Dict[str, str]]:
    """
    Identify VSP document sections using regex.
    Splits by patient name or claim headers.
    """
    import re
    sections = []
    
    # 1. Identify Patient Blocks (Anchor: Patient Name in blue header)
    # Usually starts with PATIENT NAME: or similar or just a known pattern
    # VSP often has "Member Name: LAST, FIRST" or just "LAST, FIRST" in a header
    # We look for capitalized names followed by IDs
    patient_pattern = r"(?:Plan Name:.*?\n)?(?:Patient Name:)?\s*([A-Z, ]{3,30})\n"
    
    matches = list(re.finditer(patient_pattern, text))
    
    if not matches:
        # Fallback to a single section if no splits found
        return [{"type": "content", "text": text}]
        
    for i in range(len(matches)):
        start_pos = matches[i].start()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        section_text = text[start_pos:end_pos]
        sections.append({
            "type": "claim_block",
            "patient_hint": matches[i].group(1).strip(),
            "text": section_text
        })
        
    return sections

def calculate_totals(claims_data: dict) -> dict:
    """Calculate format-specific totals for the final response"""
    total_billed = 0.0
    total_paid = 0.0
    total_patient_responsibility = 0.0
    
    # Extract claims from the nested structure
    page = claims_data.get('vsp_remittance_page', {})
    claims = page.get('claims', [])
    
    for claim in claims:
        services = claim.get('services', [])
        for svc in services:
            total_billed += float(svc.get('billed_amount') or 0)
            total_paid += float(svc.get('provider_payment') or 0)
            total_patient_responsibility += float(svc.get('copay') or 0) + float(svc.get('patient_pay') or 0)
            
    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_patient_responsibility": total_patient_responsibility
    }