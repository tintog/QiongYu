import tempfile
import shutil
import unittest
from pathlib import Path
import numpy as np
from app import dataset_manager as dm, observation_data as obs

FILES=Path(__file__).resolve().parents[4]/'数据/nc_output/20260928'

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='obs-tests-')
        self.previous=dm.STORE
        dm.STORE=Path(self.temp.name)
    def tearDown(self):
        dm.STORE=self.previous
        self.temp.cleanup()
    def imported(self,source):
        paths=sorted((FILES/source).glob('*.nc'))
        self.assertEqual(len(paths),4)
        j=dm.create_job('obs',source,source+' analysis','reference',4)
        dest=dm.job_path(j['id'])/'files';dest.mkdir()
        for p in paths:
            dm.safe_filename(p.name,'obs')
            shutil.copyfile(p,dest/p.name)
            result=dm.record_file(j['id'],p.name,p.stat().st_size)
            self.assertEqual(result['files'][-1]['status'],'valid',result['files'][-1])
        result=dm.finalize(j['id']);self.assertEqual(result['status'],'ready',result)
        return result
    def test_surface_import_and_matched_metrics(self):
        j=self.imported('CRALand')
        dm.activate(j['id'])
        result=obs.verification('t2m',j['id'],'builtin-DF-20260928')
        self.assertTrue(result['available'],result)
        self.assertEqual([r['leadHour'] for r in result['series']],[6,12,18])
        self.assertEqual(result['unit'],'℃')
        self.assertTrue(np.isfinite(result['overall']['rmse']))
        self.assertEqual(result['segments'][0]['matchedTimeCount'],3)
        for metric in ('mae','rmse','bias','corr','validPoints'):
            self.assertEqual(result['segments'][0][metric],result['overall'][metric])
        for segment in result['segments'][1:]:
            self.assertEqual(segment['matchedTimeCount'],0)
            self.assertEqual(segment['validPoints'],0)
            for metric in ('mae','rmse','bias','corr'):
                self.assertIsNone(segment[metric])
        self.assertFalse(obs.verification('tp',j['id'])['available'])
        self.assertFalse(obs.verification('z500',j['id'])['available'])
        self.assertTrue(any(b['product']=='obs' for b in dm.catalog()['batches']))
        with self.assertRaises(ValueError):dm.resolve(j['id'])
    def test_upper_and_previous_cycle_match(self):
        j=self.imported('ART_ATM')
        result=obs.verification('z500',j['id'],'builtin-DF-20260927')
        self.assertTrue(result['available'],result)
        self.assertEqual([r['leadHour'] for r in result['series']],[24,30,36,42])
    def test_normalization_and_known_scores(self):
        np.testing.assert_allclose(obs.normalize(np.array([273.15]),'T2M','K'),[0])
        np.testing.assert_allclose(obs.normalize(np.array([.001]),'Q700','kg kg**-1'),[1])
        np.testing.assert_allclose(obs.normalize(np.array([100000.]),'MSL','Pa'),[1000])
        r=obs.stats(np.array([1.,3.]),np.array([0.,1.]))
        self.assertEqual(r['mae'],1.5)
        self.assertAlmostEqual(r['rmse'],np.sqrt(2.5))
        self.assertIsNone(obs.stats(np.zeros(2),np.zeros(2))['corr'])
    def test_forecast_cannot_be_reference(self):
        p=Path(__file__).resolve().parents[1]/'../data/DF/20260928'
        with self.assertRaises(ValueError):obs.inspect(next(p.glob('*.nc')))

if __name__=='__main__':unittest.main()
