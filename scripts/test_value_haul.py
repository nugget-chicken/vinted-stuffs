import unittest

import value_haul as vh

VH = {
    "min_items": 3,
    "min_items_steal": 2,
    "steal_max_delivered_per_item_ron": 20,
    "max_candidates_to_score": 12,
}
WATCH = {
    "target_sizes": ["M", "L"],
    "target_type": "men's gym clothing suitable for building a multi-item bundle",
    "notes": "H&M Sport Nike Adidas",
}


def item(iid, title, brand="H&M", size="M", price="20"):
    return {
        "id": iid,
        "title": title,
        "brand_title": brand,
        "size_title": size,
        "price": {"amount": price, "currency_code": "RON"},
        "status": "Very good",
    }


class GateTests(unittest.TestCase):
    def test_three_candidates_pass(self):
        self.assertTrue(vh.passes_value_haul_gate(3, 40.0, VH))

    def test_two_cheap_pass(self):
        self.assertTrue(vh.passes_value_haul_gate(2, 18.0, VH))

    def test_two_expensive_fail(self):
        self.assertFalse(vh.passes_value_haul_gate(2, 35.0, VH))

    def test_one_fails(self):
        self.assertFalse(vh.passes_value_haul_gate(1, 10.0, VH))


class PrefilterTests(unittest.TestCase):
    def test_size_m_slash_l_matches(self):
        self.assertTrue(vh.size_matches(item(1, "tee", size="M/L"), ["M", "L"]))

    def test_size_xl_does_not_match_l(self):
        self.assertFalse(vh.size_matches(item(1, "tee", size="XL"), ["M", "L"]))

    def test_wrong_size_rejected(self):
        self.assertFalse(vh.size_matches(item(1, "tee", size="S"), ["M", "L"]))

    def test_title_letters_do_not_override_size(self):
        self.assertFalse(
            vh.size_matches(item(1, "Gym training top", size="S"), ["M", "L"])
        )

    def test_gym_title_accepted(self):
        self.assertTrue(vh.looks_like_gymwear(item(1, "H&M Sport póló"), WATCH))

    def test_random_home_rejected(self):
        self.assertFalse(
            vh.looks_like_gymwear(item(1, "Ikea cushion cover", brand="Ikea"), WATCH)
        )

    def test_prefilter_caps_and_keeps_gym(self):
        items = [
            item(1, "Nike training tee", price="15"),
            item(2, "Adidas gym short", size="L", price="18"),
            item(3, "H&M Sport top", price="12"),
            item(4, "Candle holder", brand="Home", size="M", price="5"),
        ]
        out = vh.prefilter_candidates(items, WATCH, {"value_haul": VH})
        ids = [x["id"] for x in out]
        self.assertIn(1, ids)
        self.assertIn(2, ids)
        self.assertIn(3, ids)
        self.assertNotIn(4, ids)


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_sorted_useful_only(self):
        items = [item(3, "c"), item(1, "a"), item(2, "b")]
        score = {"reject_ids": [2]}
        useful = vh.useful_items(items, score)
        self.assertEqual(vh.value_haul_fingerprint(99, useful), "99:1,3")


class PayloadAndAlertTests(unittest.TestCase):
    def test_payload_totals(self):
        items = [
            item(1, "H&M Sport", price="16.67"),
            item(2, "H&M Sport", size="L", price="16.67"),
            item(3, "Nike tee", price="16.66"),
        ]
        payload = vh.build_haul_payload("robert", "hu", 40.0, items, WATCH)
        self.assertEqual(payload["kind"], "value_haul")
        self.assertEqual(payload["matching_items"], 3)
        self.assertAlmostEqual(payload["total_listing_price"], 50.0, places=1)
        self.assertAlmostEqual(payload["estimated_total"], 90.0, places=1)
        self.assertIn("value_haul", vh.value_haul_prompt(payload, VH).lower())

    def test_parse_object(self):
        raw = '{"deal_score":9,"value_band":"steal","useful_item_count":3,"effective_price_per_useful_item":21.2,"hunt_fit":true,"scam_risk":"low","reason":"good","reject_ids":[]}'
        score = vh.parse_value_haul_score(raw)
        self.assertEqual(score["deal_score"], 9)

    def test_alert_requires_gate_after_rejects(self):
        items = [item(1, "a"), item(2, "b"), item(3, "c")]
        score = {
            "deal_score": 9,
            "value_band": "steal",
            "hunt_fit": True,
            "scam_risk": "low",
            "reject_ids": [1],
            "effective_price_per_useful_item": 18.0,
            "useful_item_count": 2,
        }
        useful = vh.useful_items(items, score)
        self.assertEqual(len(useful), 2)
        self.assertTrue(vh.is_value_haul_alert(score, useful, 25.0, VH))

    def test_alert_rejects_high_scam(self):
        items = [item(1, "a"), item(2, "b"), item(3, "c")]
        score = {
            "deal_score": 9,
            "value_band": "steal",
            "hunt_fit": True,
            "scam_risk": "high",
            "reject_ids": [],
            "effective_price_per_useful_item": 15.0,
        }
        self.assertFalse(vh.is_value_haul_alert(score, items, 25.0, VH))


if __name__ == "__main__":
    unittest.main()
