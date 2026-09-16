import requests

from app.config import settings

TEXTLK_API_URL = "https://app.text.lk/api/v3/sms/send"


def _to_textlk_format(phone: str) -> str:
    """Converts a local 07XXXXXXXX number to Text.lk's expected 94XXXXXXXXX format."""
    digits = phone.strip()
    if digits.startswith("0"):
        return "94" + digits[1:]
    return digits


def send_otp_sms(phone: str, otp_code: str) -> bool:
    """Sends a password reset OTP via Text.lk. Returns True if the request succeeded."""
    if not settings.textlk_api_token:
        print("TEXTLK_API_TOKEN not configured — cannot send SMS")
        return False

    recipient = _to_textlk_format(phone)
    print(f"Attempting to send OTP SMS to {recipient}...")

    try:
        response = requests.post(
            TEXTLK_API_URL,
            headers={
                "Authorization": f"Bearer {settings.textlk_api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "recipient": recipient,
                "sender_id": "TextLKDemo",
                "type": "plain",
                "message": f"Your Job Tracker password reset code is: {otp_code}. Valid for 10 minutes.",
            },
            timeout=10,
        )
        print(f"Text.lk response: {response.status_code} — {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Failed to send OTP SMS (network error): {e}")
        return False