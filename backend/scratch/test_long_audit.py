import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from providers.yandex import YandexProvider

async def test_long_audit_trigger():
    provider = YandexProvider(api_key="fake", folder_id="fake")
    
    # Create a long transcription ( > 20,000 chars)
    long_transcription = "A " * 11000  # 22,000 chars
    protocol = "Short protocol"
    
    print(f"Testing with transcription length: {len(long_transcription)}")
    
    # Mock _summarize_for_audit
    from unittest.mock import AsyncMock
    provider._summarize_for_audit = AsyncMock(return_value="Summarized transcript")
    
    # Mock requests.post to avoid real API calls
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": {
                "alternatives": [{"message": {"text": "Audit Report"}}],
                "usage": {"inputTextTokens": "100", "completionTokens": "50"}
            }
        }
        
        result = await provider.verify_protocol(long_transcription, protocol)
        
        print(f"Audit called successfully. Result: {result['verification_report']}")
        
        # Check if _summarize_for_audit was called
        if provider._summarize_for_audit.called:
            print("SUCCESS: _summarize_for_audit was called for long transcript.")
        else:
            print("FAILURE: _summarize_for_audit was NOT called.")

if __name__ == "__main__":
    asyncio.run(test_long_audit_trigger())
