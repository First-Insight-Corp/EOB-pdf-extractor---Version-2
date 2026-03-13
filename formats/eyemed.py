from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class EyeMedServiceLine(BaseModel):
    """
    Represents a single service row within an EyeMed claim.
    Extracts data from the main table columns like 'Service Code', 'Total Charges', etc.
    """
    date_of_service: Optional[str] = Field(
        None, 
        description="Date service was performed (e.g., '10/10/25'). Found in 'Date of Service' column."
    )
    service_code: Optional[str] = Field(
        None, 
        description="CPT/HCPCS code (e.g., '92004', 'V278126'). Found in 'Service Code' column."
    )
    units: Optional[int] = Field(
        None, 
        description="Number of units. Found in '# of Units' column."
    )
    total_charges: Optional[float] = Field(
        None, 
        description="Submitted amount. Found in 'Total Charges' column."
    )
    contractual_write_off: Optional[float] = Field(
        None, 
        description="Amount written off. Found in 'Contractual Write-Off' column."
    )
    member_responsibility: Optional[float] = Field(
        None, 
        description="Amount the patient pays. Found in 'Member Resp.' column."
    )
    claim_payment: Optional[float] = Field(
        None, 
        description="Net payment for this line before tax/chargebacks. Found in 'Claim Payment' column."
    )
    dispensing_amount: Optional[float] = Field(
        None, 
        description="Found in 'Dispensing Amount' column."
    )
    copay_amount: Optional[float] = Field(
        None, 
        description="Patient copay found in 'Copay Amount' column."
    )
    other_insurance: Optional[float] = Field(
        None, 
        description="Payments from other insurers. Found in 'Other Insurance' column."
    )
    line_chargebacks: Optional[float] = Field(
        None, 
        description="Chargebacks specific to this line item. Found in 'Chargebacks' column."
    )
    remark_codes: Optional[str] = Field(
        None, 
        description="Codes explaining adjustments (e.g., 'PSR', '918'). Found in 'Remark Code(s)' column."
    )

class LabMaterialLine(BaseModel):
    """
    Represents a row in the small 'Lab Materials' table often found at the bottom of a claim.
    """
    description: Optional[str] = Field(
        None, 
        description="Description of the lab item (e.g., 'PROGRESSIVE LAB GROUP L', 'AR LAB GROUP H')."
    )
    amount: Optional[float] = Field(
        None, 
        description="The chargeback amount for this material."
    )

class ClaimModel(BaseModel):
    """
    Represents a full claim block for a specific patient. 
    EyeMed documents often split header info between 'Claim #' section and 'Subscriber Name' section.
    """
    # --- Header Information ---
    claim_number: Optional[str] = Field(
        None, 
        description="Unique claim ID (e.g., '120670758600')."
    )
    member_name: Optional[str] = Field(
        None, 
        description="Patient name (e.g., 'ARNOLD, ROSANNA'). Found in 'Member Name'."
    )
    member_id: Optional[str] = Field(
        None, 
        description="Member ID if present."
    )
    provider_name: Optional[str] = Field(
        None, 
        description="Doctor associated with this specific claim (e.g., 'MURATA, NELSON T.')."
    )
    plan_type: Optional[str] = Field(
        None, 
        description="Plan name (e.g., 'MEDICARE')."
    )
    subscriber_name: Optional[str] = Field(
        None, 
        description="Name of the main subscriber. Found in 'Subscriber Name'."
    )
    subscriber_id: Optional[str] = Field(
        None, 
        description="Subscriber ID (e.g., '36001550700')."
    )
    place_of_service_code: Optional[str] = Field(
        None, 
        description="Code indicating where service occurred (e.g., '11')."
    )
    place_of_service_Description: Optional[str] = Field(
        None,
        description="Description of place of service (e.g., 'Office')."
    )

    # --- Line Items ---
    services: List[EyeMedServiceLine] = Field(
        ..., 
        description="List of service lines (procedures) for this claim."
    )
    lab_materials: Optional[List[LabMaterialLine]] = Field(
        None, 
        description="List of items from the 'Lab Materials' chargeback table, if present."
    )

    # --- Claim Totals (Footer) ---
    total_claim_chargebacks: Optional[float] = Field(
        None, 
        description="Total chargebacks for the claim. Found in 'Chargebacks' summary field."
    )
    sales_tax: Optional[float] = Field(
        None, 
        description="Sales tax deducted. Found in 'Sales Tax' field."
    )
    claim_net_payment: Optional[float] = Field(
        None, 
        description="The final net payment for this claim. Found in 'Claim Net Payment'."
    )
    total_claim_revenue: Optional[float] = Field(
        None, 
        description="Total revenue reported for this claim. Found in 'Total Claim Revenue'."
    )

class StatementSummary(BaseModel):
    """
    Extracts the 'Statement Summary' table usually found on the first page.
    """
    statement_date: Optional[str] = Field(
        None, description="Date of the statement (e.g., '10/30/25')."
    )
    statement_id: Optional[str] = Field(
        None, description="The Statement ID (e.g., 'S-D102X...')."
    )
    tax_id: Optional[str] = Field(
        None, description="Provider Tax ID."
    )
    total_claims_payment: Optional[float] = Field(
        None, description="Sum of payments before deductions."
    )
    total_chargebacks: Optional[float] = Field(
        None, description="Total chargebacks for the whole statement."
    )
    statement_net_total: Optional[float] = Field(
        None, description="The final check/EFT amount (e.g., '-$172.27')."
    )
    deposit_id: Optional[str] = Field(
        None, description="Deposit ID/Reference Number associated with this statement."
    )

class ResponseModel(BaseModel):
    """
    Top-level model for extracting data from an EyeMed Remittance Advice.
    """
    provider_address_block: Optional[str] = Field(
        None, 
        description="The provider name and address text block found at the top left (e.g., 'NELSON T MURATA OD...')."
    )
    statement_summary: Optional[StatementSummary] = Field(
        None, 
        description="The summary table usually found on Page 1."
    )
    claims: List[ClaimModel] = Field(
        ..., 
        description="List of all patient claims extracted from the document."
    )

class BatchModel(BaseModel):
    """Model for validating a single batch of claims"""
    claims: List[ClaimModel] = Field(..., description="List of claims found in this batch")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Batch-level metadata")

def map_extracted_data(extracted_claims: List[dict], aggregated_metadata: dict) -> dict:
    """
    Standard function to map generic extraction results into the EyeMed hierarchy.
    """
    return {
        "provider_address_block": aggregated_metadata.get('provider_address_block'),
        "statement_summary": aggregated_metadata.get('statement_summary'),
        "claims": extracted_claims
    }

# Define schema description for AI extraction
SCHEMA_DESCRIPTION = """
EyeMed Extraction Rules:
1. DOCUMENT METADATA: On Page 1, look for the 'provider_address_block' (top left) and the 'Statement Summary' table. Include these in the 'metadata' object.
2. NESTED STRUCTURE: Every item in the 'claims' list MUST be an 'ClaimModel' object.
3. SERVICES ARRAY: Every 'ClaimModel' MUST have a 'services' list containing 'EyeMedServiceLine' objects. DO NOT flatten service fields into the claim header.
4. ZERO-VALUE RULE: Return 0.0 for numeric fields showing 0.00. Do not return null.
5. REMARK CODES: Use spaces for multiple codes (e.g., "PSR 918").

Field Hierarchy:
- ResponseModel Metadata:
    - provider_address_block, statement_summary (on Page 1)
- ClaimModel (Header Fields):
    - claim_number, member_name, member_id, provider_name, plan_type, subscriber_name, subscriber_id, etc.
    - services: [
        {
            "date_of_service": "...",
            "service_code": "...",
            "total_charges": ...,
            "claim_payment": ...,
            ... (other EyeMedServiceLine fields)
        }
      ]
    - lab_materials: [ ... ]
"""

def section_builder(text: str) -> List[Dict[str, str]]:
    """
    Identify EyeMed document sections using regex.
    EyeMed usually has a simpler structure but can be split by 'Claim #' or 'Member Name'.
    """
    import re
    sections = []
    
    # Simple pattern for EyeMed claim blocks
    pattern = r"(?:Claim\s*#:\s*(\d+))"
    matches = list(re.finditer(pattern, text))
    
    if not matches:
        return [{"type": "content", "text": text}]
        
    for i in range(len(matches)):
        start_pos = matches[i].start()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        sections.append({
            "type": "claim_block",
            "claim_hint": matches[i].group(1),
            "text": text[start_pos:end_pos]
        })
        
    return sections

def calculate_totals(claims_data: dict) -> dict:
    """Calculate format-specific totals for the final response"""
    total_charges = 0.0
    total_plan_paid = 0.0
    total_member_responsibility = 0.0
    
    claims = claims_data.get('claims', [])
    
    for claim in claims:
        services = claim.get('services', [])
        for svc in services:
            total_charges += float(svc.get('total_charges') or 0)
            total_plan_paid += float(svc.get('claim_payment') or 0)
            total_member_responsibility += float(svc.get('member_responsibility') or 0)
            
    return {
        "total_charges": total_charges,
        "total_plan_paid": total_plan_paid,
        "total_member_responsibility": total_member_responsibility
    }