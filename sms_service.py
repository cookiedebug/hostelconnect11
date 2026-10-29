
import os
import requests
from requests.auth import HTTPBasicAuth


def send_sms(phone_number, message):
    client_id = os.getenv("HUBTEL_CLIENT_ID")
    client_secret = os.getenv("HUBTEL_CLIENT_SECRET")
    sender_id = os.getenv("HUBTEL_SENDER_ID")

    if not phone_number or not message:
        raise ValueError("A phone number and message are required.")

    if not client_id or not client_secret:
        raise RuntimeError("Hubtel credentials are not configured.")

    if not sender_id:
        raise RuntimeError("Hubtel sender ID is not configured.")

    url = os.getenv(
        "HUBTEL_SMS_URL",
        "https://smsc.hubtel.com/v1/messages/send"
    )

    payload = {
        "from": sender_id,
        "to": phone_number,
        "content": message
    }

    response = requests.post(
        url,
        auth=HTTPBasicAuth(client_id, client_secret),
        json=payload,
        timeout=20
    )

    if not response.ok:
        response.raise_for_status()

    return response.json()
