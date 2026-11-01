import os
from xml.sax.saxutils import escape


def trigger_emergency_call(alert_text: str, *, approved: bool = False) -> bool:
    """Optional voice adapter; never place calls without explicit approval/configuration."""
    if not approved or os.getenv("AEGIS_AUTH_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return False
    if os.getenv("AEGIS_ENABLE_LIVE_VOICE", "false").lower() not in ("1", "true", "yes"):
        return False
    try:
        from twilio.rest import Client
        from dotenv import load_dotenv
        load_dotenv()
        sid, token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
        from_num, to_num = os.getenv("TWILIO_PHONE_NUMBER"), os.getenv("TARGET_PHONE_NUMBER")
        if not all((sid, token, from_num, to_num)):
            print("Voice Agent: Twilio credentials missing; no call sent.")
            return False
        safe_text = escape(str(alert_text)[:1200])
        call = Client(sid, token).calls.create(
            twiml=f"<Response><Say>{safe_text}</Say></Response>", to=to_num, from_=from_num
        )
        print(f"Voice Agent: call initiated {call.sid}")
        return True
    except ImportError:
        print("Voice Agent: Twilio is not installed; no call sent.")
        return False
    except Exception as exc:
        print(f"Voice Agent error: {exc}")
        return False
