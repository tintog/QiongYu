"""Forecast differences, not verification scores. No nearest-lead substitution."""
from datetime import datetime, timedelta

import numpy as np

from app import dataset_manager as dm
from app import qiongyu_data as qd
from app import qiongyu_service as svc


def _lead(index, valid_time):
    t = datetime.fromisoformat(valid_time)
    if t.tzinfo is None:
        raise ValueError("有效时间必须包含时区")
    hour = (t - qd.cycle_to_datetime(index.cycle)).total_seconds() / 3600
    if not hour.is_integer() or int(hour) not in index.leads:
        raise ValueError("该批次没有所选有效时间，不能用相邻时效代替")
    return int(hour)


def _hours(index, variable, accumulation):
    spec = qd.VARIABLE_MAP[variable]
    hours = []
    for lead in index.leads:
        required = [lead-18, lead-12, lead-6, lead] if variable == "tp" and accumulation == "24h" else [lead]
        if all(h >= 6 and index.path_for(spec["file"], h) for h in required):
            hours.append(lead)
    return hours


def _field(index, variable, lead, accumulation, stride):
    cache_key = f"compare|{index.root}|{index.product}|{index.cycle}|{variable}|{lead}|{accumulation}|{stride}"
    cached = qd.FIELD_CACHE.get(cache_key)
    if cached is not None:
        return cached
    spec = qd.VARIABLE_MAP[variable]
    hours = [lead-18, lead-12, lead-6, lead] if variable == "tp" and accumulation == "24h" else [lead]
    if lead not in _hours(index, variable, accumulation):
        raise ValueError("缺少所选时效或完整累计时段")
    if index.product == "ens" and variable not in ("tp", "z500"):
        raise ValueError("当前集合文件不支持该要素")
    total = None
    for hour in hours:
        path = index.path_for(spec["file"], hour)
        if index.product == "ens":
            values, lons, lats = svc._read_ensemble_members(path, spec["var"], stride)
            values = values.mean(axis=0)
        elif spec["kind"] == "wind":
            u, lons, lats = qd.read_china_field(path, spec["u"], stride)
            v, _, _ = qd.read_china_field(path, spec["v"], stride)
            values = np.hypot(u, v)
        else:
            values, lons, lats = qd.read_china_field(path, spec["var"], stride)
        if total is not None and (not np.array_equal(lons, previous_lon) or not np.array_equal(lats, previous_lat)):
            raise ValueError("累计时段内网格不一致")
        total = values if total is None else total + values
        previous_lon, previous_lat = lons, lats
    result = (total, lons, lats)
    qd.FIELD_CACHE.put(cache_key, result)
    return result


def options(a, b, variable="tp", accumulation="6h", mode="cycles"):
    if a == b:
        raise ValueError("请选择两组不同批次")
    left, right = dm.resolve(a), dm.resolve(b)
    if mode not in ("cycles", "sources", "ensemble"):
        raise ValueError("未知对比类型")
    if mode == "cycles" and (left.product != "DF" or right.product != "DF" or left.cycle == right.cycle):
        raise ValueError("批次变化对比需不同起报时间的两组确定性产品")
    if mode == "sources" and (left.product != right.product or left.cycle != right.cycle):
        raise ValueError("来源对比需同起报时间、同产品类型，不代表来源已经独立认证")
    if mode == "ensemble" and (left.cycle != right.cycle or {left.product, right.product} != {"DF", "ens"}):
        raise ValueError("确定性/集合均值对照需同起报时间的一组确定性和一组集合")
    keys = [v["key"] for v in qd.VARIABLES if left.product == right.product == "DF" or v["key"] in ("tp", "z500")]
    if variable not in keys or accumulation not in ("6h", "24h"):
        raise ValueError("要素或累计模式不受双方支持")
    bases = [qd.cycle_to_datetime(x.cycle) for x in (left, right)]
    times = [{(base + timedelta(hours=h)).isoformat(): h for h in _hours(index, variable, accumulation)}
             for index, base in zip((left, right), bases)]
    common = sorted(times[0].keys() & times[1].keys())
    return {"variables": [v for v in qd.VARIABLES if v["key"] in keys],
            "times": [{"validTime": t, "leadA": times[0][t], "leadB": times[1][t]} for t in common],
            "message": "" if common else "没有双方共同有效时间/完整累计时段"}


def compare(a, b, variable, accumulation, valid_time, mode, stride=2, lon=120.15, lat=30.28):
    opts = options(a, b, variable, accumulation, mode)
    if valid_time not in [t["validTime"] for t in opts["times"]]:
        raise ValueError("所选时间不在共同有效时间范围")
    if not np.isfinite([lon, lat]).all() or not (70 <= lon <= 140 and 12 <= lat <= 56):
        raise ValueError("地点超出中国展示范围")
    indexes = [dm.resolve(a), dm.resolve(b)]
    metadata = {x["id"]: x for x in dm.catalog()["batches"]}
    spec = qd.VARIABLE_MAP[variable]
    unit = "mm/24h" if variable == "tp" and accumulation == "24h" else spec["unit"]
    fields = [_field(index, variable, _lead(index, valid_time), accumulation, stride) for index in indexes]
    values_a, lons, lats = fields[0]
    values_b, lons_b, lats_b = fields[1]
    if not np.array_equal(lons, lons_b) or not np.array_equal(lats, lats_b):
        raise ValueError("网格不一致：第一版不自动插值，禁止逐格点差值")
    delta = values_a - values_b
    sides = []
    for batch_id, index, (values, _, _) in zip((a, b), indexes, fields):
        info = metadata[batch_id]
        finite = values[np.isfinite(values)]
        sides.append({"id": batch_id, "name": info["name"] + ("（集合均值）" if index.product == "ens" else ""),
                      "source": info["source"], "model": info["model"], "cycle": index.cycle,
                      "leadHour": _lead(index, valid_time), "validTime": valid_time,
                      "points": qd.field_to_points(values, lons, lats),
                      "statistics": {"minimum": round(float(finite.min()), 2), "maximum": round(float(finite.max()), 2), "average": round(float(finite.mean()), 2)}})
    series = []
    grid_points = None
    for t in opts["times"]:
        point_values, gps = [], []
        for index in indexes:
            field, xs, ys = _field(index, variable, _lead(index, t["validTime"]), accumulation, 1)
            i, j = int(np.argmin(abs(ys-lat))), int(np.argmin(abs(xs-lon)))
            point_values.append(round(float(field[i, j]), 2))
            gps.append({"lon": float(xs[j]), "lat": float(ys[i])})
        series.append({"validTime": t["validTime"], "a": point_values[0], "b": point_values[1], "leadA": t["leadA"], "leadB": t["leadB"]})
        grid_points = gps
    finite_delta = delta[np.isfinite(delta)]
    return {"available": True, "sides": sides, "variable": spec, "unit": unit,
            "validTime": valid_time, "accumulation": accumulation,
            "difference": {"points": qd.field_to_points(delta, lons, lats), "label": "A − B",
                           "minimum": round(float(finite_delta.min()), 2), "maximum": round(float(finite_delta.max()), 2),
                           "mean": round(float(finite_delta.mean()), 2), "meanAbsolute": round(float(np.abs(finite_delta).mean()), 2)},
            "colorRange": [float(min(values_a.min(), values_b.min())), float(max(values_a.max(), values_b.max()))],
            "series": series, "requested": {"lon": lon, "lat": lat}, "gridPoints": grid_points,
            "note": "对齐有效时间及累计时段；A−B只表示产品差异，不是相对实况的误差，不用于准确性排名。区域统计为展示网格统计。"}
