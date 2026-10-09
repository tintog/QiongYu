"""Local, append-only dataset registry. Uploaded files never replace source products."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
import copy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app import qiongyu_data as qd
from app import import_metadata as im

STORE = Path(os.environ.get("QIONGYU_MANAGED_ROOT", str(qd.PROJECT_ROOT / "managed_data")))
LOCK = threading.RLock()
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 240
_builtin_cache = {}
_hash_cache = {}
REQUIRED = {
    "DF": {"SURFACE": ["TP", "T2M", "U10", "V10", "Q2M", "MSL"],
           "PLEVELS": ["Z500", "Q700", "T850", "U850", "V850"]},
    "ens": {"SURFACE": ["TP"], "PLEVELS": ["Z500"]},
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def job_path(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("无效导入任务编号")
    return STORE / "batches" / job_id


def job(job_id):
    value = _read(job_path(job_id) / "manifest.json")
    if value is None:
        raise ValueError("导入任务不存在")
    return value


def create_job(product, name, source, model, expected, staged=False):
    if product not in {*REQUIRED, 'obs'} or not 1 <= expected <= MAX_FILES:
        raise ValueError("只支持DF/ens/obs，每批1—240个NetCDF文件")
    if not staged and (not name.strip() or not source.strip()):
        raise ValueError("请填写批次名称及来源（未知来源请明确填写未知）")
    value = {"id": uuid.uuid4().hex, "product": product, "name": name.strip() or '待识别批次',
             "source": source.strip() or '未核实', "model": model.strip() or "未声明", 'staged':staged, 'metadataConfirmed':not staged,
             "sourceVerified": False, "expectedFiles": expected, "files": [],
             "status": "uploading", "createdAt": _now(), "bytes": 0,
             "errors": [], "warnings": []}
    with LOCK:
        _save(job_path(value["id"]) / "manifest.json", value)
    return value


def safe_filename(filename, product=None):
    if (not filename or len(filename) > 180 or re.search(r'[<>"|?*\x00-\x1f]', filename) or "/" in filename or "\\" in filename
            or ":" in filename or ".." in filename or not (re.fullmatch(r'OBS_ANALYSIS_\d{10}\.nc', filename) if product == 'obs' else qd._FILE_RE.fullmatch(filename))):
        raise ValueError("文件名不符合当前产品格式，或包含不安全路径")
    return filename


def _unit_ok(var, unit):
    normalized = str(unit).lower().replace(" ", "")
    if var in ("MSL", "Q2M", "Q700"):
        qd.normalize_display_units(np.array([1.]), var, unit)
    else:
        accepted = ({"mm", "mm/6h"} if var == "TP" else
                    {"degc", "℃", "celsius", "degrees_celsius"} if var in ("T2M", "T850") else
                    {"gpm", "m"} if var == "Z500" else {"m/s", "ms-1", "ms**-1"})
        if normalized not in accepted:
            raise ValueError(f"{var}单位 {unit!r} 不受当前读取器支持")


def inspect_file(path, product):
    if product == 'obs':
        from app import observation_data
        return observation_data.inspect(path)
    match = qd._FILE_RE.fullmatch(path.name)
    if not match:
        raise ValueError("文件命名无法识别")
    kind, lead = match["kind"].upper(), int(match["lead"])
    cycles = re.findall(r"(?<!\d)\d{10}(?!\d)", path.name)
    if len(cycles) != 1 or not 6 <= lead <= 360 or lead % 6:
        raise ValueError("需唯一10位起报时间及6—360小时的逐6小时时效")
    cycle = cycles[0]
    qd.cycle_to_datetime(cycle)
    with qd._open_dataset(path) as ds:
        if str(ds.attrs.get("init_time", "")) != cycle or int(ds.attrs.get("lead_hours", -1)) != lead:
            raise ValueError("文件名与init_time/lead_hours属性不一致")
        if ds.attrs.get("product_type") != ("deterministic" if product == "DF" else "ensemble"):
            raise ValueError("文件product_type与所选数据类型不一致")
        for dim in ("time", "dtime"):
            if ds.sizes.get(dim) != 1:
                raise ValueError("每文件必须包含单一time和dtime")
        if int(ds.dtime.values[0]) != lead:
            raise ValueError("dtime与文件时效不一致")
        expected = np.datetime64(datetime.strptime(cycle, "%Y%m%d%H"), "ns")
        if ds.time.values[0] != expected:
            raise ValueError("time与起报时间不一致（按UTC识别）")
        coords = {}
        for dim, low, high in (("lon", 70, 140), ("lat", 12, 56)):
            if dim not in ds.coords or ds[dim].dims != (dim,):
                raise ValueError("需一维lon/lat坐标")
            values = np.asarray(ds[dim].values, dtype=float)
            diffs = np.diff(values)
            if (values.size < 2 or values.size > (1440 if dim == "lon" else 721) or not np.isfinite(values).all()
                    or not (np.all(diffs > 0) or np.all(diffs < 0))
                    or not np.allclose(np.abs(diffs), .25)
                    or values.min() > low or values.max() < high):
                raise ValueError("第一版仅支持覆盖70—140°E、12—56°N的0.25°规则网格")
            coords[dim] = values.tolist()
        members = []
        if product == "ens":
            if "member" not in ds.coords or not 2 <= ds.sizes.get("member", 0) <= 64:
                raise ValueError("集合需至少2个明确编号的member")
            members = ds.member.values.tolist()
            if len(set(members)) != len(members):
                raise ValueError("集合成员编号重复")
        elif "member" in ds.dims:
            raise ValueError("确定性文件不能含member维")
        variables = REQUIRED[product][kind]
        units = {}
        expected_dims = (("member",) if product == "ens" else ()) + ("time", "dtime", "lat", "lon")
        for var in variables:
            if var not in ds or ds[var].dims != expected_dims:
                raise ValueError(f"缺少{var}或维度顺序不符合当前格式")
            units[var] = ds[var].attrs.get("units", "")
            _unit_ok(var, units[var])
            a = ds[var].values
            if not np.isfinite(a).all() or (var == "TP" and np.any(a < 0)):
                raise ValueError(f"{var}存在缺测/非有限值或负降水，不进入可用批次")
        if "TP" in variables:
            description = str(ds.TP.attrs.get("long_name", "")).lower()
            step = str(ds.attrs.get("tp_step_type", "")).lower()
            if "6-hour" not in description and "6-hour" not in step:
                raise ValueError("TP必须明确声明为6小时累计降水，不能将起报累计误作6小时量")
        grid_hash = hashlib.sha256(json.dumps(coords, sort_keys=True).encode()).hexdigest()
        return {"kind": kind, "lead": lead, "cycle": cycle, "units": units,
                "grid": grid_hash, "members": members,
                "gridInfo": {"lonCount": len(coords["lon"]), "latCount": len(coords["lat"]), "resolution": "0.25°"},
                "fileSource": str(ds.attrs.get("source", "未声明")), **im.metadata(ds,path.name)}


def record_file(job_id, filename, size):
    with LOCK:
        value = job(job_id)
        path = job_path(job_id) / "files" / filename
        item = {"name": filename, "bytes": size, "status": "valid"}
        try:
            item.update(inspect_file(path, value["product"]))
            with path.open('rb') as stream:
                item['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
        except Exception as exc:
            item.update(status="invalid", error=str(exc))
        value["files"].append(item)
        value["bytes"] += size
        _save(job_path(job_id) / "manifest.json", value)
        return value


def duplicate_batches(value):
    hashes=sorted(f.get('sha256','') for f in value['files'])
    if not hashes or not all(hashes):return []
    duplicates=[]
    for path in (STORE/'batches').glob('*/manifest.json'):
        other=_read(path)
        if other['id']!=value['id'] and other['product']==value['product'] and other['status']=='ready':
            other_hashes=sorted(f.get('sha256','') for f in other['files'])
            overlap=set(hashes)&set(other_hashes)
            if overlap:
                duplicates.append({'id':other['id'],'name':other['name'],'matchedFiles':len(overlap),'exact':hashes==other_hashes})
    if value['product'] in REQUIRED:
        for entry in _builtin_entries():
            if entry['product']!=value['product']:continue
            index=resolve(entry['id'])
            original=[]
            sizes={f['bytes'] for f in value['files']}
            for path in index.files.values():
                if path.stat().st_size not in sizes:continue
                signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
                if signature not in _hash_cache:
                    with path.open('rb') as stream:_hash_cache[signature]=hashlib.file_digest(stream,'sha256').hexdigest()
                original.append(_hash_cache[signature])
            overlap=set(hashes)&set(original)
            if overlap:duplicates.append({'id':entry['id'],'name':entry['name'],'matchedFiles':len(overlap),'exact':hashes==sorted(original) and len(hashes)==entry['fileCount']})
    return duplicates


def preview(job_id):
    with LOCK:
        value=job(job_id)
        result=im.summarize(value)
        result.update(id=job_id,duplicates=duplicate_batches(value),
                      errors=preview_errors(value),
                      complete=len(value['files'])==value['expectedFiles'])
        value['preview']=result
        _save(job_path(job_id)/'manifest.json',value)
        return result


def preview_errors(value):
    valid=[f for f in value['files'] if f['status']=='valid']
    if value['product']=='obs':
        from app import observation_data
        errors=observation_data.finalize(copy.deepcopy(value))['errors']
    else:
        errors=[f"{f['name']}：{f['error']}" for f in value['files'] if f['status']!='valid']
        if len(value['files'])!=value['expectedFiles']:errors.append('文件数量尚未达到声明数量')
        for key in ('cycle','grid','members'):
            if len({json.dumps(f[key]) for f in valid})!=1:errors.append('批次内'+key+'不一致或无有效文件')
        pairs={(f['kind'],f['lead']) for f in valid}
        if len(pairs)!=len(valid):errors.append('重复文件种类/时效')
        for lead in {f['lead'] for f in valid}:
            for kind in ('SURFACE','PLEVELS'):
                if (kind,lead) not in pairs:errors.append(f'+{lead}h缺少{kind}')
    for key in ('dataProduct','productVersion'):
        if len({f.get(key,'未声明') for f in valid})>1:errors.append('批次内产品或版本不一致，请分批导入')
    return list(dict.fromkeys(errors))


def update_metadata(job_id, fields):
    with LOCK:
        value=job(job_id)
        if value['status']!='uploading':raise ValueError('只有待入库任务可修改元数据')
        if not fields['name'].strip() or not fields['source'].strip():raise ValueError('请确认批次名称及来源；未知来源填未核实')
        value.update({k:(v.strip() if isinstance(v,str) else v) for k,v in fields.items()})
        value['productVersion']=fields.get('model','').strip() or '未声明'
        value['metadataConfirmed']=True
        _save(job_path(job_id)/'manifest.json',value)
        return value


def finalize(job_id):
    with LOCK:
        value = job(job_id)
        if value["status"] != "uploading":
            raise ValueError("该任务不能重复校验")
        if value.get('staged') and not value.get('metadataConfirmed'):
            raise ValueError('请先确认自动识别信息、名称及来源')
        if value.get('staged'):
            consistency=preview_errors(value)
            if consistency:
                value.update(status='failed',errors=consistency,canActivate=False)
                _save(job_path(job_id)/'manifest.json',value)
                return value
        duplicates=duplicate_batches(value)
        if value.get('staged') and duplicates and not value.get('allowDuplicate'):
            raise ValueError('文件内容与已有批次重复；请查看预览并明确确认重复登记')
        summary=im.summarize(value)
        for k in ('dataProduct','productVersion','institution','elementGroup','spatialProcessing'):
            value.setdefault(k,summary.get(k,'未声明'))
        value['duplicates']=duplicates
        if value['product'] == 'obs':
            from app import observation_data
            value = observation_data.finalize(value)
            if duplicates:value['warnings'].append('全部或部分文件与已有批次重复；重复文件不代表新增数据')
            _save(job_path(job_id) / 'manifest.json', value)
            return value
        files = value["files"]
        errors = [f"{f['name']}：{f['error']}" for f in files if f["status"] != "valid"]
        if len(files) != value["expectedFiles"]:
            errors.append("上传文件数量与声明不一致")
        valid = [f for f in files if f["status"] == "valid"]
        for key, label in (("cycle", "起报时间"), ("grid", "网格"), ("members", "成员编号")):
            if len({json.dumps(f[key]) for f in valid}) != 1:
                errors.append(f"批次内{label}不一致或没有有效文件")
        pairs = [(f["kind"], f["lead"]) for f in valid]
        if len(set(pairs)) != len(pairs):
            errors.append("存在重复的文件种类/时效")
        leads = sorted({f["lead"] for f in valid})
        for lead in leads:
            for kind in ("SURFACE", "PLEVELS"):
                if (kind, lead) not in pairs:
                    errors.append(f"+{lead}h缺少{kind}配套文件")
        value["errors"] = errors
        value["warnings"] = []
        if duplicates:value['warnings'].append('全部或部分文件与已有批次重复；重复文件不代表新增数据')
        value["status"] = "failed" if errors else "ready"
        if not errors:
            value["cycle"] = valid[0]["cycle"]
            value["leads"] = leads
            value["grid"] = valid[0]["gridInfo"]
            value["members"] = valid[0]["members"]
            missing = sorted(set(range(6, 361, 6)) - set(leads))
            value["missingLeads"] = missing
            if missing:
                value["warnings"].append(f"缺少{len(missing)}个15天时效，仅可展示已导入范围")
            value["canActivate"] = leads[:4] == [6, 12, 18, 24] and leads == list(range(6, max(leads) + 1, 6))
            if not value["canActivate"]:
                value["warnings"].append("时效未从+6h连续覆盖至至少+24h：已保存校验报告，但不可全局启用")
        _save(job_path(job_id) / "manifest.json", value)
        return value


def _builtin_entries():
    entries = []
    for product, days in qd.list_available_cycles(qd.DATA_ROOT).items():
        for day in days:
            index = qd.resolve_cycle(day, qd.DATA_ROOT, product)
            if not index:
                continue
            signature = (str(qd.DATA_ROOT), product, day, tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in index.files.values()))
            cached = _builtin_cache.get((product, day))
            if cached and cached[0] == signature:
                entries.append(dict(cached[1]))
                continue
            path = index.path_for("SURFACE", index.leads[0])
            with qd._open_dataset(path) as ds:
                source = str(ds.attrs.get("source", "内置交付文件；来源未声明"))
                metadata=im.metadata(ds,path.name)
                members = ds.member.values.tolist() if "member" in ds.coords else []
                grid = {"lonCount": ds.sizes["lon"], "latCount": ds.sizes["lat"], "resolution": "0.25°"}
            row = {"id": f"builtin-{product}-{day}", "product": product,
                   "name": f"{('确定性预报' if product == 'DF' else '内置集合')} · {index.cycle}",
                   "source": source, "sourceVerified": False, "model": f"{index.product_name} {index.product_version}",
                   "cycle": index.cycle, "leads": index.leads, "fileCount": index.file_count(), "grid": grid,
                   "members": members, "status": "ready", "builtin": True, "canActivate": True,
                   "warnings": ["内置交付数据；来源属性不等于独立来源认证"], "errors": [], **metadata}
            _builtin_cache[(product, day)] = (signature, row)
            entries.append(dict(row))
    return entries


def selection():
    with LOCK:
        return _read(STORE / "active.json", {})


def catalog():
    with LOCK:
        entries = _builtin_entries()
        jobs = []
        directory = STORE / "batches"
        if directory.exists():
            for path in directory.glob("*/manifest.json"):
                value = _read(path)
                jobs.append({k: v for k, v in value.items() if k != "files"})
                if value["status"] == "ready":
                    entries.append({**value, "builtin": False, "fileCount": len(value["files"])})
        active = selection()
        default_det, default_ens = qd.resolve_latest(qd.DATA_ROOT, use_active=False)
        selected_det = resolve(active["DF"]) if active.get("DF") else default_det
        for item in entries:
            if not item.get('builtin'):
                # Read legacy manifests without rewriting user data or renaming their batches.
                files=item.get('files',[])
                if files and 'dataProduct' not in files[0]:
                    with qd._open_dataset(job_path(item['id'])/'files'/files[0]['name']) as ds:
                        meta=im.metadata(ds,files[0]['name'])
                    files=[{**meta,**f} for f in files]
                derived=im.summarize({**item,'files':files})
                for key in ('dataProduct','productVersion','institution','elementGroup','spatialProcessing'):
                    item.setdefault(key,derived.get(key,'未声明'))
            times=item.get('validTimes')
            if not times:
                from datetime import timedelta
                init=datetime.strptime(item['cycle'],'%Y%m%d%H')
                times=[(init+timedelta(hours=h)).isoformat() for h in item['leads']]
            item['validTimeStart'],item['validTimeEnd']=min(times),max(times)
            fallback = default_det if item["product"] == "DF" else default_ens if item['product'] == 'ens' else None
            default_id = f"builtin-{item['product']}-{fallback.day}" if fallback else None
            item["active"] = item["id"] == active.get(item["product"], default_id)
            if item["product"] == "ens" and (selected_det is None or item["cycle"] != selected_det.cycle):
                item["active"] = False
            item["variables"] = [v for v in qd.VARIABLES if (set([v['u'],v['v']] if 'u' in v else [v['var']]) <= set(item.get('observationVariables',[])) if item['product']=='obs' else item["product"] == "DF" or v["key"] in ("tp", "z500"))]
            item.pop("files", None)
        return {"batches": entries, "jobs": jobs, "active": active, "limits": {"maxFiles": MAX_FILES, "maxFileBytes": MAX_FILE, "maxTotalBytes": MAX_TOTAL}}


def resolve(batch_id):
    if batch_id.startswith("builtin-"):
        match = re.fullmatch(r"builtin-(DF|ens)-(\d{8})", batch_id)
        if not match:
            raise ValueError("无效内置批次编号")
        index = qd.resolve_cycle(match[2], qd.DATA_ROOT, match[1])
        if index is None:
            raise ValueError("批次不存在")
        return index
    value = job(batch_id)
    if value["status"] != "ready":
        raise ValueError("批次未通过校验或已移除")
    if value['product'] == 'obs':
        raise ValueError('分析/实况参考批次不能作为预报读取')
    index = qd.ProductIndex(job_path(batch_id), value["cycle"][:8], value["product"])
    index.cycle = value["cycle"]
    index.init_hour = int(index.cycle[8:])
    index.product_name = value["model"]
    index.product_version = "导入数据"
    index.leads = value["leads"]
    index.files = {(f["kind"], f["lead"]): job_path(batch_id) / "files" / f["name"] for f in value["files"]}
    return index


def active_index(product, fallback):
    active = selection()
    if product in active and active[product] is None:
        return None
    batch_id = active.get(product)
    return resolve(batch_id) if batch_id else fallback


def activate(batch_id):
    with LOCK:
        item = next((x for x in catalog()["batches"] if x["id"] == batch_id), None)
        if not item or not item["canActivate"]:
            raise ValueError("该批次不可启用，请先查看校验报告")
        active = selection()
        if item["product"] == "DF":
            candidates = [x for x in catalog()["batches"] if x["product"] == "ens" and x["cycle"] == item["cycle"] and x.get("canActivate")]
            matching = next((x for x in candidates if x["id"] == active.get("ens")), None) or next(iter(candidates), None)
            active["ens"] = matching["id"] if matching else None
        elif item["product"] == "ens":
            det, _ = qd.resolve_latest()
            if det is None or item["cycle"] != det.cycle:
                raise ValueError("集合批次起报时间须与当前全局确定性预报一致，请先切换对应预报日期")
        active[item["product"]] = batch_id
        _save(STORE / "active.json", active)
        qd.FIELD_CACHE.clear()
        qd.POINT_CACHE.clear()
        return item


def remove(batch_id):
    with LOCK:
        value = job(batch_id)
        if batch_id in selection().values():
            raise ValueError("不能移除正在启用的批次，请先启用其他批次")
        value["status"] = "removed"
        _save(job_path(batch_id) / "manifest.json", value)
        return {"id": batch_id, "message": "已从可用列表移除，原始上传文件保留可恢复"}
