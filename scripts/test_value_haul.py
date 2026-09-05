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

    def test_wrong_size_rejected(self):
        self.assertFalse(vh.size_matches(item(1, "tee", size="S"), ["M", "L"]))

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


if __name__ == "__main__":
    unittest.main()
