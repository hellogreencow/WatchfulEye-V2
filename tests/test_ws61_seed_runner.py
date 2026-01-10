import unittest


from scripts.dev.seed_ws61_from_existing import (
    _action_to_direction,
    _action_to_probability,
    _deterministic_seed_forecast_id,
    _deterministic_seed_inv_id,
    _deterministic_seed_report_id,
    _parse_horizons_days,
)


class TestWS61SeedRunner(unittest.TestCase):
    def test_deterministic_ids(self) -> None:
        self.assertEqual(_deterministic_seed_inv_id(123), "seed_inv_global_brief_123")
        self.assertEqual(_deterministic_seed_report_id(123), "seed_rpt_global_brief_123")
        self.assertEqual(
            _deterministic_seed_forecast_id(recommendation_id=999, horizon_days=30),
            "seed_fc_rec_999_30",
        )

    def test_parse_horizons_days(self) -> None:
        self.assertEqual(_parse_horizons_days("7,30,90"), [7, 30, 90])
        self.assertEqual(_parse_horizons_days(" 7 , 30 , 90 "), [7, 30, 90])
        self.assertEqual(_parse_horizons_days("30,30,7"), [30, 7])
        self.assertEqual(_parse_horizons_days(""), [])
        self.assertEqual(_parse_horizons_days("0,-1,7"), [7])

    def test_action_to_probability_conservative(self) -> None:
        self.assertEqual(_action_to_probability("buy"), 0.6)
        self.assertEqual(_action_to_probability("sell"), 0.6)
        self.assertEqual(_action_to_probability("strong buy"), 0.65)
        self.assertEqual(_action_to_probability("strong sell"), 0.65)
        self.assertEqual(_action_to_probability("unknown"), 0.55)

    def test_action_to_direction(self) -> None:
        self.assertEqual(_action_to_direction("buy"), "outperforms")
        self.assertEqual(_action_to_direction("long"), "outperforms")
        self.assertEqual(_action_to_direction("sell"), "underperforms")
        self.assertEqual(_action_to_direction("short"), "underperforms")


if __name__ == "__main__":
    unittest.main()


