from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ServiceLineItem(BaseModel):
    """Represents an individual service line within an Avesis claim."""

    service_date: Optional[str] = Field(
        None,
        description="Date of service in MM/DD/YYYY format (e.g., '02/03/2025', '01/27/2025')."
    )
    proc_code: Optional[str] = Field(
        None,
        description="CPT/HCPCS procedure code for this service line (e.g., '92014', 'V2100', 'V2520')."
    )
    service_description: Optional[str] = Field(
        None,
        description="Full text description of the service or material (e.g., 'Vision Exam - Est Patient - Comprehensive', 'ANTI-REFLECTIVE COATING, PER LENS')."
    )
    billed_amount: Optional[float] = Field(
        None,
        description="Amount billed by the provider for this service line (e.g., 150.00, 37.50)."
    )
    copay_amount: Optional[float] = Field(
        None,
        description="Patient copay amount for this service line (e.g., 10.00, 25.00, 0.00)."
    )
    int_fee: Optional[float] = Field(
        None,
        description="Interest fee amount for this service line. Usually 0.00 (e.g., 0.00, 0.19)."
    )
    prov_adj: Optional[float] = Field(
        None,
        description="Provider adjustment amount for this service line (e.g., 0.00, 26.28). From the 'Prov Adj' column."
    )
    lab_chargeback: Optional[float] = Field(
        None,
        description="Lab chargeback amount for this service line (e.g., 0.00). From the 'Lab Chargeback' column."
    )
    paid_amount: Optional[float] = Field(
        None,
        description="Amount paid to the provider for this service line (e.g., 50.00, 7.50, 0.00, 175.19)."
    )
    remarks: Optional[str] = Field(
        None,
        description="Remark codes associated with this service line (e.g., 'VM80', 'PF35', '119O'). Separate multiple with a space."
    )

    @field_validator("remarks", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v


class Claim(BaseModel):
    """Represents a full claim for a single patient within an Avesis remittance."""

    plan: Optional[str] = Field(
        None,
        description="Plan code identifying the insurance plan for this claim (e.g., '050130EZL3', '065175CZL6', '9180', '9181'). Appears in the left-most column of the claim header row."
    )
    insured_id: Optional[str] = Field(
        None,
        description="Insured member identification number (e.g., '17103585', 'W018616000', '16477188')."
    )
    patient_name: Optional[str] = Field(
        None,
        description="Full name of the patient (e.g., 'Keaton M Chapman', 'Brandi Lea Millison', 'Alex Muntz')."
    )
    patient_account_number: Optional[str] = Field(
        None,
        description="Provider-assigned patient account number (e.g., '52792', '52741', '52756')."
    )
    claim_number: Optional[str] = Field(
        None,
        description="Unique claim number assigned by Avesis (e.g., '2025035T0095500', '2025029T0167600', '2025034M0077900')."
    )
    claim_billed_amount: Optional[float] = Field(
        None,
        description="Total billed amount for this claim as shown in the bold claim header row (e.g., 500.00, 520.00, 150.00)."
    )
    claim_copay_amount: Optional[float] = Field(
        None,
        description="Total copay amount for this claim as shown in the bold claim header row (e.g., 35.00, 20.00, 0.00)."
    )
    claim_int_fee: Optional[float] = Field(
        None,
        description="Total interest fee for this claim as shown in the bold claim header row (e.g., 0.00, 0.19)."
    )
    claim_prov_adj: Optional[float] = Field(
        None,
        description="Total provider adjustment for this claim as shown in the bold claim header row (e.g., 0.00, 26.28)."
    )
    claim_lab_chargeback: Optional[float] = Field(
        None,
        description="Total lab chargeback for this claim as shown in the bold claim header row (e.g., 0.00)."
    )
    claim_paid_amount: Optional[float] = Field(
        None,
        description="Total paid amount for this claim as shown in the bold claim header row (e.g., 128.00, 120.00, 60.00, 148.91)."
    )

    services: List[ServiceLineItem] = Field(
        default_factory=list,
        description="All individual service line items within this claim, indented below the claim header row."
    )
    claim_totals: Optional[ServiceLineItem] = Field(
        None,
        description=(
            "Summary totals row for this claim if a separate totals row exists. "
            "MANDATORY: Map the totals row here — do NOT include it in the services list. "
            "Note: For Avesis, claim-level totals are usually embedded in the bold claim header row "
            "fields (claim_billed_amount, claim_paid_amount, etc.) rather than a separate totals row."
        )
    )


class ClaimModel(Claim):
    """Standardized naming for the main repeating entity."""
    pass


class RemarkCode(BaseModel):
    """Represents a single entry from the Remarks / Service Line Explanation table."""

    code: Optional[str] = Field(
        None,
        description="The remark code (e.g., '119O', 'PF35', 'VM80')."
    )
    service_line_explanation: Optional[str] = Field(
        None,
        description="Full text explanation for the remark code (e.g., 'Benefit maximum for this benefit period has been reached.', 'Member receives preferred pricing on lens option.')."
    )


class ClaimCycleSummary(BaseModel):
    """Represents the Claim Cycle Summary block on the final page of the Avesis remittance."""

    outstanding_balance_applied: Optional[float] = Field(
        None,
        description="Any outstanding balance applied against this payment cycle (e.g., 0.00)."
    )
    claim_cycle_total: Optional[float] = Field(
        None,
        description="Total paid amount across all claims in this remittance cycle (e.g., 686.91)."
    )
    refund_paid: Optional[float] = Field(
        None,
        description="Any refund paid amount in this cycle (e.g., 0.00)."
    )
    total_amount_paid: Optional[float] = Field(
        None,
        description="Final total amount paid after all adjustments, matching the check amount (e.g., 686.91)."
    )


class AvesisRemittancePage(BaseModel):
    """The top-level model representing a single Avesis Incorporated Remittance Advice document."""

    payer_name: Optional[str] = Field(
        None,
        description="Name of the payer/insurer (e.g., 'AVESIS INCORPORATED')."
    )
    payer_address: Optional[str] = Field(
        None,
        description="Payer mailing address as printed on the document (e.g., 'P.O. BOX 38300, PHOENIX, AZ 85069')."
    )
    provider_name: Optional[str] = Field(
        None,
        description="Name of the billing provider/practice (e.g., 'Child and Family Vision Center, Inc'). Appears in the top-right header."
    )
    provider_address: Optional[str] = Field(
        None,
        description="Full billing provider address (e.g., '2525 NORTH ANKENY BLVD, ANKENY, IA 50023-4708'). Appears in the top-right header."
    )
    check_date: Optional[str] = Field(
        None,
        description="Date of the remittance/check labeled 'DATE:' (e.g., '02/05/2025'). May appear as YYYYMMDD on summary page (e.g., '20250205')."
    )
    check_number: Optional[str] = Field(
        None,
        description="Check number labeled 'Check #:' (e.g., '307796')."
    )
    claims: List[Claim] = Field(
        ...,
        description="A comprehensive list of every patient claim extracted from the remittance table."
    )
    claim_cycle_summary: Optional[ClaimCycleSummary] = Field(
        None,
        description="The Claim Cycle Total summary block from the final page of the remittance."
    )
    remark_codes: List[RemarkCode] = Field(
        default_factory=list,
        description="All remark code definitions from the 'Remarks / Service Line Explanation' table at the bottom of the remittance."
    )


SCHEMA_DESCRIPTION = """
### HIERARCHICAL ANALYSIS METHODOLOGY:
**CRITICAL**: Study each page's visual hierarchy before extraction:
1. **Scan the Document Header**: Top-left shows payer name and address. Top-center shows DATE and Check #.
   Top-right shows billing provider name and address.
2. **Identify Claim Header Rows**: Bold rows in the main table represent individual claim headers.
   Each bold row contains: Plan | Insured ID | Patient Name | Patient Acct # | Claim Number |
   Billed Amount | Copay Amount | Int Fee | Prov Adj | Lab Chargeback | Paid Amount.
3. **Extract Service Lines**: Indented (non-bold) rows below each claim header are the service lines.
   Each contains: Service Date | Proc Code | Service Description | Billed Amount | Copay Amount |
   Int Fee | Prov Adj | Lab Chargeback | Paid Amount | Remarks.
4. **Capture Remarks Table**: At the bottom of the last claims page, a 'Remarks / Service Line Explan'
   table lists remark code definitions → `remark_codes`.
5. **Capture Claim Cycle Summary**: The final page contains a summary box → `claim_cycle_summary`.

### DOCUMENT STRUCTURE:

1. **DOCUMENT-LEVEL HEADER** (top of every page):
   - Left: Payer name (AVESIS INCORPORATED), payer address.
   - Center: DATE, Check #.
   - Right: Provider/practice name and address.

2. **REMITTANCE TABLE** (main body, multi-page):
   Column headers (two-row spanning header):
   Row 1: Plan | Insured ID | Patient Name | Patient Acct # | Claim Number
   Row 2: [Plan column] | Service Date | Proc Code | Service Description |
           Billed Amount | Copay Amount | Int Fee | Prov Adj | Lab Chargeback | Paid Amount | Remarks

   **CLAIM HEADER ROW** (bold, spans full row width):
   - Plan code (leftmost, e.g., '050130EZL3', '9180')
   - Insured ID
   - Patient Name (bold)
   - Patient Acct #
   - Claim Number
   - Billed Amount (claim total, bold)
   - Copay Amount (claim total, bold)
   - Int Fee (claim total, bold)
   - Prov Adj (claim total, bold)
   - Lab Chargeback (claim total, bold)
   - Paid Amount (claim total, bold)
   Map these to `claim_billed_amount`, `claim_copay_amount`, `claim_int_fee`,
   `claim_prov_adj`, `claim_lab_chargeback`, `claim_paid_amount` on the Claim model.

   **SERVICE LINE ROWS** (indented, non-bold, below each claim header):
   - service_date, proc_code, service_description, billed_amount, copay_amount,
     int_fee, prov_adj, lab_chargeback, paid_amount, remarks.
   - `remarks`: Codes appear in the rightmost column (e.g., 'VM80', 'PF35', '119O').
   - `int_fee`: May have a value like 0.19 even when prov_adj is 0.00 — capture independently.
   - `prov_adj`: Capture the value from the 'Prov Adj' column — may be non-zero (e.g., 26.28).

3. **REMARKS / SERVICE LINE EXPLANATION TABLE**:
   - Located at the bottom of the last claims page.
   - Two columns: Code | Service Line Explanation.
   - Extract fully into `remark_codes`.
   - Note: PF35 may have multi-line explanations — concatenate into a single string.

4. **CLAIM CYCLE SUMMARY** (final page):
   Labeled box containing:
   - Outstanding Balance Applied
   - Claim Cycle Total
   - Outstanding Balance Applied (second instance)
   - Refund Paid
   - Total Amount Paid
   Map to `claim_cycle_summary`.

### SPECIAL EXTRACTION NOTES:

- **Plan Code**: The leftmost column in each bold claim header row. Numeric values like '9180',
  '9181' are plan codes, not IDs — map to `plan` field.
- **Insured ID formats vary**: May be alphanumeric (e.g., '17103585', 'W018616000', '16477188').
  Always treat as string.
- **Claim Number formats vary**: Mix of date-prefixed codes (e.g., '2025035T0095500',
  '2025034M0077900') — always string.
- **Int Fee vs Prov Adj**: These are separate columns. Do not conflate.
  Int Fee = interest/interchange fee. Prov Adj = provider-level adjustment.
- **Multi-line remarks**: A single service line may have multiple remark codes (e.g., 'VM80 PF35').
  Join with a space.
- **Remark table PF35**: Spans multiple lines in the document — concatenate all lines
  for PF35 into a single service_line_explanation string.
- **Date formats**: `check_date` appears as MM/DD/YYYY on claim pages (e.g., '02/05/2025')
  and as YYYYMMDD on the summary page (e.g., '20250205'). Use MM/DD/YYYY format.

### ZERO DATA LOSS RULES:
- Every claim MUST capture both the claim header totals (claim_billed_amount, claim_paid_amount, etc.)
  AND the individual service line rows in `services`.
- `remark_codes` must be fully extracted — do not return an empty list if the table exists.
- `claim_cycle_summary` is MANDATORY when the final summary page is present.
- `int_fee` and `prov_adj` on service lines must be captured independently — never merged.
- Service lines that show 0.00 in paid_amount must still be included in `services`.
- `remarks` on service lines must be captured even when they appear in only some rows.
"""


def build_avesis_payload(extracted_claims: list, merged_meta: dict) -> dict:
    return {
        "avesis_remittance_page": {
            "payer_name": merged_meta.get("payer_name"),
            "payer_address": merged_meta.get("payer_address"),
            "provider_name": merged_meta.get("provider_name"),
            "provider_address": merged_meta.get("provider_address"),
            "check_date": merged_meta.get("check_date"),
            "check_number": merged_meta.get("check_number"),
            "claims": extracted_claims,
            "claim_cycle_summary": merged_meta.get("claim_cycle_summary"),
            "remark_codes": merged_meta.get("remark_codes") or [],
        }
    }


def calculate_totals(claims_data: dict) -> dict:
    """Calculate format-specific totals for the final response."""
    total_billed = 0.0
    total_paid = 0.0
    total_patient_responsibility = 0.0

    page = claims_data.get("avesis_remittance_page", {})
    claims = page.get("claims", [])

    for claim in claims:
        for svc in claim.get("services", []):
            total_billed += float(svc.get("billed_amount") or 0)
            total_paid += float(svc.get("paid_amount") or 0)
            total_patient_responsibility += float(svc.get("copay_amount") or 0)

    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_patient_responsibility": total_patient_responsibility,
    }