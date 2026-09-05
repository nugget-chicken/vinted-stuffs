"""Regression: one CLI process per listing batch, not per seller.

The live failure was Vinted bootstrap 429 after ~11 new `node dist/cli.js seller`
processes per hunt. attach_seller_profiles must issue a single seller argv.
"""
import unittest
from unittest.mock import patch

import vinted_bot as bot


class ProfileBatchTests(unittest.TestCase):
    def setUp(self):
        bot._profile_consecutive_failures = 0
        bot._profile_endpoint_disabled = False
        bot._profile_debug_printed = True

    def test_attach_issues_one_comma_separated_seller_call(self):
        items = [
            {"id": i, "user": {"id": 1000 + i}}
            for i in range(10)
        ]
        calls = []

        def fake_vinted(args, timeout=60, stdin_payload=None):
            calls.append((list(args), stdin_payload))
            return {
                "sellers": [
                    {
                        "id": 1000 + i,
                        "feedbackCount": 1,
                        "feedbackReputation": 1,
                        "itemCount": 2,
                        "countryCode": "RO",
                    }
                    for i in range(10)
                ]
            }

        with patch.object(bot, "_vinted_json", side_effect=fake_vinted):
            bot.attach_seller_profiles(items, "ro")

        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0][0], ["batch"])
        self.assertEqual(len(calls[0][1]["sellers"]["ids"]), 10)
        self.assertEqual(items[0]["_profile"]["feedback_count"], 1)
        self.assertEqual(items[9]["_profile"]["country_code"], "ro")


if __name__ == "__main__":
    unittest.main()
