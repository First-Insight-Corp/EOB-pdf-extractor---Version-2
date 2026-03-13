import requests
import json
import os

def test_extraction():
    url = "http://localhost:8000/api/v1/process-pdf"
    pdf_path = r"d:\8 - EOB agentic solution\Backups\050225 - full working backup\pdfs\VSP - 4pages.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"document_type": "vsp"}
        
        print(f"Processing {pdf_path} (this may take several minutes due to verification loops)...")
        try:
            response = requests.post(url, files=files, data=data, timeout=600) # 10 minute timeout
        except requests.exceptions.Timeout:
            print("Error: Request timed out after 10 minutes")
            return
        except Exception as e:
            print(f"Error during request: {e}")
            return
        
    if response.status_code == 200:
        result = response.json()
        print("Success!")
        # Check for service_date and procedure_code
        data = result.get('data', {})
        claims = data.get('vsp_remittance_page', {}).get('claims', [])
        
        missing_dates = [c.get('patient_name') for c in claims if not c.get('service_date')]
        missing_procs = []
        for c in claims:
            for s in c.get('services', []):
                if not s.get('procedure_code'):
                    missing_procs.append(f"{c.get('patient_name')} - {s.get('description')}")
        
        print(f"Total Claims: {len(claims)}")
        print(f"Claims missing service_date: {len(missing_dates)}")
        if missing_dates: print(f"  {missing_dates}")
        
        print(f"Services missing procedure_code: {len(missing_procs)}")
        if missing_procs: print(f"  {missing_procs}")
        
        with open("test_result_summary.json", "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_extraction()
