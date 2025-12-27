import unittest

from watchfuleye.performance.perf_calc import compute_returns, position_multiplier


class TestPerfCalc(unittest.TestCase):
    def test_position_multiplier(self):
        self.assertEqual(position_multiplier("BUY"), 1)
        self.assertEqual(position_multiplier("LONG"), 1)
        self.assertEqual(position_multiplier("HEDGE"), 1)
        self.assertEqual(position_multiplier("SELL"), -1)
        self.assertEqual(position_multiplier("SHORT"), -1)

    def test_compute_returns_long(self):
        r = compute_returns(action="BUY", entry_price=100, exit_price=110, benchmark_entry=100, benchmark_exit=105)
        self.assertAlmostEqual(r.rec_return, 0.10)
        self.assertAlmostEqual(r.benchmark_return, 0.05)
        self.assertAlmostEqual(r.alpha, 0.05)

    def test_compute_returns_short(self):
        r = compute_returns(action="SELL", entry_price=100, exit_price=110, benchmark_entry=100, benchmark_exit=105)
        self.assertAlmostEqual(r.rec_return, -0.10)
        self.assertAlmostEqual(r.benchmark_return, 0.05)
        self.assertAlmostEqual(r.alpha, -0.15)


if __name__ == "__main__":
    unittest.main()


