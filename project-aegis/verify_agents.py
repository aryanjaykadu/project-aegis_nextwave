import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import twilio
    import playwright
    import dotenv
    print("✅ SYSTEM VERIFIED: All Action Agents (Twilio, Playwright, Dotenv) are successfully installed and online!")
except ImportError as e:
    print(f"❌ CRITICAL FAILURE: Missing dependency - {e}")
