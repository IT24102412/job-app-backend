import requests

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(push_token: str | None, title: str, body: str, data: dict | None = None) -> None:
    """Sends a real push notification via Expo's free push service.
    Fails silently (logs only) so a push failure never breaks the real action
    (assigning a job, closing a job, etc.) that triggered it."""
    if not push_token:
        return

    try:
        requests.post(
            EXPO_PUSH_URL,
            json={
                "to": push_token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                "priority": "high",
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=5,
        )
    except requests.exceptions.RequestException as e:
        print(f"Failed to send push notification: {e}")