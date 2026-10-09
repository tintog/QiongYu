import unittest
import numpy as np
from app.observation_data import precip_scores,normalize

class PrecipScores(unittest.TestCase):
    def test_contingency_and_scores(self):
        row=precip_scores(np.array([2,2,0,0]),np.array([2,0,2,0]))[1]
        self.assertEqual((row['hits'],row['falseAlarms'],row['misses'],row['correctNegatives']),(1,1,1,1))
        self.assertAlmostEqual(row['TS'],1/3)
        self.assertEqual(row['POD'],.5)
        self.assertEqual(row['FAR'],.5)
        self.assertEqual(row['BIAS'],1)
    def test_undefined_and_threshold_boundary(self):
        dry=precip_scores(np.zeros(3),np.zeros(3))[0]
        for key in ('TS','POD','FAR','BIAS'):self.assertIsNone(dry[key])
        row=precip_scores(np.array([1]),np.array([1]))[1]
        self.assertEqual(row['TS'],1)
        self.assertEqual(row['FAR'],0)
        np.testing.assert_allclose(normalize(np.array([.001]),'TP','m'),[1])

if __name__=='__main__':unittest.main()
