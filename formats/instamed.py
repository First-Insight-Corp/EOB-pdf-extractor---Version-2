from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ServiceLineItem(BaseModel):
    """
    Represents an individual service line within an Instamed claim.
    """

    begin_service_date: Optional[str] = Field(
        None,
        description="Start date of the service in MM/DD/YYYY format (e.g., '9/28/2025')."
    )
    end_service_date: Optional[str] = Field(
        None,
        description="End date of the service in MM/DD/YYYY format. Usually the same as begin_service_date."
    )
    procedure_code: Optional[str] = Field(
        None,
        description="The CPT/HCPCS procedure code (e.g., '92014', 'V2020', 'V2299')."
    )
    modifiers: Optional[str] = Field(
        None,
        description="Modifier(s) appended to the procedure code in parentheses (e.g., 'NP', 'PL', 'MV', 'UL'). Separate multiple with a space."
    )
    num_of_units: Optional[int] = Field(
        None,
        description="Number of units billed for this service line (e.g., 1, 2)."
    )
    amount_billed: Optional[float] = Field(
        None,
        description="Amount billed by the provider for this service line (e.g., 322.00)."
    )
    allowed: Optional[float] = Field(
        None,
        description="Allowed/contractual amount for this service line per fee schedule (e.g., 87.50)."
    )
    payment: Optional[float] = Field(
        None,
        description="Amount paid by the payer for this service line. May be negative for reversals (e.g., -0.50)."
    )
    patient_responsibility: Optional[float] = Field(
        None,
        description="Amount the patient is responsible for on this service line (e.g., copay 10.00)."
    )
    contractual_adjustments: Optional[float] = Field(
        None,
        description="Contractual adjustment amount for this service line (e.g., 322.00, 163.00)."
    )
    other_adjustments: Optional[float] = Field(
        None,
        description="Other adjustment amount for this service line (e.g., 0.00)."
    )
    adjustment_reason: Optional[str] = Field(
        None,
        description="All adjustment reason codes for this line (e.g., 'CO-45', 'PR-3 CO-45', 'CO-P14'). Separate multiple with a space."
    )
    remarks: Optional[str] = Field(
        None,
        description="Remark codes for this service line (e.g., 'N807'). Separate multiple with a space."
    )

    @field_validator("modifiers", "adjustment_reason", "remarks", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v


class Claim(BaseModel):
    """
    Represents a full claim for a single patient within an Instamed remittance.
    """

    patient_account_number: Optional[str] = Field(
        None,
        description="Provider-assigned patient account number. Often '0' if not assigned (e.g., '0')."
    )
    patient_name: Optional[str] = Field(
        None,
        description="Full name of the patient in 'LAST, FIRST' format (e.g., 'MITCHEM, PAMELAP')."
    )
    insured_id: Optional[str] = Field(
        None,
        description="Insured member identification number (e.g., '601104537715')."
    )
    insured_name: Optional[str] = Field(
        None,
        description="Full name of the insured/subscriber (e.g., 'MITCHEM, PAMELAP')."
    )
    payer_claim_number: Optional[str] = Field(
        None,
        description="Unique claim number assigned by the payer (e.g., '0046190797')."
    )
    claim_status: Optional[str] = Field(
        None,
        description="Processing status of the claim (e.g., 'Processed as Primary')."
    )
    service_provider_npi: Optional[str] = Field(
        None,
        description="NPI of the service/rendering provider (e.g., '1225069792')."
    )
    service_provider_qualifier: Optional[str] = Field(
        None,
        description="Qualifier code for the service provider identifier (e.g., 'XX')."
    )
    service_provider_name: Optional[str] = Field(
        None,
        description="Name of the rendering/service provider (e.g., 'Bigham, Kevin')."
    )

    @field_validator("claim_status", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v

    services: List[ServiceLineItem] = Field(
        default_factory=list,
        description="All individual service line items within this claim."
    )
    claim_totals: Optional[ServiceLineItem] = Field(
        None,
        description=(
            "The 'Total' summary row for this claim. "
            "MANDATORY: Map the totals row here — do NOT include it in the services list."
        )
    )


class ClaimModel(Claim):
    """Standardized naming for the main repeating entity."""
    pass


class AdjustmentReasonCode(BaseModel):
    """
    Represents a single entry from the Adjustment Reason Codes section.
    """

    group: Optional[str] = Field(
        None,
        description="Group category label (e.g., 'CO: Contractual Obligations', 'PR: Patient Responsibility')."
    )
    code: Optional[str] = Field(
        None,
        description="The adjustment reason code (e.g., 'CO-45', 'CO-P14', 'PR-3')."
    )
    description: Optional[str] = Field(
        None,
        description="Full text description of the adjustment reason code."
    )


class RemarkCode(BaseModel):
    """
    Represents a single entry from the Remark Codes section.
    """

    code: Optional[str] = Field(
        None,
        description="The remark code (e.g., 'N807')."
    )
    description: Optional[str] = Field(
        None,
        description="Full text description of the remark code."
    )


class ReconciliationSummary(BaseModel):
    """
    Represents the Reconciliation Summary block of the remittance.
    """

    total_charges: Optional[float] = Field(
        None,
        description="Total charges billed across all claims (e.g., 1657.00)."
    )
    total_patient_responsibility: Optional[float] = Field(
        None,
        description="Total patient responsibility across all claims. May be negative (e.g., -20.00)."
    )
    total_contractual_adjustments: Optional[float] = Field(
        None,
        description="Total contractual adjustments across all claims. May be negative (e.g., -1628.50)."
    )
    total_other_adjustments: Optional[float] = Field(
        None,
        description="Total other adjustments across all claims (e.g., 0.00)."
    )
    total_claim_payment: Optional[float] = Field(
        None,
        description="Total claim payment amount (e.g., 8.50)."
    )
    provider_adjustments: Optional[float] = Field(
        None,
        description="Provider-level adjustment amount (e.g., 0.00)."
    )
    payment_amount: Optional[float] = Field(
        None,
        description="Final payment amount matching the check/EFT (e.g., 8.50)."
    )


class PayerInformation(BaseModel):
    """
    Represents the Payer Information block of the remittance.
    """

    payer_name: Optional[str] = Field(
        None,
        description="Name of the insurance payer (e.g., 'Superior Vision by MetLife')."
    )
    payer_id: Optional[str] = Field(
        None,
        description="Payer identification number (e.g., '13374')."
    )
    payer_id_qualifier: Optional[str] = Field(
        None,
        description="Qualifier for the payer ID (e.g., 'XV')."
    )
    payer_address: Optional[str] = Field(
        None,
        description="Full payer mailing address (e.g., '881 Elkridge Landing Rd, Linthicum Heights, MD 21090')."
    )


class PaymentInformation(BaseModel):
    """
    Represents the Payment Information block of the remittance.
    """

    payment_amount: Optional[float] = Field(
        None,
        description="Payment amount issued (e.g., 8.50)."
    )
    payment_date: Optional[str] = Field(
        None,
        description="Date the payment was issued (e.g., '10/15/2025')."
    )
    payment_method: Optional[str] = Field(
        None,
        description="Method of payment (e.g., 'ACH')."
    )
    check_eft_trace_number: Optional[str] = Field(
        None,
        description="Check or EFT trace/reference number (e.g., '39521379')."
    )
    billing_provider_name: Optional[str] = Field(
        None,
        description="Name of the billing provider/practice (e.g., 'FIRST CHOICE EYE CARE OD PLLC')."
    )
    billing_provider_id: Optional[str] = Field(
        None,
        description="Billing provider identifier (e.g., '300095616')."
    )
    billing_provider_id_qualifier: Optional[str] = Field(
        None,
        description="Qualifier for the billing provider ID (e.g., 'FI')."
    )
    billing_provider_address: Optional[str] = Field(
        None,
        description="Full billing provider mailing address (e.g., '14617A W Lawyers Rd, MATTHEWS, NC 28104-3219')."
    )
    version_identification: Optional[str] = Field(
        None,
        description="EDI version identification string (e.g., 'HSP')."
    )


class InstamedRemittancePage(BaseModel):
    """
    The top-level model representing a single Instamed Remittance document.
    """

    payer_information: Optional[PayerInformation] = Field(
        None,
        description="Payer name, ID, qualifier, and address from the Payer Information block."
    )
    payment_information: Optional[PaymentInformation] = Field(
        None,
        description="Payment amount, date, method, trace number, and billing provider details."
    )
    reconciliation_summary: Optional[ReconciliationSummary] = Field(
        None,
        description="High-level financial totals from the Reconciliation Summary block."
    )
    claims: List[Claim] = Field(
        ...,
        description="A comprehensive list of every patient claim extracted from the Claim Summary section."
    )
    adjustment_reason_codes: List[AdjustmentReasonCode] = Field(
        default_factory=list,
        description="All adjustment reason code definitions from the Adjustment Reason Codes section."
    )
    remark_codes: List[RemarkCode] = Field(
        default_factory=list,
        description="All remark code definitions from the Remark Codes section."
    )


SCHEMA_DESCRIPTION = """
### HIERARCHICAL ANALYSIS METHODOLOGY:
**CRITICAL**: Study each page's visual hierarchy in detail before extraction:
1. **Scan for Summary Blocks**: Locate PAYER INFORMATION, PAYMENT INFORMATION, and RECONCILIATION SUMMARY panels.
2. **Identify Claim Blocks**: Each claim block starts with 'Claim / Patient Account # X for PATIENT_NAME'.
3. **Analyze Claim Structure**:
   - **Header Row**: Patient Account # | Patient Name | Insured ID | Insured Name | Payer Claim # | Status
   - **Service Provider Row**: Service Provider NPI (qualifier) Provider Name
   - **Service Lines**: Every row between the column headers and the 'Total' row
   - **Total Row**: The 'Total' row at the bottom of each claim — map to `claim_totals`, NOT to `services`
4. **Multi-value Cells**: Some cells stack multiple values vertically (e.g., Payment shows two rows, Patient Responsibility shows two rows). Extract each value to the correct service line.
5. **Capture Code Tables**: Extract all rows from ADJUSTMENT REASON CODES and REMARK CODES tables.

### INSTAMED DOCUMENT STRUCTURE:

1. **PAYER INFORMATION BLOCK**:
   - Payer Name, Payer ID (qualifier), Payer Address.

2. **PAYMENT INFORMATION BLOCK**:
   - Payment Amount, Payment Date, Payment Method, Check/EFT Trace #.
   - Billing Provider Name, Billing Provider ID (qualifier), Billing Provider Address.
   - Version Identification.

3. **RECONCILIATION SUMMARY BLOCK**:
   - Total Charges, Total Patient Responsibility, Total Contractual Adjustments, Total Other Adjustments.
   - Total Claim Payment, Provider Adjustments, Payment Amount.

4. **CLAIM SUMMARY SECTION** (repeating per claim):
   - Patient Account #, Patient Name, Insured ID, Insured Name, Payer Claim #, Claim Status.
   - Service Provider NPI, qualifier, provider name.
   - **SERVICE LINE ITEMS**: Every data row before the 'Total' row.
     - begin_service_date, end_service_date, procedure_code, modifiers (from parentheses),
       num_of_units, amount_billed, allowed, payment, patient_responsibility,
       contractual_adjustments, other_adjustments, adjustment_reason (space-separated), remarks.
   - **TOTAL ROW**: MANDATORY — map to `claim_totals`. NEVER add to `services` list.

5. **ADJUSTMENT REASON CODES TABLE**: Extract all rows → `adjustment_reason_codes`.

6. **REMARK CODES TABLE**: Extract all rows → `remark_codes`.

### ZERO DATA LOSS RULES:
- Every claim MUST have `claim_totals`. Retrieve from the 'Total' row at the bottom of the claim block.
- Multi-row cells: When Payment or Patient Responsibility shows stacked values, split them across the correct service lines based on their vertical position.
- `adjustment_reason` must capture ALL codes on the line, space-separated (e.g., 'PR-3 CO-45').
- `adjustment_reason_codes` and `remark_codes` must be fully extracted — do not return empty lists if entries exist.
- `reconciliation_summary` is MANDATORY if the block is present.
"""


def build_instamed_payload(extracted_claims: list, merged_meta: dict) -> dict:
    return {
        "instamed_remittance_page": {
            "payer_information": merged_meta.get("payer_information"),
            "payment_information": merged_meta.get("payment_information"),
            "reconciliation_summary": merged_meta.get("reconciliation_summary"),
            "claims": extracted_claims,
            "adjustment_reason_codes": merged_meta.get("adjustment_reason_codes") or [],
            "remark_codes": merged_meta.get("remark_codes") or [],
        }
    }


def calculate_totals(claims_data: dict) -> dict:
    """Calculate format-specific totals for the final response."""
    total_billed = 0.0
    total_payment = 0.0
    total_patient_responsibility = 0.0

    page = claims_data.get("instamed_remittance_page", {})
    claims = page.get("claims", [])

    for claim in claims:
        services = claim.get("services", [])
        for svc in services:
            total_billed += float(svc.get("amount_billed") or 0)
            total_payment += float(svc.get("payment") or 0)
            total_patient_responsibility += float(svc.get("patient_responsibility") or 0)

    return {
        "total_billed": total_billed,
        "total_payment": total_payment,
        "total_patient_responsibility": total_patient_responsibility,
    }