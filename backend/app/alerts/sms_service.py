import os
from twilio.rest import Client

def send_fall_sms_alert(phone_number: str, message: str, user_config: dict = None):
    """
    Sends an SMS alert via Twilio. If user-specific configuration is provided in `user_config`
    it will use those; otherwise, it falls back to environment variables.
    If no credentials exist, it prints a mock log to the console.
    """
    # 1. Retrieve credentials
    account_sid = (user_config or {}).get("twilio_sid") or os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = (user_config or {}).get("twilio_token") or os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = (user_config or {}).get("twilio_phone") or os.getenv("TWILIO_PHONE_NUMBER")
    to_phone = phone_number or (user_config or {}).get("phone_number") or os.getenv("TO_PHONE_NUMBER")

    if not to_phone:
        print("[SMS Alert] Error: No destination phone number configured.")
        return False

    # 2. Try sending via Twilio if credentials are available
    if account_sid and auth_token and from_phone:
        try:
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=message,
                from_=from_phone,
                to=to_phone
            )
            print(f"[SMS Alert] Twilio SMS sent to {to_phone} successfully.")
            return True
        except Exception as e:
            print(f"[SMS Alert] Twilio API call failed: {e}")
            print(f"[SMS Alert Mock] Destination: {to_phone} | Message: {message}")
            return False
    else:
        # Fallback Mock
        print("\n" + "="*50)
        print("[SMS Alert MOCK] Twilio credentials not configured.")
        print(f"To: {to_phone}")
        print(f"Message: {message}")
        print("="*50 + "\n")
        return True
