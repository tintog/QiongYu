import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from app import dataset_manager as dm, observation_data as obs
from test_data_workflow import make_files

FILES=Path(__file__).resolve().parents[4]/'数据/nc_output/20260928'

class ImportMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='metadata-tests-')
        self.root=Path(self.temp.name)
        self.patcher=patch.object(dm,'STORE',self.root/'store');self.patcher.start()
    def tearDown(self):
        self.patcher.stop();self.temp.cleanup()
    def draft(self,source='CRALand'):
        j=dm.create_job('obs','','','',4,True)
        dest=dm.job_path(j['id'])/'files';dest.mkdir()
        for p in sorted((FILES/source).glob('*.nc')):
            shutil.copyfile(p,dest/p.name)
            dm.record_file(j['id'],p.name,p.stat().st_size)
        return j['id']
    def fields(self,p,allow=False):
        return dict(name=p['suggestedName'],source=p['suggestedSource'],model=p['suggestedModel'],
                    dataProduct=p['dataProduct'],institution=p['institution'],tags=['演示','九月'],remarks='来源待核实',allowDuplicate=allow)
    def finish(self,j):
        p=dm.preview(j);dm.update_metadata(j,self.fields(p));return dm.finalize(j)
    def test_auto_identification_of_both_sources(self):
        for source,group in [('CRALand','地面分析'),('ART_ATM','高空分析及气压')]:
            j=self.draft(source);p=dm.preview(j)
            self.assertEqual(p['dataProduct'],source)
            self.assertEqual(p['suggestedName'],f'{source} · {group} · 20260928')
            self.assertEqual(len(p['validTimes']),4)
            self.assertEqual(p['referenceType'],'analysis')
            self.assertFalse(p['errors'],p)
            self.assertEqual(p['grid']['lonCount'],281)
            self.assertFalse(any(b['id']==j for b in dm.catalog()['batches']))
            self.assertFalse(dm.selection())
            if source=='CRALand':self.assertEqual(p['suggestedModel'],'V1.0.0')
    def test_confirmation_and_content_based_duplicates(self):
        j=self.draft()
        with self.assertRaisesRegex(ValueError,'确认'):dm.finalize(j)
        self.assertEqual(self.finish(j)['status'],'ready')
        second=self.draft();p=dm.preview(second)
        self.assertIn(j,[d['id'] for d in p['duplicates']])
        fields=self.fields(p);fields['name']='另一个名称';dm.update_metadata(second,fields)
        with self.assertRaisesRegex(ValueError,'重复'):dm.finalize(second)
        fields['allowDuplicate']=True;dm.update_metadata(second,fields)
        result=dm.finalize(second)
        self.assertEqual(result['status'],'ready')
        self.assertTrue(any('重复' in x for x in result['warnings']))
        self.assertNotEqual(j,second)
        self.assertEqual(result['tags'],['演示','九月'])
    def test_incomplete_preview_cannot_be_admitted(self):
        j=self.draft();v=dm.job(j);v['expectedFiles']=5
        dm._save(dm.job_path(j)/'manifest.json',v)
        p=dm.preview(j);self.assertFalse(p['complete']);self.assertTrue(p['errors'])
        dm.update_metadata(j,self.fields(p))
        self.assertEqual(dm.finalize(j)['status'],'failed')
    def test_partial_content_duplicates_also_reported(self):
        j=self.draft();self.finish(j)
        second=self.draft();value=dm.job(second);value['files']=value['files'][:2];value['expectedFiles']=2
        dm._save(dm.job_path(second)/'manifest.json',value)
        duplicate=next(d for d in dm.preview(second)['duplicates'] if d['id']==j)
        self.assertEqual(duplicate['matchedFiles'],2)
        self.assertFalse(duplicate['exact'])
    def test_legacy_names_and_manifests_preserved(self):
        j=self.draft();self.finish(j);v=dm.job(j);v['name']='原用户批次名'
        for k in ['dataProduct','productVersion','institution','elementGroup']:v.pop(k,None)
        for f in v['files']:
            for k in ['dataProduct','productVersion','institution','originalFile','spatialProcessing']:f.pop(k,None)
        path=dm.job_path(j)/'manifest.json';dm._save(path,v);before=path.read_bytes()
        row=next(b for b in dm.catalog()['batches'] if b['id']==j)
        self.assertEqual(row['name'],'原用户批次名');self.assertEqual(row['dataProduct'],'CRALand')
        self.assertEqual(path.read_bytes(),before)
    def test_reference_preflight_and_unmatched_time(self):
        a=self.draft();self.finish(a);z=self.draft('ART_ATM');self.finish(z)
        result=obs.reference_options('builtin-DF-20260928')
        self.assertEqual(len(result['references']),2)
        self.assertTrue(all(r['matchedCount']==3 for r in result['references']))
        self.assertEqual([t['leadHour'] for t in result['references'][0]['matchedTimes']],[6,12,18])
        files=make_files(self.root/'future',cycle='2030010100')
        j=dm.create_job('DF','future','fixture','TEST',len(files));dest=dm.job_path(j['id'])/'files';dest.mkdir()
        for p in files:
            shutil.copyfile(p,dest/p.name);dm.record_file(j['id'],p.name,p.stat().st_size)
        dm.finalize(j['id'])
        unmatched=obs.reference_options(j['id'])
        self.assertFalse(unmatched['references'])
        self.assertTrue(all(r['reason']=='有效时间不匹配' for r in unmatched['excluded']))

if __name__=='__main__':unittest.main()
