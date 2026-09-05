import unittest
from unittest.mock import patch

import vinted_bot as bot

CONFIG = {
    "min_deal_score": 8,
    "require_hunt_fit": True,
    "keep_value_bands": ["steal", "hunt"],
    "solo_floor_clothing_ron": 100,
    "bundle_extra_min_score": 6,
    "checkout_extra_ron": {"ro": 25, "default": 25},
}
WATCH = {"name": "Lululemon gym M-L", "target_type": "men's gym clothing", "country": "ro"}


def row(iid, score, band, seller, price="150", hunt_fit=True):
    return {
        "item": {
            "id": iid,
            "title": f"item {iid}",
            "price": {"amount": price, "currency_code": "RON"},
            "url": f"https://www.vinted.ro/items/{iid}",
            "user": {"id": seller, "login": "seller"},
            "_profile": {"country_code": "ro"},
        },
        "score": {
            "deal_score": score,
            "value_band": band,
            "hunt_fit": hunt_fit,
            "scam_risk": "medium",
        },
        "watch": WATCH["name"],
        "watch_obj": WATCH,
    }


class BundlePoolTests(unittest.TestCase):
    def test_failed_closet_is_omitted_but_empty_closet_is_retained(self):
        response = {
            "closets": [
                {"sellerId": 10, "error": "temporary failure"},
                {"sellerId": 20, "items": []},
            ]
        }
        with patch.object(bot, "_vinted_json", return_value=response):
            closets = bot.get_seller_closets([10, 20], "ro", 12)
        self.assertNotIn("10", closets)
        self.assertEqual(closets["20"], [])

    def test_alerted_keys_preserve_insertion_order_and_trim_oldest(self):
        ordered = [f"old-{i}" for i in range(200)]
        membership = set(ordered)
        bot.add_alerted_bundle_key(ordered, membership, "value-haul")
        bot.add_alerted_bundle_key(ordered, membership, "keep-bundle")
        bot.add_alerted_bundle_key(ordered, membership, "value-haul")
        self.assertEqual(ordered[-2:], ["value-haul", "keep-bundle"])
        self.assertEqual(ordered[-200:][0], "old-2")
        self.assertEqual(len(ordered), 202)

    def test_prior_extra_plus_new_keep_makes_bundle(self):
        keep = row(1, 9, "steal", 99)
        extra = row(2, 7, "acceptable", 99)
        bundles, solos = bot.assemble_bundles(bot.merge_scored([keep], [extra]), CONFIG)
        self.assertEqual(len(bundles), 1)
        self.assertEqual(len(solos), 0)
        self.assertEqual(bundles[0]["keeps"][0]["item"]["id"], 1)
        self.assertEqual(bundles[0]["extras"][0]["item"]["id"], 2)

    def test_current_row_wins_on_same_id(self):
        old = row(1, 6, "acceptable", 99)
        new = row(1, 9, "steal", 99)
        merged = bot.merge_scored([new], [old])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["score"]["deal_score"], 9)

    def test_fingerprint_stable(self):
        keep = row(1, 9, "steal", 99)
        extra = row(2, 7, "acceptable", 99)
        bundles, _ = bot.assemble_bundles([keep, extra], CONFIG)
        self.assertEqual(bot.bundle_fingerprint(bundles[0]), "99:1,2")


if __name__ == "__main__":
    unittest.main()
