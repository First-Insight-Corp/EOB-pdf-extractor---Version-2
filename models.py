from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

# VSP Models
class VSPClaim(BaseModel):
    """Individual VSP claim structure"""
    claim_number: str = Field(description="Unique claim identifier")
    patient_name: str = Field(description="Patient full name")
    patient_id: Optional[str] = Field(default=None, description="Patient ID or member number")
    date_of_service: str = Field(description="Date when service was provided")
    provider_name: str = Field(description="Healthcare provider name")
    provider_id: Optional[str] = Field(default=None, description="Provider identification number")
    service_description: str = Field(description="Description of service provided")
    procedure_code: Optional[str] = Field(default=None, description="CPT or procedure code")
    billed_amount: float = Field(description="Amount billed by provider")
    allowed_amount: float = Field(description="Amount allowed by insurance")
    paid_amount: float = Field(description="Amount paid by insurance")
    patient_responsibility: float = Field(description="Amount patient owes")
    claim_status: str = Field(description="Status of the claim (Paid, Pending, Denied, etc.)")
    denial_reason: Optional[str] = Field(default=None, description="Reason for denial if applicable")
    processed_date: Optional[str] = Field(default=None, description="Date claim was processed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "claim_number": "VSP123456789",
                "patient_name": "John Doe",
                "patient_id": "VSP987654",
                "date_of_service": "2024-01-15",
                "provider_name": "Vision Care Center",
                "provider_id": "PRV12345",
                "service_description": "Comprehensive Eye Exam",
                "procedure_code": "92004",
                "billed_amount": 150.00,
                "allowed_amount": 120.00,
                "paid_amount": 100.00,
                "patient_responsibility": 20.00,
                "claim_status": "Paid",
                "denial_reason": None,
                "processed_date": "2024-01-20"
            }
        }

class VSPResponse(BaseModel):
    """Complete VSP document response structure"""
    document_type: str = Field(default="VSP", description="Type of document")
    total_claims: int = Field(description="Total number of claims in document")
    claims: List[VSPClaim] = Field(description="List of all claims")
    total_billed: float = Field(description="Sum of all billed amounts")
    total_paid: float = Field(description="Sum of all paid amounts")
    total_patient_responsibility: float = Field(description="Sum of all patient responsibilities")
    processing_notes: Optional[str] = Field(default=None, description="Any processing notes or warnings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "VSP",
                "total_claims": 1,
                "claims": [],
                "total_billed": 150.00,
                "total_paid": 100.00,
                "total_patient_responsibility": 20.00,
                "processing_notes": "All claims processed successfully"
            }
        }


# EyeMed Models
class EyeMedClaim(BaseModel):
    """Individual EyeMed claim structure"""
    claim_id: str = Field(description="Unique claim identifier")
    member_name: str = Field(description="Member full name")
    member_number: str = Field(description="Member identification number")
    group_number: Optional[str] = Field(default=None, description="Group identification number")
    service_date: str = Field(description="Date of service")
    provider_name: str = Field(description="Provider name")
    provider_npi: Optional[str] = Field(default=None, description="Provider NPI number")
    service_type: str = Field(description="Type of service (Exam, Materials, Lenses, Frames, etc.)")
    procedure_codes: Optional[List[str]] = Field(default=None, description="List of procedure codes")
    charge_amount: float = Field(description="Total charge amount")
    copay_amount: float = Field(description="Copay amount")
    plan_paid: float = Field(description="Amount paid by plan")
    member_paid: float = Field(description="Amount paid by member")
    discount_amount: Optional[float] = Field(default=None, description="Discount applied")
    status: str = Field(description="Claim status")
    remarks: Optional[str] = Field(default=None, description="Additional remarks or notes")
    check_number: Optional[str] = Field(default=None, description="Check number if payment made")
    payment_date: Optional[str] = Field(default=None, description="Payment date")
    
    class Config:
        json_schema_extra = {
            "example": {
                "claim_id": "EM987654321",
                "member_name": "Jane Smith",
                "member_number": "EM123456789",
                "group_number": "GRP12345",
                "service_date": "2024-02-10",
                "provider_name": "Eye Care Specialists",
                "provider_npi": "1234567890",
                "service_type": "Comprehensive Exam",
                "procedure_codes": ["92014"],
                "charge_amount": 175.00,
                "copay_amount": 10.00,
                "plan_paid": 140.00,
                "member_paid": 35.00,
                "discount_amount": 0.00,
                "status": "Processed",
                "remarks": None,
                "check_number": "CHK789456",
                "payment_date": "2024-02-15"
            }
        }

class EyeMedResponse(BaseModel):
    """Complete EyeMed document response structure"""
    document_type: str = Field(default="EyeMed", description="Type of document")
    statement_period: Optional[str] = Field(default=None, description="Statement period")
    total_claims_count: int = Field(description="Total number of claims")
    claims: List[EyeMedClaim] = Field(description="List of all claims")
    total_charges: float = Field(description="Sum of all charge amounts")
    total_plan_paid: float = Field(description="Sum of all plan payments")
    total_member_responsibility: float = Field(description="Sum of all member responsibilities")
    processing_summary: Optional[str] = Field(default=None, description="Processing summary notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "EyeMed",
                "statement_period": "January 2024",
                "total_claims_count": 1,
                "claims": [],
                "total_charges": 175.00,
                "total_plan_paid": 140.00,
                "total_member_responsibility": 35.00,
                "processing_summary": "All claims processed without issues"
            }
        }
