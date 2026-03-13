import sys
import os
import logging
from typing import List, Optional

# Ensure current directory is in path
sys.path.append(os.getcwd())

from agents.format_generator_agent import FormatGeneratorAgent
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_retry_logic():
    print("\n--- Testing FormatGeneratorAgent Retry Logic ---")
    
    # Initialize with real keys (but we will mock the actual API call)
    agent = FormatGeneratorAgent(
        anthropic_key=config.ANTHROPIC_API_KEY,
        gemini_key=config.GEMINI_API_KEY
    )
    
    # Mock the internal generation methods
    original_claude = agent._generate_with_claude
    
    call_count = 0
    
    def mock_claude(pdf_images, short_name, system_prompt, model_name, feedback_prompt=None):
        nonlocal call_count
        call_count += 1
        print(f"Call {call_count}: Feedback provided: {bool(feedback_prompt)}")
        
        if call_count == 1:
            # Return code with syntax error
            return "class BatchModel: \n    invalid code["
        elif call_count == 2:
            # Return code missing required components
            return "class BatchModel: pass\ndef map_extracted_data(): pass"
        else:
            # Return valid code
            return """
class BatchModel: pass
class ClaimModel: pass
def map_extracted_data(claims, metadata): return {}
SCHEMA_DESCRIPTION = "Test schema"
def calculate_totals(data): return data
def section_builder(data): return data
"""

    agent._generate_with_claude = mock_claude
    
    try:
        print("\nStarting generation with simulated failures...")
        code = agent.generate_format([], "retry_test", provider="claude")
        
        if call_count == 3:
            print(f"SUCCESS: Agent retried {call_count-1} times and finally succeeded.")
            print("Final code validation passed.")
        else:
            print(f"FAILURE: Expected 3 calls, but got {call_count}.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        agent._generate_with_claude = original_claude

if __name__ == "__main__":
    test_retry_logic()
