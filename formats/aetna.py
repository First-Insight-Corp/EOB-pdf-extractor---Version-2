from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ServiceLineItem(BaseModel):
    """
    Represents an individual service line within a UnitedHealthCare claim.
    """

    begin_service_date: Optional[str] = Field(
        None,
        description="Start date of the service in MM/DD/YYYY format (e.g., '12/22/2025')."
    )
    end_service_date: Optional[str] = Field(
        None,
        description="End date of the service in MM/DD/YYYY format. Usually the same as begin_service_date."
    )
    rendering_npi: Optional[str] = Field(
        None,
        description="The NPI of the rendering provider for this specific service line."
    )
    paid_units: Optional[int] = Field(
        None,
        description="Number of units paid for this service line (e.g., 1)."
    )
    procedure_code: Optional[str] = Field(
        None,
        description="The CPT/HCPCS procedure code (e.g., '92014', '92015', '92133')."
    )
    modifiers: Optional[str] = Field(
        None,
        description="Any procedure code modifiers (e.g., 'RT', 'LT'). Separate multiple with a space."
    )
    billed_amount: Optional[float] = Field(
        None,
        description="Amount billed by the provider for this service line."
    )
    allowed_amount: Optional[float] = Field(
        None,
        description="Allowed/contractual amount for this service line per fee schedule."
    )
    deduct_amount: Optional[float] = Field(
        None,
        description="Deductible amount applied to this service line."
    )
    coins_amount: Optional[float] = Field(
        None,
        description="Co-insurance amount applied to this service line."
    )
    copay_amount: Optional[float] = Field(
        None,
        description="Co-pay amount applied to this service line (patient responsibility)."
    )
    late_filing_reduction: Optional[float] = Field(
        None,
        description="Any reduction applied due to late filing."
    )
    other_adjustments: Optional[float] = Field(
        None,
        description="Sum of all other adjustment amounts (e.g., CO-253 sequestration + CO-45 contractual)."
    )
    adjustment_codes: Optional[str] = Field(
        None,
        description="All adjustment reason codes for this line (e.g., 'CO-253 CO-45'). Separate multiple with a space."
    )
    provider_paid: Optional[float] = Field(
        None,
        description="Net amount actually paid to the provider for this service line."
    )
    remark_codes: Optional[str] = Field(
        None,
        description="Any remark codes associated with this service line. Separate multiple with a space."
    )

    @field_validator("modifiers", "adjustment_codes", "remark_codes", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v


class Claim(BaseModel):
    """
    Represents a full claim for a single patient within a UnitedHealthCare remittance.
    """

    patient_name: Optional[str] = Field(
        None,
        description="Full name of the patient (e.g., 'CATHERINE A BATSCHELET')."
    )
    member_identification_number: Optional[str] = Field(
        None,
        description="The patient's member identification number (e.g., '949522733')."
    )
    insured_name: Optional[str] = Field(
        None,
        description="Full name of the insured/subscriber. May differ from patient name."
    )
    insured_member_identification_number: Optional[str] = Field(
        None,
        description="Insured member identification number. Often the same as member_identification_number."
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim identifier assigned by the payer (e.g., '251223536202')."
    )
    patient_account_number: Optional[str] = Field(
        None,
        description="Provider-assigned patient account number (e.g., '147793521')."
    )
    claim_status: Optional[str] = Field(
        None,
        description="Processing status of the claim (e.g., 'Processed as Primary')."
    )
    rendering_provider: Optional[str] = Field(
        None,
        description="Name of the rendering provider (e.g., 'CHRISTIAN SWENBY')."
    )
    rendering_npi: Optional[str] = Field(
        None,
        description="NPI of the rendering provider at the claim level (e.g., '1447336474')."
    )
    payer_claim_control_number: Optional[str] = Field(
        None,
        description="Payer's Internal Control Number / ICN# (e.g., 'OEB0711342000')."
    )
    claim_payment_amount: Optional[float] = Field(
        None,
        description="Total amount paid by the payer for this claim."
    )
    claim_adjustment_amount: Optional[float] = Field(
        None,
        description="Total claim-level adjustment amount, if any."
    )
    claim_adjustment_codes: Optional[str] = Field(
        None,
        description="Claim-level adjustment codes, if any. Separate multiple with a space."
    )
    claim_remark_codes: Optional[str] = Field(
        None,
        description="Claim-level remark codes, if any. Separate multiple with a space."
    )
    patient_responsibility: Optional[float] = Field(
        None,
        description="Total amount the patient is responsible for across the claim."
    )
    patient_responsibility_reason_code: Optional[str] = Field(
        None,
        description="Reason code explaining the patient responsibility (e.g., 'PR-3' for co-payment)."
    )
    patient_group_number: Optional[str] = Field(
        None,
        description="The patient's group/plan number (e.g., '15743')."
    )

    @field_validator("claim_adjustment_codes", "claim_remark_codes",
                     "patient_responsibility_reason_code", mode="before")
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
            "The 'SERVICE LINE TOTALS' summary row for this claim. "
            "MANDATORY: Map the totals row here — do NOT include it in the services list."
        )
    )


class ClaimModel(Claim):
    """Standardized naming for the main repeating entity."""
    pass


class CheckTotals(BaseModel):
    """
    Represents the grand total summary row at the bottom of the remittance.
    """

    billed_amount: Optional[float] = Field(None, description="Total billed amount across all claims.")
    allowed_amount: Optional[float] = Field(None, description="Total allowed amount across all claims.")
    deduct_amount: Optional[float] = Field(None, description="Total deductible applied across all claims.")
    coins_amount: Optional[float] = Field(None, description="Total co-insurance applied across all claims.")
    copay_amount: Optional[float] = Field(None, description="Total co-pay applied across all claims.")
    late_filing_reduction: Optional[float] = Field(None, description="Total late filing reduction across all claims.")
    other_adjustments: Optional[float] = Field(None, description="Total other adjustments across all claims.")
    total_paid: Optional[float] = Field(None, description="Grand total paid by the payer across all claims.")


class AdjustmentCodeGlossaryEntry(BaseModel):
    """
    Represents a single entry from the Adjustment Codes Glossary section.
    """

    code: Optional[str] = Field(None, description="The adjustment/remark code (e.g., 'CO-45', 'PR-3').")
    group: Optional[str] = Field(None, description="Group prefix (e.g., 'CO' for Contractual Obligations, 'PR' for Patient Responsibility).")
    description: Optional[str] = Field(None, description="Full text description of the code.")
    start_date: Optional[str] = Field(None, description="Date this code became effective (e.g., '01/01/1995').")
    last_modified_date: Optional[str] = Field(None, description="Date this code was last modified, if present.")


class UHCRemittancePage(BaseModel):
    """
    The top-level model representing a single UnitedHealthCare Standard Remittance document.
    """

    payer_name: Optional[str] = Field(
        None,
        description="Name of the insurance payer (e.g., 'United HealthCare of all states')."
    )
    payer_address: Optional[str] = Field(
        None,
        description="Payer mailing address as it appears on the document."
    )
    payee_name: Optional[str] = Field(
        None,
        description="Name of the practice/payee receiving the payment (e.g., 'VISUALEYES LLC')."
    )
    payee_address: Optional[str] = Field(
        None,
        description="Payee mailing address as it appears on the document."
    )
    provider_number: Optional[str] = Field(
        None,
        description="Provider number assigned by the payer (e.g., '1760554729')."
    )
    provider_tax_id: Optional[str] = Field(
        None,
        description="Provider federal tax identification number (e.g., '830365527')."
    )
    eft_number: Optional[str] = Field(
        None,
        description="Electronic Funds Transfer reference number (e.g., 'U6611455')."
    )
    npi_group_provider_number: Optional[str] = Field(
        None,
        description="NPI or Group Provider Number for the practice (e.g., '1922147503')."
    )
    check_date: Optional[str] = Field(
        None,
        description="Date the check/EFT was issued (e.g., '1/16/2026')."
    )
    created_date: Optional[str] = Field(
        None,
        description="Date the remittance was created (e.g., '1/14/2026')."
    )
    check_amount: Optional[float] = Field(
        None,
        description="Total check/EFT payment amount (e.g., 261.64)."
    )
    provider_adjustment_amount: Optional[float] = Field(
        None,
        description="Provider-level adjustment amount (e.g., 0.00)."
    )
    claims: List[Claim] = Field(
        ...,
        description="A comprehensive list of every patient claim extracted from the document."
    )
    check_totals: Optional[CheckTotals] = Field(
        None,
        description="The grand 'TOTALS' summary row at the bottom of the remittance."
    )
    adjustment_code_glossary: List[AdjustmentCodeGlossaryEntry] = Field(
        default_factory=list,
        description="All adjustment and remark code definitions from the glossary section."
    )


SCHEMA_DESCRIPTION = """
### HIERARCHICAL ANALYSIS METHODOLOGY:
**CRITICAL**: Study each page's visual hierarchy in detail before extraction:
1. **Scan for Document Header**: Top section contains payer name, payee name, EFT #, check date, check amount.
2. **Identify Claim Blocks**: Each patient block starts with Patient Name / Member ID header rows.
3. **Analyze Vertical Stacking**:
   - **Header Rows**: Patient Name | Member ID | Insured Name | Claim ID | Patient Account # | Claim Status
   - **Service Lines**: Rows between the claim header and SERVICE LINE TOTALS
   - **Totals Row**: The SERVICE LINE TOTALS row — map to `claim_totals`, NOT to `services`
4. **Capture Check Totals**: The grand TOTALS row at the bottom maps to `check_totals`.
5. **Capture Glossary**: All adjustment/remark code definitions map to `adjustment_code_glossary`.

### UHC DOCUMENT STRUCTURE:

1. **DOCUMENT-LEVEL HEADER**:
   - Payer name, payer address, payee name, payee address.
   - Provider #, Provider Tax ID #, EFT #, NPI / Group Provider Number.
   - Check Date, Created Date, Check Amount, Provider Adj Amt.

2. **PATIENT CLAIM BLOCKS**:
   - Patient Name, Member Identification #, Insured Name, Insured Member Identification #.
   - Claim ID, Patient Account Number, Claim Status, Rendering Provider, Rendering NPI.
   - Payer Claim Control # / ICN#, Claim Payment Amount, Patient Responsibility, Patient Group #.
   - **SERVICE LINE ITEMS**: Every row between the claim header and SERVICE LINE TOTALS.
     - begin_service_date, end_service_date, rendering_npi, paid_units, procedure_code, modifiers,
       billed_amount, allowed_amount, deduct_amount, coins_amount, copay_amount,
       late_filing_reduction, other_adjustments (sum of all adjustment dollar amounts on the line),
       adjustment_codes (space-separated e.g. 'CO-253 CO-45'), provider_paid, remark_codes.
   - **SERVICE LINE TOTALS**: MANDATORY — map to `claim_totals`. NEVER add to `services` list.

3. **CHECK TOTALS**: Grand TOTALS row at document bottom — map to `check_totals`.

4. **ADJUSTMENT CODE GLOSSARY**: All code entries at the end of the document — map to `adjustment_code_glossary`.

### ZERO DATA LOSS RULES:
- Every claim MUST have `claim_totals`. Retrieve from SERVICE LINE TOTALS row.
- `other_adjustments` per service line = sum of ALL individual adjustment dollar amounts on that line.
- `adjustment_codes` must capture ALL codes on the line, space-separated.
- `check_totals` is MANDATORY if a TOTALS row exists at the document level.
- `adjustment_code_glossary` must be fully extracted — do not return an empty list if entries exist.
"""


def build_uhc_payload(extracted_claims: list, merged_meta: dict) -> dict:
    return {
        "uhc_remittance_page": {
            "payer_name": merged_meta.get("payer_name"),
            "payer_address": merged_meta.get("payer_address"),
            "payee_name": merged_meta.get("payee_name"),
            "payee_address": merged_meta.get("payee_address"),
            "provider_number": merged_meta.get("provider_number"),
            "provider_tax_id": merged_meta.get("provider_tax_id"),
            "eft_number": merged_meta.get("eft_number"),
            "npi_group_provider_number": merged_meta.get("npi_group_provider_number"),
            "check_date": merged_meta.get("check_date"),
            "created_date": merged_meta.get("created_date"),
            "check_amount": merged_meta.get("check_amount"),
            "provider_adjustment_amount": merged_meta.get("provider_adjustment_amount"),
            "claims": extracted_claims,
            "check_totals": merged_meta.get("check_totals"),
            "adjustment_code_glossary": merged_meta.get("adjustment_code_glossary") or [],
        }
    }


def calculate_totals(claims_data: dict) -> dict:
    """Calculate format-specific totals for the final response."""
    total_billed = 0.0
    total_paid = 0.0
    total_patient_responsibility = 0.0

    page = claims_data.get("uhc_remittance_page", {})
    claims = page.get("claims", [])

    for claim in claims:
        services = claim.get("services", [])
        for svc in services:
            total_billed += float(svc.get("billed_amount") or 0)
            total_paid += float(svc.get("provider_paid") or 0)
            total_patient_responsibility += float(svc.get("copay_amount") or 0)

    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_patient_responsibility": total_patient_responsibility,
    }