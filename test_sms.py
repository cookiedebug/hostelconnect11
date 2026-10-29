import os
import unittest
from unittest.mock import Mock, patch

import requests
from sms_service import send_sms


def run_sms_probe(phone_number=None):
    if phone_number is None:
        phone_number = os.getenv("TEST_PHONE_NUMBER")
    if phone_number is None:
        phone_number = input(
            "Enter your phone number with country code (e.g. +233XXXXXXXXX): "
        )

    result = send_sms(
        phone_number,
        "HostelConnect test: Your Hubtel SMS integration is working!",
    )
    print("Hubtel response:")
    print(result)


class SmsIntegrationTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials_raise_without_sending(self):
        with patch("sms_service.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "credentials are not configured"):
                send_sms("+233123456789", "Test message")

        post.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "HUBTEL_CLIENT_ID": "test-client",
            "HUBTEL_CLIENT_SECRET": "test-secret",
        },
        clear=True,
    )
    def test_missing_sender_id_raises_without_sending(self):
        with patch("sms_service.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "sender ID is not configured"):
                send_sms("+233123456789", "Test message")

        post.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "HUBTEL_CLIENT_ID": "test-client",
            "HUBTEL_CLIENT_SECRET": "test-secret",
            "HUBTEL_SENDER_ID": "TEST",
            "HUBTEL_SMS_URL": "https://sms.example.invalid/send",
        },
        clear=True,
    )
    @patch("sms_service.requests.post")
    def test_send_sms_posts_configured_payload(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {"status": "accepted"}
        post.return_value = response

        result = send_sms("+233123456789", "Test message")

        self.assertEqual(result, {"status": "accepted"})
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://sms.example.invalid/send")
        self.assertEqual(kwargs["json"], {
            "from": "TEST",
            "to": "+233123456789",
            "content": "Test message",
        })
        self.assertEqual(kwargs["timeout"], 20)
        self.assertEqual(kwargs["auth"].username, "test-client")
        self.assertEqual(kwargs["auth"].password, "test-secret")

    @patch.dict(
        os.environ,
        {
            "HUBTEL_CLIENT_ID": "test-client",
            "HUBTEL_CLIENT_SECRET": "test-secret",
            "HUBTEL_SENDER_ID": "TEST",
        },
        clear=True,
    )
    @patch("sms_service.requests.post")
    def test_http_errors_are_raised(self, post):
        response = Mock()
        response.ok = False
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError("Service unavailable")
        post.return_value = response

        with self.assertRaisesRegex(requests.HTTPError, "Service unavailable"):
            send_sms("+233123456789", "Test message")

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_phone_or_message_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "phone number and message are required"):
            send_sms("", "Test message")


if __name__ == "__main__":
    run_sms_probe()
