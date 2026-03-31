#!/usr/bin/env python3
"""
Test script for PDF Claims Extraction API
Demonstrates how to use the API endpoints
"""

import requests
import json
import os
from typing import Literal

class PDFClaimsAPIClient:
    """Client for interacting with PDF Claims Extraction API"""
    
    def __init__(self, base_url: str = "http://localhost:8040"):
        self.base_url = base_url
    
    def health_check(self) -> dict:
        """Check API health status"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def process_pdf(self, pdf_path: str, document_type: Literal["vsp", "eyemed"]) -> dict:
        """
        Process a PDF file and extract claims.
        
        Args:
            pdf_path: Path to the PDF file
            document_type: Type of document ("vsp" or "eyemed")
        
        Returns:
            API response with extracted claims
        """
        url = f"{self.base_url}/api/v1/process-pdf"
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        with open(pdf_path, "rb") as f:
            files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
            data = {"document_type": document_type}
            
            print(f"📤 Uploading {os.path.basename(pdf_path)}...")
            print(f"📋 Document Type: {document_type.upper()}")
            
            response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            error = response.json()
            raise Exception(f"API Error: {error.get('detail', 'Unknown error')}")
    
    def list_responses(self) -> dict:
        """List all saved response files"""
        response = requests.get(f"{self.base_url}/api/v1/responses")
        return response.json()
    
    def get_response(self, filename: str) -> dict:
        """Get a specific response file"""
        response = requests.get(f"{self.base_url}/api/v1/response/{filename}")
        return response.json()


def print_result_summary(result: dict):
    """Print a formatted summary of the extraction result"""
    print("\n" + "="*70)
    print("✅ EXTRACTION SUCCESSFUL")
    print("="*70)
    
    doc_info = result.get("document_info", {})
    data = result.get("data", {})
    metadata = result.get("processing_metadata", {})
    
    print(f"\n📄 Document Information:")
    print(f"   Filename: {doc_info.get('filename')}")
    print(f"   Type: {doc_info.get('type')}")
    print(f"   Total Pages: {doc_info.get('total_pages')}")
    print(f"   Batches Processed: {doc_info.get('batches_processed')}")
    
    print(f"\n📊 Extraction Results:")
    print(f"   Total Claims: {data.get('total_claims', data.get('total_claims_count', 0))}")
    
    if data.get('document_type') == 'VSP':
        print(f"   Total Billed: ${data.get('total_billed', 0):.2f}")
        print(f"   Total Paid: ${data.get('total_paid', 0):.2f}")
        print(f"   Patient Responsibility: ${data.get('total_patient_responsibility', 0):.2f}")
    else:  # EyeMed
        print(f"   Total Charges: ${data.get('total_charges', 0):.2f}")
        print(f"   Total Plan Paid: ${data.get('total_plan_paid', 0):.2f}")
        print(f"   Member Responsibility: ${data.get('total_member_responsibility', 0):.2f}")
    
    print(f"\n💾 Response File: {result.get('response_file')}")
    print(f"\n⚙️  Processing Details:")
    print(f"   Conversation Turns: {metadata.get('conversation_turns')}")
    print(f"   Claims Extracted: {metadata.get('claims_extracted')}")
    print(f"   Timestamp: {metadata.get('timestamp')}")
    
    print("\n" + "="*70)
    
    # Print first few claims as examples
    claims = data.get('claims', [])
    if claims:
        print(f"\n📋 Sample Claims (showing first 3 of {len(claims)}):\n")
        for i, claim in enumerate(claims[:3], 1):
            print(f"   Claim {i}:")
            if data.get('document_type') == 'VSP':
                print(f"      • Claim Number: {claim.get('claim_number')}")
                print(f"      • Patient: {claim.get('patient_name')}")
                print(f"      • Service: {claim.get('service_description')}")
                print(f"      • Date: {claim.get('date_of_service')}")
                print(f"      • Status: {claim.get('claim_status')}")
                print(f"      • Paid: ${claim.get('paid_amount', 0):.2f}")
            else:  # EyeMed
                print(f"      • Claim ID: {claim.get('claim_id')}")
                print(f"      • Member: {claim.get('member_name')}")
                print(f"      • Service: {claim.get('service_type')}")
                print(f"      • Date: {claim.get('service_date')}")
                print(f"      • Status: {claim.get('status')}")
                print(f"      • Plan Paid: ${claim.get('plan_paid', 0):.2f}")
            print()


def main():
    """Main test function"""
    print("="*70)
    print("PDF CLAIMS EXTRACTION API - TEST SCRIPT")
    print("="*70)
    
    # Initialize client
    client = PDFClaimsAPIClient()
    
    # Test 1: Health Check
    print("\n🏥 Testing Health Check...")
    try:
        health = client.health_check()
        print(f"   Status: {health.get('status')}")
        print(f"   Gemini API Configured: {health.get('gemini_api_configured')}")
        
        if not health.get('gemini_api_configured'):
            print("\n⚠️  WARNING: Gemini API key not configured!")
            print("   Please set GEMINI_API_KEY in your .env file")
            return
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        print("   Make sure the server is running: python main.py")
        return
    
    # Test 2: Process PDF
    print("\n📄 Testing PDF Processing...")
    print("\nTo test PDF processing, use one of these methods:\n")
    
    # Example 1: Direct file path
    print("Method 1: Direct Python call")
    print("-" * 40)
    print("""
    client = PDFClaimsAPIClient()
    result = client.process_pdf(
        pdf_path="/path/to/your/claims.pdf",
        document_type="vsp"  # or "eyemed"
    )
    print_result_summary(result)
    """)
    
    # Example 2: cURL command
    print("\nMethod 2: Using cURL")
    print("-" * 40)
    print("""
        curl -X POST "http://localhost:8040/api/v1/process-pdf" \\
      -F "file=@/path/to/your/claims.pdf" \\
      -F "document_type=vsp"
    """)
    
    # Example 3: Interactive test
    print("\nMethod 3: Interactive Test")
    print("-" * 40)
    pdf_path = input("Enter path to PDF file (or press Enter to skip): ").strip()
    
    if pdf_path and os.path.exists(pdf_path):
        doc_type = input("Enter document type (vsp/eyemed): ").strip().lower()
        
        if doc_type in ["vsp", "eyemed"]:
            try:
                result = client.process_pdf(pdf_path, doc_type)
                print_result_summary(result)
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
        else:
            print("❌ Invalid document type. Use 'vsp' or 'eyemed'")
    else:
        print("⏭️  Skipping PDF processing test")
    
    # Test 3: List Responses
    print("\n📁 Testing List Responses...")
    try:
        responses = client.list_responses()
        total = responses.get('total_responses', 0)
        print(f"   Total saved responses: {total}")
        
        if total > 0:
            print("\n   Recent responses:")
            for resp in responses.get('responses', [])[:5]:
                print(f"      • {resp['filename']}")
                print(f"        Type: {resp['document_type']}, Size: {resp['size_bytes']} bytes")
    except Exception as e:
        print(f"   ⚠️  Could not list responses: {str(e)}")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
    print("\nAPI Documentation: http://localhost:8040/docs")
    print("Health Check: http://localhost:8040/health")
    print("\n")


if __name__ == "__main__":
    main()
