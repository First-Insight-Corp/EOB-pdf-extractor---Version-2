import sys
import os
import logging
import base64

# Ensure current directory is in path
sys.path.append(os.getcwd())

from agents.format_generator_agent import FormatGeneratorAgent
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_agent_logic():
    print("\n--- Testing FormatGeneratorAgent Enhancements ---")
    
    # Initialize with mock/real keys
    agent = FormatGeneratorAgent(
        anthropic_key=config.ANTHROPIC_API_KEY,
        gemini_key=config.GEMINI_API_KEY
    )
    
    # 1. Test Prompt Building with Azure Text
    print("\n1. Testing System Prompt with Azure Context...")
    azure_text = "DUMMY AZURE DATA: TABLE CONTENT RECORD 1"
    prompt = agent._build_system_prompt("test_fmt", azure_text=azure_text)
    
    if "HIGH-QUALITY OCR & TABLE DATA" in prompt and azure_text in prompt:
        print("SUCCESS: Azure context correctly included in system prompt.")
    else:
        print("FAILURE: Azure context missing from prompt.")
        print(f"Prompt start: {prompt[:200]}")

    # 2. Test model switching logic (without making network calls)
    print("\n2. Testing Provider Switching Logic...")
    
    # We can mock the internal methods to see if they are called
    original_claude = agent._generate_with_claude
    original_gemini = agent._generate_with_gemini
    
    claude_called = False
    gemini_called = False
    
    def mock_claude(*args, **kwargs):
        nonlocal claude_called
        claude_called = True
        return "class BatchModel: pass"
    
    def mock_gemini(*args, **kwargs):
        nonlocal gemini_called
        gemini_called = True
        return "class BatchModel: pass"
        
    agent._generate_with_claude = mock_claude
    agent._generate_with_gemini = mock_gemini
    
    agent.generate_format([], "test", provider="claude")
    if claude_called: print("SUCCESS: Claude provider correctly targeted.")
    
    agent.generate_format([], "test", provider="gemini")
    if gemini_called: print("SUCCESS: Gemini provider correctly targeted.")
    
    # Clean up
    agent._generate_with_claude = original_claude
    agent._generate_with_gemini = original_gemini

if __name__ == "__main__":
    try:
        test_agent_logic()
    except Exception as e:
        print(f"Verification script failed: {e}")
        import traceback
        traceback.print_exc()
