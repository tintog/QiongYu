"""Import, activation, comparison and actual HTTP regression checks.

All generated uploads and selections use isolated temporary stores; delivery files
and the user's active selection are not modified.
"""
import json
import http.cookiejar
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import numpy as np
import xarray as xr

from app import dataset_manager as dm
from app import product_comparison as pc
from app import qiongyu_data as qd
from app import qiongyu_service as svc


def make_files(directory, cycle="2026092900", product="DF", leads=(6,12,18,24), offset=0):
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    units = {"TP":"mm","T2M":"degC","U10":"m/s","V10":"m/s","Q2M":"g/g","MSL":"Pa",
             "Z500":"gpm","Q700":"g/kg","T850":"degC","U850":"m/s","V850":"m/s"}
    values = {"TP":2+offset,"T2M":20+offset,"Q2M":.01,"MSL":101325.,"Z500":5500.,"Q700":5.,"T850":10.,"U10":3.,"V10":4.,"U850":6.,"V850":8.}
    dims = (("member",) if product == "ens" else ()) + ("time","dtime","lat","lon")
    shape = ((3,) if product == "ens" else ()) + (1,1,177,281)
    for lead in leads:
        for kind, variables in dm.REQUIRED[product].items():
            coords = {"time":[np.datetime64(cycle[:4]+"-"+cycle[4:6]+"-"+cycle[6:8]+"T"+cycle[8:]+":00")],
                      "dtime":[lead],"lat":np.arange(12,56.01,.25),"lon":np.arange(70,140.01,.25)}
            if product == "ens": coords["member"] = [1,2,3]
            ds = xr.Dataset({v:(dims,np.full(shape,values[v],dtype=np.float32),{"units":units[v],"long_name":"6-hour accumulated precipitation" if v == "TP" else v}) for v in variables},coords=coords,
                            attrs={"init_time":cycle,"lead_hours":lead,"product_type":"deterministic" if product == "DF" else "ensemble","source":"isolated regression fixture"})
            path = directory / f"TEST_V1_GLB_{kind}_OP25_6HOR_FCST_{cycle}_{lead:03}.nc"
            ds.to_netcdf(path,engine="h5netcdf"); ds.close(); result.append(path)
    return result


class DataWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qiongyu-data-test-")
        self.root = Path(self.temp.name)
        self.store_patch = patch.object(dm,"STORE",self.root/"store")
        self.store_patch.start()
        qd.FIELD_CACHE.clear(); qd.POINT_CACHE.clear()

    def tearDown(self):
        self.store_patch.stop(); self.temp.cleanup()
        qd.FIELD_CACHE.clear(); qd.POINT_CACHE.clear()

    def imported(self, cycle="2026092900", product="DF", leads=(6,12,18,24), offset=0):
        files = make_files(self.root / (cycle+product+str(offset)),cycle,product,leads,offset)
        value = dm.create_job(product,"测试批次","测试声明来源","TEST V1",len(files))
        directory = dm.job_path(value["id"])/"files"; directory.mkdir()
        for path in files:
            shutil.copyfile(path,directory/path.name)
            dm.record_file(value["id"],path.name,path.stat().st_size)
        return dm.finalize(value["id"])

    def test_import_report_and_activation_linkage(self):
        value = self.imported()
        self.assertEqual(value["status"],"ready"); self.assertTrue(value["canActivate"])
        self.assertEqual(len(value["missingLeads"]),56)
        dm.activate(value["id"])
        self.assertEqual(qd.resolve_latest()[0].cycle,"2026092900")
        info = svc.system_info()
        self.assertEqual(info["dataSource"],"测试声明来源")
        self.assertEqual(info["activeBatchId"],value["id"])
        self.assertEqual(svc.overview(24,"24h",6)["cycle"],value["cycle"])
        point = svc.point_forecast(120.15,30.28,"msl")
        self.assertEqual(point["cycle"],value["cycle"])
        self.assertEqual(point["series"][0]["value"],1013.25)
        self.assertEqual(svc.variable_field("t2m",24,6)["cycle"],value["cycle"])
        self.assertEqual(svc.timeline()[0]["validTime"],qd.cycle_to_datetime(value["cycle"]).isoformat())
        with self.assertRaises(ValueError): dm.remove(value["id"])
        dm.activate("builtin-DF-20260928")
        dm.remove(value["id"])
        self.assertTrue((dm.job_path(value["id"])/"files").is_dir())
        self.assertNotIn(value["id"],[b["id"] for b in dm.catalog()["batches"]])

    def test_global_cycle_pairs_ensemble_and_never_falls_back(self):
        builtins=[b for b in dm.catalog()["batches"] if b.get("builtin") and b["product"]=="DF"]
        self.assertTrue(builtins)
        for batch in builtins:
            self.assertEqual(batch["name"],"确定性预报 · "+batch["cycle"])
        forecast=self.imported()
        dm.activate(forecast["id"])
        self.assertIsNone(qd.resolve_latest()[1])
        self.assertFalse(svc.ensemble_probability()["available"])
        self.assertFalse(any(b["active"] for b in dm.catalog()["batches"] if b["product"]=="ens"))
        ensemble=self.imported(product="ens")
        dm.activate(forecast["id"])
        self.assertEqual(dm.selection()["ens"],ensemble["id"])
        self.assertEqual(qd.resolve_latest()[1].cycle,forecast["cycle"])
        dm.activate("builtin-DF-20260928")
        self.assertEqual(qd.resolve_latest()[1].cycle,"2026092800")
        with self.assertRaises(ValueError):
            dm.activate(ensemble["id"])
        dm.activate(forecast["id"])
        self.assertEqual(qd.resolve_latest()[0].cycle,qd.resolve_latest()[1].cycle)

    def test_failed_batch_never_available(self):
        v = dm.create_job("DF","失败样例","未知","未声明",1)
        directory = dm.job_path(v["id"])/"files"; directory.mkdir()
        name = "TEST_V1_GLB_SURFACE_FCST_2026092900_006.nc"
        (directory/name).write_bytes(b"not netcdf")
        dm.record_file(v["id"],name,10)
        result=dm.finalize(v["id"])
        self.assertEqual(result["status"],"failed"); self.assertTrue(result["errors"])
        self.assertNotIn(v["id"],[x["id"] for x in dm.catalog()["batches"]])
        with self.assertRaises(ValueError): dm.activate(v["id"])
        with self.assertRaises(ValueError): dm.resolve(v["id"])

    def test_missing_pair_and_noncontiguous_activation(self):
        files=make_files(self.root/"missing",leads=(6,))
        v=dm.create_job("DF","缺文件","未知","",1)
        directory=dm.job_path(v["id"])/"files"; directory.mkdir()
        shutil.copyfile(files[0],directory/files[0].name)
        dm.record_file(v["id"],files[0].name,files[0].stat().st_size)
        self.assertEqual(dm.finalize(v["id"])["status"],"failed")
        sparse=self.imported(leads=(6,18,24))
        self.assertEqual(sparse["status"],"ready"); self.assertFalse(sparse["canActivate"])
        with self.assertRaises(ValueError): dm.activate(sparse["id"])

    def test_metadata_units_and_nonfinite_rejected(self):
        path=make_files(self.root/"bad",leads=(6,))[0]
        with qd._open_dataset(path) as source: original=source.load()
        for scenario in ("cycle","units","missing","nonfinite","grid"):
            ds=original.copy(deep=True)
            if scenario == "cycle": ds.attrs["init_time"]="2026092800"
            if scenario == "units": ds.TP.attrs["units"]="m"
            if scenario == "missing": ds=ds.drop_vars("TP")
            if scenario == "nonfinite": ds.TP.values.flat[0]=np.nan
            if scenario == "grid": ds=ds.assign_coords(lon=np.arange(281))
            ds.to_netcdf(path,engine="h5netcdf"); ds.close()
            with self.subTest(scenario=scenario), self.assertRaises(ValueError): dm.inspect_file(path,"DF")

    def test_unsafe_paths_and_duplicate_pairs_rejected(self):
        for name in ("../x.nc","a\\b.nc","C:x.nc","file.exe"):
            with self.subTest(name=name), self.assertRaises(ValueError): dm.safe_filename(name)
        with self.assertRaises(ValueError): dm.job_path("../anything")
        value=self.imported()
        raw=dm.job(value["id"]); raw["status"]="uploading"; raw["files"].append(raw["files"][0]); raw["expectedFiles"]+=1
        dm._save(dm.job_path(value["id"])/"manifest.json",raw)
        result=dm.finalize(value["id"])
        self.assertEqual(result["status"],"failed")
        self.assertTrue(any("重复" in e for e in result["errors"]))

    def test_real_same_valid_time_difference(self):
        a,b="builtin-DF-20260928","builtin-DF-20260927"
        opts=pc.options(a,b,"tp","24h")
        time_row=next(t for t in opts["times"] if t["leadA"]==24)
        self.assertEqual(time_row["leadB"],48)
        result=pc.compare(a,b,"tp","24h",time_row["validTime"],"cycles",4)
        self.assertEqual(result["sides"][0]["validTime"],result["sides"][1]["validTime"])
        av,x,y=pc._field(dm.resolve(a),"tp",24,"24h",4)
        bv,_,_=pc._field(dm.resolve(b),"tp",48,"24h",4)
        self.assertEqual(result["difference"]["points"],qd.field_to_points(av-bv,x,y))
        self.assertEqual(result["unit"],"mm/24h")
        self.assertTrue(result["series"])
        self.assertNotIn("scores",result)

    def test_unmatched_time_mode_and_grid_rejected(self):
        a,b="builtin-DF-20260928","builtin-DF-20260927"
        with self.assertRaises(ValueError): pc.options(a,b,mode="sources")
        with self.assertRaises(ValueError): pc.options(a,a)
        with self.assertRaises(ValueError): svc._accumulate(dm.resolve(a),6,"24h",6)
        with self.assertRaises(ValueError): pc.compare(a,b,"tp","6h","2026-09-28T09:00:00+08:00","cycles")
        opts=pc.options(a,b)
        real_field=pc._field
        def shifted(index,*args):
            field,x,y=real_field(index,*args)
            return (field,x+.01,y) if index.day=="20260927" else (field,x,y)
        with patch.object(pc,"_field",side_effect=shifted), self.assertRaises(ValueError):
            pc.compare(a,b,"tp","6h",opts["times"][0]["validTime"],"cycles",6)

    def test_imported_sources_and_ensemble_mean(self):
        a=self.imported(offset=0); b=self.imported(offset=1)
        t=pc.options(a["id"],b["id"],mode="sources")["times"][0]["validTime"]
        result=pc.compare(a["id"],b["id"],"tp","6h",t,"sources",6)
        self.assertEqual(result["difference"]["mean"],-1.)
        e=self.imported(product="ens")
        t=pc.options(a["id"],e["id"],mode="ensemble")["times"][0]["validTime"]
        result=pc.compare(a["id"],e["id"],"tp","6h",t,"ensemble",6)
        self.assertEqual(result["difference"]["mean"],0.)
        self.assertIn("集合均值",result["sides"][1]["name"])


class HTTPWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="qiongyu-http-test-")
        cls.root=Path(cls.temp.name)
        with socket.socket() as sock: sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
        cls.base=f"http://127.0.0.1:{port}"
        env={**os.environ,"QIONGYU_MANAGED_ROOT":str(cls.root/"store"),'QIONGYU_AUTH_ROOT':str(cls.root/'auth'),'QIONGYU_ADMIN_PASSWORD':'Admin@2026'}
        cls.process=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+"/api/health",timeout=1).close(); break
            except (OSError,urllib.error.URLError): time.sleep(.1)
        else:
            cls.process.terminate(); cls.process.wait(); cls.temp.cleanup(); raise RuntimeError("测试服务未启动")
        cls.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        req=urllib.request.Request(cls.base+'/api/auth/login',data=json.dumps({'username':'admin','password':'Admin@2026','role':'admin'}).encode(),headers={'Content-Type':'application/json'})
        cls.opener.open(req,timeout=10).close()

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=15); cls.temp.cleanup()

    def request(self,path,body=None,raw=False):
        data=body if raw else json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.base+path,data=data,headers={"Content-Type":"application/octet-stream" if raw else "application/json"})
        with self.opener.open(req,timeout=120) as response: return json.load(response)["data"]

    def test_http_upload_finalize_activate_and_catalog(self):
        files=make_files(self.root/"input",cycle="2026092800")
        value=self.request("/api/data/imports",{"product":"DF","name":"HTTP regression","source":"test fixture","expectedFiles":len(files)})
        job_id=value["id"]
        for path in files:
            value=self.request(f"/api/data/imports/{job_id}/files?filename={path.name}",path.read_bytes(),True)
            self.assertEqual(value["files"][-1]["status"],"valid")
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request(f"/api/data/imports/{job_id}/files?filename={files[0].name}",files[0].read_bytes(),True)
        self.assertEqual(context.exception.code,400)
        context.exception.close()
        value=self.request(f"/api/data/imports/{job_id}/finalize",{})
        self.assertEqual(value["status"],"ready")
        self.request(f"/api/data/batches/{job_id}/activate",{})
        self.assertEqual(self.request("/api/module/system")["activeBatchId"],job_id)
        self.assertEqual(self.request("/api/module/point?lon=120&lat=30&variable=t2m")["summary"]["average"],20.)
        self.request("/api/data/batches/builtin-DF-20260928/activate",{})
        self.request(f"/api/data/batches/{job_id}/remove",{})
        self.assertTrue((self.root/"store"/"batches"/job_id/"files").exists())
        catalog=self.request("/api/data/batches")
        self.assertFalse(any(b["id"] == job_id for b in catalog["batches"]))

    def test_removed_comparison_and_supported_observations(self):
        for path in ("/api/module/comparison", "/api/data/comparison/options", "/api/data/comparison"):
            with self.assertRaises(urllib.error.HTTPError) as context:
                self.request(path)
            self.assertEqual(context.exception.code,404)
            context.exception.close()
        result=self.request("/api/data/imports", {"product":"obs","name":"obs","source":"test","expectedFiles":1})
        self.assertEqual(result['product'],'obs')

    def test_http_analysis_upload_and_verification(self):
        paths=sorted((Path(__file__).resolve().parents[4]/'数据/nc_output/20260928/CRALand').glob('*.nc'))
        self.assertEqual(len(paths),4)
        j=self.request('/api/data/imports',{'product':'obs','name':'surface analysis','source':'CRA analysis','expectedFiles':4})
        for p in paths:
            result=self.request(f"/api/data/imports/{j['id']}/files?filename={p.name}",p.read_bytes(),True)
            self.assertEqual(result['files'][-1]['status'],'valid',result)
        result=self.request(f"/api/data/imports/{j['id']}/finalize",{})
        self.assertEqual(result['status'],'ready',result)
        result=self.request(f"/api/module/verification?reference_id={j['id']}&forecast_id=builtin-DF-20260928&variable=t2m")
        self.assertTrue(result['available'],result)
        self.assertEqual([r['leadHour'] for r in result['series']],[6,12,18])

    def test_http_staged_identification_confirmation_and_preflight(self):
        for source in ('CRALand','ART_ATM'):
            paths=sorted((Path(__file__).resolve().parents[4]/'数据/nc_output/20260928'/source).glob('*.nc'))
            j=self.request('/api/data/imports',{'product':'obs','expectedFiles':4,'staged':True})
            for p in paths:self.request(f"/api/data/imports/{j['id']}/files?filename={p.name}",p.read_bytes(),True)
            preview=self.request(f"/api/data/imports/{j['id']}/preview")
            self.assertEqual(preview['dataProduct'],source)
            self.assertFalse(preview['errors'],preview)
            with self.assertRaises(urllib.error.HTTPError) as context:self.request(f"/api/data/imports/{j['id']}/finalize",{})
            self.assertEqual(context.exception.code,400);context.exception.close()
            self.request(f"/api/data/imports/{j['id']}/metadata",{'name':preview['suggestedName'],'source':preview['suggestedSource'],
                         'model':preview['suggestedModel'],'dataProduct':source,'institution':'未核实','tags':['HTTP测试'],'allowDuplicate':True})
            result=self.request(f"/api/data/imports/{j['id']}/finalize",{})
            self.assertEqual(result['status'],'ready',result)
            options=self.request('/api/data/reference-options?forecast_id=builtin-DF-20260928')
            row=next(r for r in options['references'] if r['id']==j['id'])
            self.assertEqual(row['matchedCount'],3)

    def test_http_unsafe_and_invalid_upload(self):
        attack=urllib.request.Request(self.base+"/api/data/imports",data=b"{}",headers={"Origin":"https://example.invalid","Content-Type":"application/json"})
        with self.assertRaises(urllib.error.HTTPError) as context: urllib.request.urlopen(attack,timeout=10)
        self.assertEqual(context.exception.code,403); context.exception.close()
        value=self.request("/api/data/imports",{"product":"DF","name":"invalid","source":"unknown","expectedFiles":1})
        job_id=value["id"]
        oversized=urllib.request.Request(self.base+f"/api/data/imports/{job_id}/files?filename=TEST_V1_GLB_SURFACE_FCST_2026092800_006.nc",data=b"x",headers={"Content-Type":"application/octet-stream","Content-Length":str(dm.MAX_FILE+1)})
        with self.assertRaises(urllib.error.HTTPError) as context: self.opener.open(oversized,timeout=10)
        self.assertEqual(context.exception.code,400); context.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request(f"/api/data/imports/{job_id}/files?filename=..%2Fx.nc",b"x",True)
        self.assertEqual(context.exception.code,400)
        context.exception.close()
        name="TEST_V1_GLB_SURFACE_FCST_2026092800_006.nc"
        result=self.request(f"/api/data/imports/{job_id}/files?filename={name}",b"invalid netcdf",True)
        self.assertEqual(result["files"][0]["status"],"invalid")
        result=self.request(f"/api/data/imports/{job_id}/finalize",{})
        self.assertEqual(result["status"],"failed")


if __name__ == "__main__": unittest.main()
