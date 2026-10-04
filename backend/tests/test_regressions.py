"""从backend目录运行：python -m unittest discover -s tests -v。"""
import unittest
from unittest.mock import patch
import numpy as np
from app import qiongyu_data as qd
from app import qiongyu_service as svc
from app.realtime import RealtimeMonitor


class RegressionTests(unittest.TestCase):
    def test_unit_conversion_no_double_conversion(self):
        a = np.array([101325.0], dtype=np.float32)
        np.testing.assert_allclose(qd.normalize_display_units(a, 'MSL', 'Pa'), [1013.25])
        np.testing.assert_allclose(qd.normalize_display_units(a / 100, 'MSL', 'hPa'), [1013.25])
        np.testing.assert_allclose(qd.normalize_display_units(np.array([.01]), 'Q2M', 'g/g'), [10])
        np.testing.assert_allclose(qd.normalize_display_units(np.array([10.]), 'Q2M', 'g/kg'), [10])
        np.testing.assert_allclose(qd.normalize_display_units(np.array([10.]), 'Q700', 'g/kg'), [10])
        with self.assertRaises(ValueError):
            qd.normalize_display_units(a, 'MSL', '')

    def test_real_maps_and_points_have_same_display_units(self):
        for key, var, scale in [('msl', 'MSL', .01), ('q2m', 'Q2M', 1000)]:
            d, _ = qd.resolve_latest()
            with qd._open_dataset(d.path_for('SURFACE', 24)) as ds:
                expected = ds[var].values.squeeze() * scale
            field = svc.variable_field(key, 24, 1)
            values = np.array([p[2] for p in field['points']]).reshape(expected.shape)
            np.testing.assert_allclose(values, expected, atol=.011, rtol=1e-5)
            point = svc.point_forecast(120.15, 30.28, key)
            value = next(r['value'] for r in point['series'] if r['leadHour'] == 24)
            mapped = next(p[2] for p in field['points'] if p[:2] == [120.25, 30.25])
            self.assertEqual(value, mapped)

    def test_precip_totals_and_nonprecip_daily_statistics(self):
        for key, mode in [('tp', 'sum'), ('t2m', 'mean'), ('wind850', 'max')]:
            p = svc.point_forecast(104.07, 30.67, key)
            first_day = [s['value'] for s in p['series'] if s['leadHour'] <= 24]
            expected = sum(first_day) if mode == 'sum' else max(first_day) if mode == 'max' else np.mean(first_day)
            self.assertEqual(p['daily'][0]['value'], round(float(expected), 2))
            self.assertEqual(p['daily'][0]['aggregate'], mode)
            if key != 'tp':
                self.assertNotIn('rainyPeriods', p['summary'])
                self.assertNotIn('total', p['summary'])
                self.assertFalse(p['thresholds'])
                self.assertEqual(p['dailyUnit'], p['unit'])
            else:
                self.assertAlmostEqual(sum(x['value'] for x in p['daily']), p['summary']['total'], places=2)

    def test_risk_uses_four_complete_six_hour_periods(self):
        d, _ = qd.resolve_latest()
        risk = svc.risk_warnings(2)
        self.assertEqual(risk['unit'], 'mm/24h')
        self.assertTrue(risk['alarms'])
        for alarm in risk['alarms']:
            h = alarm['leadHour']
            self.assertGreaterEqual(h, 24)
            expected = sum(svc._load_tp_field(d, x, 2)[0] for x in [h-18,h-12,h-6,h])
            self.assertEqual(alarm['maximum'], round(float(expected.max()), 2))
            self.assertEqual(alarm['accumulationHours'], 24)
            self.assertTrue(all(r['value'] >= 25 for r in alarm['ranking']))

    def test_no_observations_no_scores(self):
        result = svc.verification(24)
        self.assertFalse(result['available'])
        self.assertIn('实况', result['message'])
        self.assertNotIn('overall', result)
        self.assertNotIn('series', result)
        self.assertEqual(result['requiredThresholds'], [.1,13.,25.])

    def test_monitor_only_changes_revision_on_product_change(self):
        m = RealtimeMonitor()
        m.scan(force=True)
        revision = m.revision
        m.scan(force=True)
        self.assertEqual(m.revision, revision)
        d, e = qd.resolve_latest()
        with patch.object(d, 'file_count', return_value=d.file_count()+1), patch.object(qd, 'resolve_latest', return_value=(d,e)):
            m.scan(force=True)
        self.assertEqual(m.revision, revision+1)
        self.assertTrue(m.events)


if __name__ == '__main__':
    unittest.main()
