import os
import unittest

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
    def test_sms_integration_is_optional(self):
        if not os.getenv("HUBTEL_CLIENT_ID") or not os.getenv("HUBTEL_CLIENT_SECRET"):
            self.skipTest("Hubtel credentials are not configured; skipping SMS integration test.")

        if not os.getenv("HUBTEL_SENDER_ID"):
            self.skipTest("Hubtel sender ID is not configured; skipping SMS integration test.")

        if not os.getenv("TEST_PHONE_NUMBER"):
            phone_number = input(
                "Enter your phone number with country code (e.g. +233XXXXXXXXX): "
            )
        else:
            phone_number = os.getenv("TEST_PHONE_NUMBER")

        try:
            result = send_sms(
                phone_number,
                "HostelConnect test: Your Hubtel SMS integration is working!",
            )
        except Exception as error:
            self.fail(f"SMS test failed: {error}")

        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    run_sms_probe()
