import unittest

import vinted_bot as bot

CONFIG = {
    "min_deal_score": 8,
    "require_hunt_fit": True,
    "keep_value_bands": ["steal", "hunt"],
    "solo_floor_clothing_ron": 100,
}
GYM = {"target_type": "men's gym clothing", "min_deal_score": 8}


class KeepRuleTests(unittest.TestCase):
    def test_steal_clothing_under_floor_is_keep(self):
        item = {"price": {"amount": "80", "currency_code": "RON"}}
        score = {
            "deal_score": 9,
            "value_band": "steal",
            "hunt_fit": True,
            "scam_risk": "medium",
        }
        self.assertTrue(bot.is_keep(score, CONFIG, GYM, item))

    def test_hunt_clothing_under_floor_is_not_keep(self):
        item = {"price": {"amount": "80", "currency_code": "RON"}}
        score = {
            "deal_score": 8,
            "value_band": "hunt",
            "hunt_fit": True,
            "scam_risk": "medium",
        }
        self.assertFalse(bot.is_keep(score, CONFIG, GYM, item))


if __name__ == "__main__":
    unittest.main()
