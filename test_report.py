import unittest
from datetime import datetime, timezone
import report

class DataTests(unittest.TestCase):
    def test_history_sorted_and_invalid_rejected(self):
        rows = [{'day':'2026-11-02','avg_price':110}, {'day':'2026-11-01','avg_price':100}]
        self.assertEqual(list(report.parse_history(rows)), ['2026-11-01','2026-11-02'])
        for price in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                report.parse_history([{'day':'2026-11-01','avg_price':price}])
        with self.assertRaises(ValueError):
            report.parse_history(rows + rows)

    def test_comparison_uses_common_start_not_different_days(self):
        a,b = report.normalized({'2026-11-01':50,'2026-11-02':100,'2026-11-03':110},
                                {'2026-11-02':200,'2026-11-03':180})
        self.assertEqual(list(a), ['2026-11-02','2026-11-03'])
        self.assertAlmostEqual(a['2026-11-02'],100)
        self.assertAlmostEqual(a['2026-11-03'],110)
        self.assertEqual(b, {'2026-11-02':100.0,'2026-11-03':90.0})

    def test_taiwan_midnight_and_morning(self):
        self.assertEqual(report.taipei_time(datetime(2026,11,25,16,tzinfo=timezone.utc)), '2026-11-26 00:00 +0800')
        self.assertEqual(report.taipei_time(datetime(2026,11,26,0,tzinfo=timezone.utc)), '2026-11-26 08:00 +0800')
        self.assertEqual(report.taipei_time(datetime(2026,11,26,4,tzinfo=timezone.utc)), '2026-11-26 12:00 +0800')

    def test_insufficient_history_and_stale_tail_rejected(self):
        now = datetime(2026,11,26,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            report.validate_coverage({'2026-11-25':100}, now)
        with self.assertRaises(ValueError):
            report.validate_coverage({f'2026-11-{d:02}':100 for d in range(1,21)}, now)

    def test_live_quote_rejects_wrong_currency_and_future_time(self):
        now = datetime(2026,11,26,tzinfo=timezone.utc)
        base = dict(symbol='XAU',currency='USD',price=100,updatedAt='2026-11-25T23:59:00Z')
        self.assertEqual(report.parse_quote(base,'XAU',now)['price'],100)
        with self.assertRaises(ValueError):
            report.parse_quote(dict(base,currency='EUR'),'XAU',now)
        with self.assertRaises(ValueError):
            report.parse_quote(dict(base,updatedAt='2026-11-27T00:00:00Z'),'XAU',now)

if __name__ == '__main__':
    unittest.main()
