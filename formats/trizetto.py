from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ServiceLineItem(BaseModel):
    """Represents an individual service line within a Trizetto remittance claim."""

    begin_service_date: Optional[str] = Field(
        None,
        description="Start date of the service in MM/DD/YYYY format (e.g., '6/24/2025')."
    )
    end_service_date: Optional[str] = Field(
        None,
        description="End date of the service in MM/DD/YYYY format. Usually the same as begin_service_date."
    )
    rendering_npi: Optional[str] = Field(
        None,
        description="NPI of the rendering provider for this service line (e.g., '1982334025')."
    )
    paid_units: Optional[int] = Field(
        None,
        description="Number of units paid for this service line. May be blank/null when not provided."
    )
    procedure_code: Optional[str] = Field(
        None,
        description="The CPT/HCPCS procedure or revenue code (e.g., '99203', '99213'). From 'Proc/Rev Code, Mods' column."
    )
    modifiers: Optional[str] = Field(
        None,
        description="Any procedure code modifiers from the 'Proc/Rev Code, Mods' column (e.g., 'GT', '25'). Separate multiple with a space."
    )
    billed_amount: Optional[float] = Field(
        None,
        description="Amount billed by the provider for this service line (e.g., 218.00)."
    )
    allowed_amount: Optional[float] = Field(
        None,
        description="Allowed/contractual amount for this service line (e.g., 0.00)."
    )
    deduct_amount: Optional[float] = Field(
        None,
        description="Deductible amount applied to this service line (e.g., 0.00)."
    )
    coins_amount: Optional[float] = Field(
        None,
        description="Co-insurance amount applied to this service line (e.g., 0.00)."
    )
    copay_amount: Optional[float] = Field(
        None,
        description="Co-pay amount applied to this service line (e.g., 0.00)."
    )
    late_filing_reduction: Optional[float] = Field(
        None,
        description="Reduction applied due to late filing (e.g., 0.00)."
    )
    other_adjustments: Optional[float] = Field(
        None,
        description="Other adjustment amount for this service line (e.g., 218.00, 148.00)."
    )
    adjustment_codes: Optional[str] = Field(
        None,
        description="All adjustment reason codes for this line (e.g., 'CO-109', 'CO-16'). Separate multiple with a space."
    )
    provider_paid: Optional[float] = Field(
        None,
        description="Net amount actually paid to the provider for this service line (e.g., 0.00)."
    )
    remark_codes: Optional[str] = Field(
        None,
        description="All remark codes for this service line (e.g., 'N105 N193 N704', 'MA27 N704 N382'). Separate multiple with a space."
    )

    @field_validator("modifiers", "adjustment_codes", "remark_codes", mode="before")
    @classmethod
    def convert_list_to_string(cls, v: Any) -> Any:
        if isinstance(v, list):
            return " ".join([str(i) for i in v if i is not None])
        return v


class Claim(BaseModel):
    """Represents a full claim for a single patient within a Trizetto remittance."""

    patient_name: Optional[str] = Field(
        None,
        description="Full name of the patient (e.g., 'FREDRICK JORDAN')."
    )
    member_identification_number: Optional[str] = Field(
        None,
        description="Patient's member identification number (e.g., '7MQ2UM7WD03')."
    )
    insured_name: Optional[str] = Field(
        None,
        description="Full name of the insured/subscriber (e.g., 'FREDRICK JORDAN')."
    )
    insured_member_identification_number: Optional[str] = Field(
        None,
        description="Insured member identification number. Often the same as member_identification_number (e.g., '7MQ2UM7WD03')."
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim identifier assigned by the provider/clearinghouse (e.g., '2506301952369')."
    )
    patient_account_number: Optional[str] = Field(
        None,
        description="Provider-assigned patient account number (e.g., '174127')."
    )
    claim_status: Optional[str] = Field(
        None,
        description="Processing status of the claim (e.g., 'Processed as Primary', 'Denied')."
    )
    rendering_provider: Optional[str] = Field(
        None,
        description="Name of the rendering provider. May be blank if not provided."
    )
    rendering_npi: Optional[str] = Field(
        None,
        description="NPI of the rendering provider at claim level (e.g., '1982334025', '1356638761')."
    )
    claim_payment_amount: Optional[float] = Field(
        None,
        description="Total amount paid by the payer for this claim (e.g., 0.00)."
    )
    claim_adjustment_amount: Optional[float] = Field(
        None,
        description="Claim-level adjustment amount, if any."
    )
    claim_adjustment_codes: Optional[str] = Field(
        None,
        description="Claim-level adjustment codes, if any. Separate multiple with a space."
    )
    claim_remark_codes: Optional[str] = Field(
        None,
        description="Claim-level remark codes (e.g., 'N105 N193 N704', 'MA27 N704 N382'). Separate multiple with a space."
    )
    payer_claim_control_number: Optional[str] = Field(
        None,
        description="Payer Internal Control Number / ICN# (e.g., '2225181234390')."
    )
    patient_responsibility: Optional[float] = Field(
        None,
        description="Total patient responsibility amount for this claim."
    )
    patient_responsibility_reason_code: Optional[str] = Field(
        None,
        description="Reason code for patient responsibility (e.g., 'PR-3'). Separate multiple with a space."
    )
    patient_group_number: Optional[str] = Field(
        None,
        description="Patient group/plan number. May be blank if not provided."
    )

    @field_validator(
        "claim_status", "claim_adjustment_codes", "claim_remark_codes",
        "patient_responsibility_reason_code", mode="before"
    )
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
    """Represents the grand TOTALS summary row at the bottom of the Trizetto remittance."""

    claim_adjustments: Optional[float] = Field(
        None,
        description="Total claim-level adjustments across all claims (e.g., 0.00)."
    )
    billed_amount: Optional[float] = Field(
        None,
        description="Total billed amount across all claims (e.g., 366.00)."
    )
    allowed_amount: Optional[float] = Field(
        None,
        description="Total allowed amount across all claims (e.g., 0.00)."
    )
    deduct_amount: Optional[float] = Field(
        None,
        description="Total deductible applied across all claims (e.g., 0.00)."
    )
    coins_amount: Optional[float] = Field(
        None,
        description="Total co-insurance applied across all claims (e.g., 0.00)."
    )
    copay_amount: Optional[float] = Field(
        None,
        description="Total co-pay applied across all claims (e.g., 0.00)."
    )
    late_filing_reduction: Optional[float] = Field(
        None,
        description="Total late filing reductions across all claims (e.g., 0.00)."
    )
    other_adjustments: Optional[float] = Field(
        None,
        description="Total other adjustments across all claims (e.g., 366.00)."
    )
    total_paid: Optional[float] = Field(
        None,
        description="Grand total paid by the payer across all claims (e.g., 0.00)."
    )


class AdjustmentCodeGlossaryEntry(BaseModel):
    """Represents a single entry from the Adjustment Codes Glossary section of a Trizetto remittance."""

    category: Optional[str] = Field(
        None,
        description=(
            "Named category grouping for this code as printed in the glossary "
            "(e.g., 'Additional Information Required – Missing/Invalid/Incomplete Data from Submitted Claim', "
            "'Billed Service Not Covered by Health Plan', 'Contractual Obligations'). "
            "Appears as a bold section heading above one or more codes."
        )
    )
    code: Optional[str] = Field(
        None,
        description="The adjustment or remark code (e.g., 'CO-16', 'CO-109', 'MA27', 'N105', 'N193', 'N382', 'N704')."
    )
    group: Optional[str] = Field(
        None,
        description="Group prefix indicating responsibility type (e.g., 'CO' for Contractual Obligations, 'N' for Remark/Alert)."
    )
    description: Optional[str] = Field(
        None,
        description="Full text description of the code as printed in the glossary."
    )
    start_date: Optional[str] = Field(
        None,
        description="Date this code became effective (e.g., '01/01/1995')."
    )
    last_modified_date: Optional[str] = Field(
        None,
        description="Date this code was last modified, if present (e.g., '11/01/2013')."
    )
    notes: Optional[str] = Field(
        None,
        description="Any additional notes printed alongside the code definition (e.g., '(Modified 2/28/03)')."
    )


class TrizettoRemittancePage(BaseModel):
    """The top-level model representing a single Trizetto Standard Remittance document."""

    payer_name: Optional[str] = Field(
        None,
        description="Name of the insurance payer (e.g., 'Medicare of Oregon')."
    )
    payer_address: Optional[str] = Field(
        None,
        description="Payer mailing address as printed on the document (e.g., '4510 13TH AVE S, FARGO, ND 58103')."
    )
    payee_name: Optional[str] = Field(
        None,
        description="Name of the practice/payee receiving the remittance (e.g., 'APPLE EYECARE PC')."
    )
    payee_address: Optional[str] = Field(
        None,
        description="Payee mailing address as printed on the document (e.g., '10709 S WALTON ROAD, ISLAND CITY, OR 978508490')."
    )
    provider_number: Optional[str] = Field(
        None,
        description="Provider number assigned by the payer (e.g., '1982334025')."
    )
    provider_tax_id: Optional[str] = Field(
        None,
        description="Provider federal tax identification number (e.g., '931321917')."
    )
    non_payment_number: Optional[str] = Field(
        None,
        description=(
            "Non-payment reference number when check amount is $0.00 (e.g., '323161261'). "
            "Appears in the field labeled 'Non-payment #' instead of EFT/Check #."
        )
    )
    npi_group_provider_number: Optional[str] = Field(
        None,
        description="NPI or Group Provider Number for the practice (e.g., '1538345269')."
    )
    check_date: Optional[str] = Field(
        None,
        description="Date of the check or remittance (e.g., '7/2/2025')."
    )
    created_date: Optional[str] = Field(
        None,
        description="Date the remittance was created (e.g., '7/1/2025')."
    )
    check_amount: Optional[float] = Field(
        None,
        description="Total check/EFT payment amount. May be $0.00 for denial/non-payment remittances (e.g., 0.00)."
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
        description="The grand 'TOTALS' summary row from the Check Totals section at the bottom of the remittance."
    )
    adjustment_code_glossary: List[AdjustmentCodeGlossaryEntry] = Field(
        default_factory=list,
        description=(
            "All adjustment and remark code definitions from the Adjustment Codes Glossary section. "
            "Includes codes grouped under named category headings."
        )
    )


SCHEMA_DESCRIPTION = """
### HIERARCHICAL ANALYSIS METHODOLOGY:
**CRITICAL**: Study the document's visual hierarchy before any extraction:
1. **Scan the Document Header**: Top block contains payer name/address, payee name/address,
   Provider #, Provider Tax ID #, Non-payment # (or EFT/Check #), NPI / Group Provider Number,
   Check Date, Created Date, Check Amount, Provider Adj Amt.
2. **Identify Claim Blocks**: Each claim block begins with a labeled header row:
   "Patient Name: ... Member Identification #: ..."
3. **Parse Claim Header Fields**: Extract all labeled fields above the service line table.
4. **Extract Service Lines**: Rows between the column header row and "SERVICE LINE TOTALS".
5. **Map SERVICE LINE TOTALS**: Always to `claim_totals` — never into the `services` list.
6. **Capture Check Totals**: The "TOTALS:" row in the Check Totals section → `check_totals`.
7. **Capture Glossary**: All entries under "Adjustment Codes Glossary" → `adjustment_code_glossary`.

### DOCUMENT STRUCTURE:

1. **DOCUMENT-LEVEL HEADER** (top of the first page):
   Fields (all labeled): Payer Name, Payer Address, Payee Name, Payee Address,
   Provider #, Provider Tax ID #, Non-payment # (or Check #/EFT #),
   NPI / Group Provider Number, Check Date, Created Date, Check Amount, Provider Adj Amt.
   - IMPORTANT: When check amount is $0.00, the reference field is labeled "Non-payment #"
     rather than "EFT #" or "Check #". Map this to `non_payment_number`.

2. **PATIENT CLAIM BLOCKS** (repeating):
   Header fields (all labeled):
   - Patient Name, Member Identification #
   - Insured Name, Insured Member Identification #
   - Claim ID, Patient Account Number
   - Claim Status (e.g., "Processed as Primary", "Denied")
   - Rendering Provider (may be blank), Rendering NPI
   - Claim Payment Amount, Claim Adj Amt
   - Claim Adj Codes, Payer Claim Control # / ICN#
   - Claim Remark Codes (comma-separated, e.g., "N105,N193,N704")
   - Patient Responsibility, Patient Responsibility Reason Code
   - Patient Group#

   **SERVICE LINE TABLE** columns (left to right):
   Begin Service Date | End Service Date | Rendering NPI | Paid Units |
   Proc/Rev Code, Mods | Billed Amount | Allowed Amount | Deduct Amount |
   CoIns Amount | CoPay Amount | Late Filing Red. | Other Adjusts |
   Adjust Codes | Provider Paid | Remark Codes

   - `paid_units`: May be absent — leave null if not present.
   - `procedure_code`: The base code from the "Proc/Rev Code, Mods" column (e.g., '99203').
   - `modifiers`: Any modifier appended after the code in the same column.
   - `remark_codes`: May span multiple lines with comma separation — join all as space-separated string.

   **SERVICE LINE TOTALS** row: MANDATORY — map to `claim_totals`. NEVER add to `services`.

3. **CHECK TOTALS SECTION**:
   Columns: Claim Adjustments | Billed Amount | Allowed Amount | Deduct Amount |
   CoIns Amount | CoPay Amount | Late Filing Red. | Other Adjustments | Total Paid
   Map the "TOTALS:" row to `check_totals`.

4. **ADJUSTMENT CODES GLOSSARY** (bottom of document, may span multiple pages):
   - Codes are grouped under bold category headings
     (e.g., "Additional Information Required...", "Billed Service Not Covered...").
   - Each entry has: code, description, Start date, Last Modified date, Notes.
   - Extract the category heading that applies to each code into the `category` field.
   - Group prefix ('CO', 'MA', 'N') goes into the `group` field.

### ZERO DATA LOSS RULES:
- Every claim MUST have `claim_totals`. Retrieve from the "SERVICE LINE TOTALS" row.
- `claim_remark_codes` on the claim header: join comma-separated codes into a space-separated string.
- `remark_codes` on service lines: join comma-separated codes into a space-separated string.
- `adjustment_codes` must capture ALL codes on each service line, space-separated.
- `check_totals` is MANDATORY when a "TOTALS:" row exists in the Check Totals section.
- `adjustment_code_glossary` must be fully extracted including all pages — do not return an empty list.
- `non_payment_number` must be populated when the header shows "Non-payment #" instead of "EFT #".
- `claim_status` can be "Processed as Primary", "Denied", or other values — capture exactly as printed.
"""


def build_trizetto_payload(extracted_claims: list, merged_meta: dict) -> dict:
    return {
        "trizetto_remittance_page": {
            "payer_name": merged_meta.get("payer_name"),
            "payer_address": merged_meta.get("payer_address"),
            "payee_name": merged_meta.get("payee_name"),
            "payee_address": merged_meta.get("payee_address"),
            "provider_number": merged_meta.get("provider_number"),
            "provider_tax_id": merged_meta.get("provider_tax_id"),
            "non_payment_number": merged_meta.get("non_payment_number"),
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

    page = claims_data.get("trizetto_remittance_page", {})
    claims = page.get("claims", [])

    for claim in claims:
        for svc in claim.get("services", []):
            total_billed += float(svc.get("billed_amount") or 0)
            total_paid += float(svc.get("provider_paid") or 0)
            total_patient_responsibility += float(svc.get("copay_amount") or 0)

    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_patient_responsibility": total_patient_responsibility,
    }