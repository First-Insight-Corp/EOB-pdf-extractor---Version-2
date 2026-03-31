import google.generativeai as genai
import os

api_key = "AIzaSyCMYBky3ltI-JYBcB7unFw0X9tWwdTX2VI"
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash") # Use a cheaper model for test

print("Checking generate_content with timeout...")
try:
    # Try passing timeout directly as a kwarg
    response = model.generate_content("Say hello", timeout=10)
    print("Direct timeout kwarg worked!")
except Exception as e:
    print(f"Direct timeout kwarg failed: {e}")

try:
    # Try passing request_options as a kwarg
    response = model.generate_content("Say hello", request_options={"timeout": 10})
    print("request_options worked!")
except Exception as e:
    print(f"request_options failed: {e}")
