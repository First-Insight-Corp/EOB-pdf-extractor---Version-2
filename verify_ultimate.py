import requests
import json
import time
import os

def test_ultimate_extraction(file_path, doc_type="vsp"):
    url = "http://localhost:8040/api/v1/process-pdf"
    
    print(f"Testing ULTIMATE extraction for: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
        data = {'document_type': doc_type}
        
        try:
            # Increased timeout for Reasoning Agent
            response = requests.post(url, files=files, data=data, timeout=600)
            
            if response.status_code == 200:
                result = response.json()
                print("SUCCESS: Extraction complete.")
                
                # Check for metadata and claims
                claims = result['data']['vsp_remittance_page'].get('claims', [])
                metadata = result['data']['vsp_remittance_page']
                
                print(f"Extracted {len(claims)} claims.")
                print(f"Header Check - Number: {metadata.get('check_number')}, Date: {metadata.get('check_date')}")
                
                with open("ultimate_test_result.json", "w") as out:
                    json.dump(result, out, indent=2)
                print("Results saved to ultimate_test_result.json")
            else:
                print(f"FAILED: Status {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_ultimate_extraction(r"d:\8 - EOB agentic solution\Backups\050225 - full working backup\pdfs\VSP - 4pages.pdf")
