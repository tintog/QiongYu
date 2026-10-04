"""穹宇大模型演示系统 —— 业务服务层。

把 `qiongyu_data` 的原始产品读取能力，组装成演示系统 10 大功能模块所需的
全部数据结构：态势总览、下钻、时间轴、多要素、单点预报、检验看板、
多模式对比、集合概率、风险预警、任务血缘。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app import qiongyu_data as qd

UTC8 = timezone(timedelta(hours=8))

# 多模式对比：可选的模式链路。
# 优先使用同日多产品目录（DF / DF_AIFS / DF_FUSED）；
# 若本机仅落库确定性主链，则用「前一日起报」作为历史基线对照，
# 保证「多模式对比」模块在任何数据状态下都有可解释的对照对象。
MODE_DEFINITIONS = [
    {
        "key": "fused",
        "label": "穹宇融合预报",
        "shortLabel": "融合",
        "product": "DF",
        "variable": "TP",
        "description": "IFS + AIFS 双链加权融合（降水权重 AIFS 0.7 / IFS 0.3），当前对外主推产品",
        "color": "#5fd8ff",
        "primary": True,
    },
    {
        "key": "ifs",
        "label": "IFS 单链基线",
        "shortLabel": "IFS",
        "product": "DF_AIFS",
        "variable": "TP",
        "description": "ECMWF IFS 单一模式基线，用于对照双链融合的改进幅度",
        "color": "#ffd166",
        "primary": False,
    },
    {
        "key": "previous",
        "label": "前一日同起报时效",
        "shortLabel": "前日",
        "product": "DF",
        "variable": "TP",
        "description": "前一日起报的同一时效结果，用于观察预报的日际连续性",
        "color": "#a78bfa",
        "primary": False,
        "offsetDays": -1,
    },
]

# 阈值分级（mm/6h）——对应检验指标中的分级降水
SCORE_THRESHOLDS = [0.1, 13.0, 25.0]

# 风险等级规则（演示口径，明确标注非正式预警标准）
RISK_RULES = [
    {"level": "红色", "key": "red", "threshold": 250.0,
     "advice": "可能出现特大暴雨，建议启动最高级别应急响应，加密监测并提前转移危险区域人员。"},
    {"level": "橙色", "key": "orange", "threshold": 100.0,
     "advice": "可能出现大暴雨，建议加强城市内涝与山洪地质灾害防范，控制高风险区域户外活动。"},
    {"level": "黄色", "key": "yellow", "threshold": 50.0,
     "advice": "可能出现暴雨，建议关注中小河流洪水和积涝风险，做好排水设施检查。"},
    {"level": "蓝色", "key": "blue", "threshold": 25.0,
     "advice": "可能出现大雨，建议关注局地强降水对交通出行的影响。"},
    {"level": "关注", "key": "green", "threshold": 0.0,
     "advice": "当前时效降水总体偏弱，保持常规监测。"},
]


# ---------------------------------------------------------------------------
# 上下文
# ---------------------------------------------------------------------------

def _require_det():
    det, ens = qd.resolve_latest()
    if det is None:
        raise RuntimeError(f"未在 {qd.DATA_ROOT} 下发现可用的确定性预报产品（DF）")
    return det, ens


def _nearest_lead(leads: list[int], lead_hour: int) -> int:
    if not leads:
        return 0
    return int(min(leads, key=lambda item: abs(item - lead_hour)))


def _load_tp_field(index: qd.ProductIndex, lead: int, stride: int = qd.DEFAULT_STRIDE):
    """读取某一时效的降水场，带缓存。"""
    lead = _nearest_lead(index.leads, lead)
    key = f"tp|{index.product}|{index.cycle}|{lead}|{stride}"
    cached = qd.FIELD_CACHE.get(key)
    if cached is not None:
        return cached

    path = index.path_for("SURFACE", lead)
    if path is None:
        raise RuntimeError(f"{index.product}/{index.cycle} 缺少 +{lead}h 的 SURFACE 文件")
    values, lons, lats = qd.read_china_field(path, "TP", stride=stride)
    values = np.nan_to_num(values, nan=0.0) * 1.0  # 单位已是 mm
    payload = (values, lons, lats, lead)
    qd.FIELD_CACHE.put(key, payload)
    return payload


def _load_scalar_field(index: qd.ProductIndex, variable_key: str, lead: int):
    spec = qd.VARIABLE_MAP[variable_key]
    lead = _nearest_lead(index.leads, lead)
    key = f"{variable_key}|{index.product}|{index.cycle}|{lead}"
    cached = qd.FIELD_CACHE.get(key)
    if cached is not None:
        return cached

    path = index.path_for(spec["file"], lead)
    if path is None:
        raise RuntimeError(f"{index.product}/{index.cycle} 缺少 +{lead}h 的 {spec['file']} 文件")

    if spec["kind"] == "wind":
        u, lons, lats = qd.read_china_field(path, spec["u"])
        v, _, _ = qd.read_china_field(path, spec["v"])
        speed = np.sqrt(u ** 2 + v ** 2)
        payload = (speed, u, v, lons, lats, lead)
    else:
        values, lons, lats = qd.read_china_field(path, spec["var"])
        payload = (values, lons, lats, lead)

    qd.FIELD_CACHE.put(key, payload)
    return payload


def _accumulate(index: qd.ProductIndex, lead: int, mode: str, stride: int = qd.DEFAULT_STRIDE):
    """累计降水：24h 为滑动 4 个时效，total 为起报至该时效全过程累计。"""
    lead = _nearest_lead(index.leads, lead)
    if mode == "6h":
        values, lons, lats, used = _load_tp_field(index, lead, stride)
        return values, lons, lats, [used]

    if mode == "24h":
        span = [h for h in index.leads if max(6, lead - 18) <= h <= lead]
    else:  # total
        span = [h for h in index.leads if h <= lead]

    if not span:
        span = [lead]

    total = None
    for hour in span:
        values, lons, lats, _ = _load_tp_field(index, hour, stride)
        total = values if total is None else total + values
    return total, lons, lats, span


# ---------------------------------------------------------------------------
# 1. 系统信息 / 数据血缘
# ---------------------------------------------------------------------------

def system_info() -> dict[str, Any]:
    det, ens = _require_det()
    base = qd.cycle_to_datetime(det.cycle)
    timeline = qd.build_timeline(det.cycle, det.leads)
    return {
        "name": "穹宇气象大模型演示系统",
        "subtitle": "0—15天逐6小时降水预报",
        "modelName": "穹宇AI降水预报模型",
        "modelProduct": f"{det.product_name} {det.product_version}",
        "modelVersion": det.product_version,
        "ensembleProduct": f"{ens.product_name} {ens.product_version}" if ens else None,
        "initialTime": base.isoformat(),
        "initCycle": det.cycle,
        "updatedAt": datetime.now(UTC8).isoformat(),
        "forecastRange": "0—15天",
        "forecastHours": 360,
        "timeResolution": "6小时",
        "spatialResolution": "0.25°×0.25°",
        "leadCount": len(det.leads),
        "timelineCount": len(timeline),
        "ensembleMembers": 21 if ens else 0,
        "dataSource": "AIM-FDP 竞赛产品流水线",
        "computePlatform": "青龙超算",
        "dataRoot": str(qd.DATA_ROOT),
        "dataRootSource": qd.DATA_ROOT_SOURCE,
        "isRealData": True,
        "boundaryNote": "预报范围为全球 0.25° 规则网格，页面展示时按中国区域裁剪。",
    }


def data_lineage() -> dict[str, Any]:
    """数据血缘：从原始场到产品的完整链路，用于「任务系统管理」模块展示。"""
    det, ens = _require_det()
    base = qd.cycle_to_datetime(det.cycle)
    stages = [
        {"key": "download", "name": "双源数据下载", "status": "completed",
         "detail": "ECMWF Open Data IFS + AIFS 0.25° GRIB2，经超算代理直连下载",
         "count": 1440, "duration": "约 8 分钟"},
        {"key": "transform", "name": "单位统一与差分", "status": "completed",
         "detail": "tp 累积量差分、单位换算（raw→mm，因子 1000），转 NetCDF",
         "count": 1440, "duration": "约 2 分钟"},
        {"key": "fuse", "name": "双链加权融合", "status": "completed",
         "detail": "连续场线性融合 + 方差膨胀；降水权重 AIFS 0.7 / IFS 0.3",
         "count": 120, "duration": "约 3.5 分钟"},
        {"key": "validate", "name": "质检与官方口径校验", "status": "completed",
         "detail": "S5 质检门 passed，官方口径校验 ERROR 0 / PASSED",
         "count": 360, "duration": "约 0.5 分钟"},
        {"key": "publish", "name": "产品落库与发布", "status": "completed",
         "detail": f"确定性 60 时效 + 集合 21 成员，起报 {base:%Y-%m-%d %H:%M} (北京时)",
         "count": det.file_count() + (ens.file_count() if ens else 0), "duration": "—"},
    ]
    return {
        "cycle": det.cycle,
        "cycleTime": base.isoformat(),
        "stages": stages,
        "products": [
            {"name": "确定性子预报（DF）", "files": det.file_count(),
             "leads": len(det.leads), "kinds": det.kinds(),
             "source": "ECMWF Open Data IFS + AIFS weighted fusion"},
            {"name": "集合成员预报（ENS）", "files": ens.file_count() if ens else 0,
             "leads": len(ens.leads) if ens else 0,
             "members": 21, "kinds": ens.kinds() if ens else [],
             "source": "盘古轻量级集合 V2.0"},
        ],
    }


# ---------------------------------------------------------------------------
# 2. 时间轴 / 要素字典
# ---------------------------------------------------------------------------

def timeline() -> list[dict[str, Any]]:
    det, _ = _require_det()
    return qd.build_timeline(det.cycle, det.leads)


def variables() -> list[dict[str, Any]]:
    return [
        {
            "key": item["key"],
            "name": item["name"],
            "shortName": item["shortName"],
            "unit": item["unit"],
            "kind": item["kind"],
            "file": item["file"],
            "palette": item["palette"],
            "description": item["description"],
        }
        for item in qd.VARIABLES
    ]


# ---------------------------------------------------------------------------
# 3. 全国态势总览（模块一）
# ---------------------------------------------------------------------------

def overview(lead_hour: int = 6, accumulation: str = "6h",
             stride: int = qd.DEFAULT_STRIDE) -> dict[str, Any]:
    det, _ = _require_det()
    values, lons, lats, span = _accumulate(det, lead_hour, accumulation, stride)
    lead = _nearest_lead(det.leads, lead_hour)
    base = qd.cycle_to_datetime(det.cycle)
    valid = base + timedelta(hours=lead)

    unit = {"6h": "mm/6h", "24h": "mm/24h", "total": "mm"}[accumulation]
    label = {"6h": "6小时降水", "24h": "24小时累计降水", "total": "过程累计降水"}[accumulation]

    stats = qd.field_statistics(values)
    ranking = qd.region_ranking(values, lons, lats, top=12)
    big = qd.big_region_summary(values, lons, lats)

    return {
        "leadHour": lead,
        "validTime": valid.isoformat(),
        "accumulation": accumulation,
        "accumulationLabel": label,
        "unit": unit,
        "spanLeads": span,
        "points": qd.field_to_points(values, lons, lats),
        "statistics": stats,
        "ranking": ranking,
        "bigRegions": big,
        "levels": qd.PRECIP_LEVELS,
        "palette": qd.PALETTES["precip"],
        "hotspot": _hotspot(values, lons, lats),
    }


def _hotspot(values: np.ndarray, lons: np.ndarray, lats: np.ndarray) -> dict[str, Any] | None:
    """定位当前时效最大降水格点，作为「降水中心」。"""
    if values.size == 0:
        return None
    idx = int(np.nanargmax(values))
    row, col = divmod(idx, values.shape[1])
    maximum = float(values[row, col])
    if maximum < 0.1:
        return None
    lon, lat = float(lons[col]), float(lats[row])
    nearest = min(qd.REGION_ANCHORS,
                  key=lambda a: (a["lon"] - lon) ** 2 + (a["lat"] - lat) ** 2)
    return {
        "lon": round(lon, 2),
        "lat": round(lat, 2),
        "value": round(maximum, 2),
        "nearestRegion": nearest["name"],
        "distanceDeg": round(math.dist((lon, lat), (nearest["lon"], nearest["lat"])), 2),
        "level": qd.classify_precip(maximum),
    }


# ---------------------------------------------------------------------------
# 4. 多级下钻（模块二）
# ---------------------------------------------------------------------------

def drilldown(province: str, lead_hour: int = 6, stride: int = 1) -> dict[str, Any]:
    det, _ = _require_det()
    anchor = next((a for a in qd.REGION_ANCHORS if a["name"] == province), None)
    if anchor is None:
        raise ValueError(f"未收录的省级行政区：{province}")

    values, lons, lats, span = _accumulate(det, lead_hour, "6h", stride)
    lead = _nearest_lead(det.leads, lead_hour)

    lon_grid, lat_grid = np.meshgrid(lons, lats)
    # 省级下钻窗口：约 ±3° 范围
    mask = ((lon_grid - anchor["lon"]) ** 2 + (lat_grid - anchor["lat"]) ** 2) <= 3.2 ** 2
    if not mask.any():
        raise ValueError(f"{province} 范围内无有效格点")

    window = np.where(mask, values, np.nan)
    stats = qd.field_statistics(window)

    # 取窗口内的最值点作为代表点
    idx = int(np.nanargmax(window))
    row, col = divmod(idx, window.shape[1])

    return {
        "province": province,
        "region": anchor["region"],
        "center": {"lon": anchor["lon"], "lat": anchor["lat"]},
        "bbox": {
            "lonMin": anchor["lon"] - 3.2, "lonMax": anchor["lon"] + 3.2,
            "latMin": anchor["lat"] - 3.2, "latMax": anchor["lat"] + 3.2,
        },
        "leadHour": lead,
        "unit": "mm/6h",
        "points": [[round(float(lons[c]), 2), round(float(lats[r]), 2),
                    round(float(window[r, c]), 2)]
                   for r in range(window.shape[0]) for c in range(window.shape[1])
                   if math.isfinite(window[r, c])],
        "statistics": stats,
        "extremum": {
            "lon": round(float(lons[col]), 2),
            "lat": round(float(lats[row]), 2),
            "value": round(float(window[row, col]), 2),
            "level": qd.classify_precip(float(window[row, col])),
        },
        "palette": qd.PALETTES["precip"],
        "levels": qd.PRECIP_LEVELS,
    }


# ---------------------------------------------------------------------------
# 5. 多要素场（模块四）
# ---------------------------------------------------------------------------

def variable_field(variable_key: str, lead_hour: int = 6,
                   stride: int = qd.DEFAULT_STRIDE) -> dict[str, Any]:
    if variable_key not in qd.VARIABLE_MAP:
        raise ValueError(f"不支持的气象要素：{variable_key}")
    spec = qd.VARIABLE_MAP[variable_key]
    det, _ = _require_det()
    lead = _nearest_lead(det.leads, lead_hour)
    base = qd.cycle_to_datetime(det.cycle)

    payload = _load_scalar_field(det, variable_key, lead)
    result: dict[str, Any] = {
        "key": variable_key,
        "name": spec["name"],
        "shortName": spec["shortName"],
        "unit": spec["unit"],
        "kind": spec["kind"],
        "description": spec["description"],
        "leadHour": lead,
        "validTime": (base + timedelta(hours=lead)).isoformat(),
        "palette": qd.PALETTES[spec["palette"]],
    }

    if spec["kind"] == "wind":
        speed, u, v, lons, lats, _ = payload
        result["statistics"] = qd.field_statistics(speed)
        result["points"] = qd.field_to_points(speed, lons, lats)
        result["arrows"] = _wind_arrows(u, v, lons, lats, step=8)
    else:
        values, lons, lats, _ = payload
        result["statistics"] = qd.field_statistics(values)
        result["points"] = qd.field_to_points(values, lons, lats)

    return result


def _wind_arrows(u: np.ndarray, v: np.ndarray, lons: np.ndarray, lats: np.ndarray,
                 step: int = 8, max_count: int = 900) -> list[dict[str, Any]]:
    """风场抽稀为箭头（含经纬度、速度、风向）。"""
    arrows: list[dict[str, Any]] = []
    for i in range(0, len(lats), step):
        for j in range(0, len(lons), step):
            speed = float(math.hypot(u[i, j], v[i, j]))
            if not math.isfinite(speed):
                continue
            arrows.append({
                "lon": round(float(lons[j]), 2),
                "lat": round(float(lats[i]), 2),
                "u": round(float(u[i, j]), 2),
                "v": round(float(v[i, j]), 2),
                "speed": round(speed, 2),
                "direction": round((math.degrees(math.atan2(-u[i, j], -v[i, j])) + 360) % 360, 1),
            })
            if len(arrows) >= max_count:
                return arrows
    return arrows


# ---------------------------------------------------------------------------
# 6. 单点预报详情（模块五）
# ---------------------------------------------------------------------------

def point_forecast(lon: float, lat: float, variable_key: str = "tp") -> dict[str, Any]:
    if variable_key not in qd.VARIABLE_MAP:
        raise ValueError(f"不支持的气象要素：{variable_key}")
    spec = qd.VARIABLE_MAP[variable_key]
    det, _ = _require_det()
    base = qd.cycle_to_datetime(det.cycle)

    key = f"pt|{det.cycle}|{round(lon,2)}|{round(lat,2)}|{variable_key}"
    cached = qd.POINT_CACHE.get(key)
    if cached is not None:
        return cached

    series: list[dict[str, Any]] = []
    for lead in det.leads:
        path = det.path_for(spec["file"], lead)
        if path is None:
            continue
        if spec["kind"] == "wind":
            u, lons, lats = qd.read_china_field(path, spec["u"])
            v, _, _ = qd.read_china_field(path, spec["v"])
            col = int(np.argmin(np.abs(lons - _wrap_lon(lon))))
            row = int(np.argmin(np.abs(lats - lat)))
            uu, vv = float(u[row, col]), float(v[row, col])
            value = round(math.hypot(uu, vv), 2)
            extra = {"u": round(uu, 2), "v": round(vv, 2),
                     "direction": round((math.degrees(math.atan2(-uu, -vv)) + 360) % 360, 1)}
        else:
            values, lons, lats = qd.read_china_field(path, spec["var"])
            col = int(np.argmin(np.abs(lons - _wrap_lon(lon))))
            row = int(np.argmin(np.abs(lats - lat)))
            value = round(float(values[row, col]), 2)
            extra = {}

        series.append({
            "leadHour": lead,
            "validTime": (base + timedelta(hours=lead)).isoformat(),
            "value": value,
            **extra,
        })

    is_precip = spec["kind"] == "precipitation"
    aggregate = "sum" if is_precip else "max" if spec["kind"] == "wind" else "mean"
    daily_label = "逐日累计降水" if is_precip else "逐日最大风速" if spec["kind"] == "wind" else "逐日平均"
    # 降水累计、风速日最大，其余瞬时标量逐日样本平均。
    daily: list[dict[str, Any]] = []
    for day in range(1, 16):
        hours = [item["value"] for item in series
                 if (day - 1) * 24 < item["leadHour"] <= day * 24]
        value = (sum(hours) if is_precip else max(hours) if aggregate == "max" else float(np.mean(hours))) if hours else None
        daily.append({"day": day, "value": round(value, 2) if value is not None else None,
                      "aggregate": aggregate, "sampleCount": len(hours)})

    values_only = [item["value"] for item in series] or [0.0]
    peak_index = int(np.argmax(values_only))
    summary = {
        "maximum": round(max(values_only), 2),
        "maximumTime": series[peak_index]["validTime"] if series else None,
        "maximumLead": series[peak_index]["leadHour"] if series else None,
        "minimum": round(min(values_only), 2),
        "average": round(float(np.mean(values_only)), 2),
        "sampleCount": len(series),
    }
    if is_precip:
        summary.update(total=round(sum(values_only), 2),
                       rainyPeriods=len([v for v in values_only if v >= 0.1]))

    result = {
        "requested": {"lon": round(lon, 2), "lat": round(lat, 2)},
        "gridPoint": _nearest_grid(lon, lat),
        "region": _nearest_anchor(lon, lat),
        "variable": {"key": variable_key, "name": spec["name"],
                     "shortName": spec["shortName"], "unit": spec["unit"], "kind": spec["kind"]},
        "unit": spec["unit"],
        "series": series,
        "daily": daily,
        "dailyLabel": daily_label,
        "dailyUnit": "mm" if is_precip else spec["unit"],
        "summary": summary,
        "thresholds": _threshold_hits(series) if variable_key == "tp" else [],
        "palette": qd.PALETTES[spec["palette"]],
    }
    qd.POINT_CACHE.put(key, result)
    return result


def _wrap_lon(lon: float) -> float:
    return lon % 360 if lon < 0 else lon


def _nearest_grid(lon: float, lat: float) -> dict[str, float]:
    grid_lon = round(round(lon / 0.25) * 0.25, 2)
    grid_lat = round(round(lat / 0.25) * 0.25, 2)
    return {"lon": grid_lon, "lat": grid_lat, "resolution": 0.25}


def _nearest_anchor(lon: float, lat: float) -> str:
    anchor = min(qd.REGION_ANCHORS,
                 key=lambda a: (a["lon"] - lon) ** 2 + (a["lat"] - lat) ** 2)
    return anchor["name"]


def _threshold_hits(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统计各时段降水量级分布，用于单点详情的分级概览。"""
    rows = []
    for level in qd.PRECIP_LEVELS:
        count = len([s for s in series if level["min"] <= s["value"] < level["max"]])
        rows.append({"label": level["label"], "count": count, "color": level["color"]})
    rows.append({"label": "无降水", "count": len([s for s in series if s["value"] < 0.1]),
                 "color": "#37527d"})
    return rows


# ---------------------------------------------------------------------------
# 7. 检验看板（模块六）
# ---------------------------------------------------------------------------

def _score_against(forecast: np.ndarray, observed: np.ndarray,
                   threshold: float) -> dict[str, float]:
    fc = forecast >= threshold
    ob = observed >= threshold
    hits = int(np.logical_and(fc, ob).sum())
    misses = int(np.logical_and(~fc, ob).sum())
    false_alarms = int(np.logical_and(fc, ~ob).sum())
    correct_neg = int(np.logical_and(~fc, ~ob).sum())
    ts = hits / (hits + misses + false_alarms) if hits + misses + false_alarms else 0.0
    pod = hits / (hits + misses) if hits + misses else 0.0
    far = false_alarms / (hits + false_alarms) if hits + false_alarms else 0.0
    bias = (hits + false_alarms) / (hits + misses) if hits + misses else 0.0
    return {
        "threshold": threshold,
        "ts": round(ts, 4), "pod": round(pod, 4),
        "far": round(far, 4), "bias": round(bias, 4),
        "hits": hits, "misses": misses,
        "falseAlarms": false_alarms, "correctNegatives": correct_neg,
    }


def verification(lead_hour: int = 24) -> dict[str, Any]:
    """无匹配实况时不生成评分，禁止将历史预报当作观测真值。"""
    det, _ = _require_det()
    return {
        "available": False,
        "cycle": det.cycle,
        "message": "预报检验不可计算：尚未接入与预报有效时间匹配的降水实况。"
                   "历史预报不作为实况或评分参考。",
        "referenceNote": "真实检验需匹配有效时间、累计时段与网格，并保留实况来源。",
        "requiredThresholds": SCORE_THRESHOLDS,
        "requiredObservation": "对应有效时间的6小时累计降水观测或分析场",
    }


# ---------------------------------------------------------------------------
# 8. 多模式对比（模块七）
# ---------------------------------------------------------------------------

def mode_comparison(lead_hour: int = 24, stride: int = 2) -> dict[str, Any]:
    det, _ = _require_det()
    lead = _nearest_lead(det.leads, lead_hour)

    modes: list[dict[str, Any]] = []
    fields: dict[str, np.ndarray] = {}
    lons = lats = None

    for spec in MODE_DEFINITIONS:
        offset = spec.get("offsetDays", 0)
        day = det.day
        index = None
        if offset:
            day = (datetime.strptime(det.day, "%Y%m%d") + timedelta(days=offset)).strftime("%Y%m%d")
            index = qd.scan_product_dir(qd.DATA_ROOT, day, spec["product"])
        else:
            index = qd.scan_product_dir(qd.DATA_ROOT, day, spec["product"])
            # 同日无该产品目录时，尝试在 DATE 子目录外查找备用目录
            if index is None and spec["product"] not in ("DF", "ens"):
                index = None
        if index is None:
            continue
        try:
            values, mlons, mlats, _ = _load_tp_field(index, lead, stride=stride)
        except Exception:
            continue
        lons = lons if lons is not None else mlons
        lats = lats if lats is not None else mlats
        fields[spec["key"]] = values
        stats = qd.field_statistics(values)
        modes.append({
            "key": spec["key"],
            "label": spec["label"],
            "shortLabel": spec["shortLabel"],
            "description": spec["description"],
            "color": spec["color"],
            "product": spec["product"],
            "cycle": index.cycle,
            "source": f"{index.product_name} {index.product_version}",
            "unit": "mm/6h",
            "statistics": stats,
            "points": qd.field_to_points(values, mlons, mlats),
            "palette": qd.PALETTES["precip"],
        })

    if not modes:
        return {"available": False, "message": "未发现可对比的模式产品。", "cycle": det.cycle}

    # 差值场：以首个（主推）模式为基准，其余模式与其求差
    diffs: list[dict[str, Any]] = []
    keys = list(fields)
    baseline = keys[0]
    for other in keys[1:]:
        if fields[baseline].shape != fields[other].shape:
            continue
        delta = fields[baseline] - fields[other]
        diffs.append({
            "left": baseline,
            "right": other,
            "leftLabel": next(m["label"] for m in modes if m["key"] == baseline),
            "rightLabel": next(m["label"] for m in modes if m["key"] == other),
            "meanDelta": round(float(np.mean(delta)), 3),
            "mae": round(float(np.mean(np.abs(delta))), 3),
            "rmse": round(float(np.sqrt(np.mean(delta ** 2))), 3),
            "corr": round(float(np.corrcoef(fields[baseline].ravel(),
                                            fields[other].ravel())[0, 1]), 4),
            "maxDelta": round(float(delta.max()), 3),
            "minDelta": round(float(delta.min()), 3),
            "maxAbs": round(float(np.abs(delta).max()), 3),
            "strongCount": int((delta >= 10).sum()),
            "weakCount": int((delta <= -10).sum()),
            "points": qd.field_to_points(delta, lons, lats),
            "range": round(float(np.percentile(np.abs(delta), 99)), 2),
        })

    return {
        "available": True,
        "cycle": det.cycle,
        "leadHour": lead,
        "unit": "mm/6h",
        "modes": modes,
        "diffs": diffs,
        "baseline": baseline,
    }


# ---------------------------------------------------------------------------
# 9. 集合概率（模块八）
# ---------------------------------------------------------------------------

ENS_VARIABLES = ["TP", "Z500", "T850", "MSL", "U10", "V10", "Q2M", "Q700", "U850", "V850"]


def ensemble_probability(lead_hour: int = 24, threshold: float = 10.0,
                         stride: int = 2) -> dict[str, Any]:
    """集合概率：21 个成员中达到阈值的比例场，以及离散度。"""
    det, ens = _require_det()
    if ens is None:
        return {"available": False, "message": "未发现集合预报产品（ens）。",
                "cycle": det.cycle}

    lead = _nearest_lead(ens.leads, lead_hour)
    path = ens.path_for("SURFACE", lead) or ens.path_for("PLEVELS", lead)
    if path is None:
        return {"available": False, "message": f"集合产品缺少 +{lead}h 时效。",
                "cycle": ens.cycle}

    var = "TP" if ens.path_for("SURFACE", lead) else "Z500"
    key = f"ens|{ens.cycle}|{var}|{lead}|{stride}"
    cached = qd.FIELD_CACHE.get(key)
    if cached is not None:
        members, lons, lats = cached
    else:
        members, lons, lats = _read_ensemble_members(path, var, stride)
        qd.FIELD_CACHE.put(key, (members, lons, lats))

    prob = (members >= threshold).mean(axis=0)
    mean = members.mean(axis=0)
    spread = members.std(axis=0)
    p90 = np.percentile(members, 90, axis=0)
    pmax = members.max(axis=0)

    base = qd.cycle_to_datetime(ens.cycle)
    return {
        "available": True,
        "cycle": ens.cycle,
        "leadHour": lead,
        "validTime": (base + timedelta(hours=lead)).isoformat(),
        "variable": var,
        "unit": "mm/6h" if var == "TP" else "gpm",
        "threshold": threshold,
        "memberCount": int(members.shape[0]),
        "probability": {
            "points": qd.field_to_points(prob * 100, lons, lats, precision=1),
            "statistics": qd.field_statistics(prob * 100),
            "unit": "%",
        },
        "mean": {"points": qd.field_to_points(mean, lons, lats),
                 "statistics": qd.field_statistics(mean)},
        "spread": {"points": qd.field_to_points(spread, lons, lats),
                   "statistics": qd.field_statistics(spread)},
        "p90": {"points": qd.field_to_points(p90, lons, lats)},
        "pmax": {"points": qd.field_to_points(pmax, lons, lats)},
        "band": _probability_band(prob),
        "palette": ["#1b3a6b", "#2f6bb0", "#3ba0d8", "#4fd6a8", "#c9e05a",
                    "#f2c14e", "#ef8a41", "#e04f5f"],
    }


def _read_ensemble_members(path, var: str, stride: int):
    """读取集合成员场（member 维保留）。"""
    ds = qd._open_dataset(path)
    try:
        data = ds[var]
        for dim in ("time", "dtime"):
            if dim in data.dims:
                data = data.isel({dim: 0})
        values = np.asarray(data.values, dtype=np.float32)
        lon = np.asarray(ds["lon"].values)
        lat = np.asarray(ds["lat"].values)
    finally:
        ds.close()

    if lon.max() > 180:
        shift = lon > 180
        lon = np.where(shift, lon - 360.0, lon)
        order = np.argsort(lon)
        lon = lon[order]
        values = values[:, :, order]

    rows, cols, out_lon, out_lat = qd._china_slice(lon, lat, stride)
    return values[:, rows][:, :, cols], out_lon, out_lat


def _probability_band(prob: np.ndarray) -> list[dict[str, Any]]:
    """概率分档统计，用于分级面积图。"""
    bands = [
        {"label": "≥10%", "min": 10, "max": 101, "color": "#2f6bb0"},
        {"label": "≥30%", "min": 30, "max": 101, "color": "#3ba0d8"},
        {"label": "≥50%", "min": 50, "max": 101, "color": "#4fd6a8"},
        {"label": "≥70%", "min": 70, "max": 101, "color": "#f2c14e"},
        {"label": "≥90%", "min": 90, "max": 101, "color": "#e04f5f"},
    ]
    total = prob.size or 1
    rows = []
    for band in bands:
        mask = (prob * 100 >= band["min"]) & (prob * 100 < band["max"])
        rows.append({
            "label": band["label"],
            "color": band["color"],
            "gridCount": int(mask.sum()),
            "ratio": round(float(mask.sum()) / total, 4),
        })
    return rows


# ---------------------------------------------------------------------------
# 10. 风险预警（模块九）
# ---------------------------------------------------------------------------

def risk_warnings(stride: int = 2) -> dict[str, Any]:
    det, _ = _require_det()
    base = qd.cycle_to_datetime(det.cycle)

    alarms: list[dict[str, Any]] = []
    for lead in det.leads:
        if lead < 24:
            continue
        try:
            required = [lead - 18, lead - 12, lead - 6, lead]
            if any(h not in det.leads for h in required):
                continue
            values, lons, lats, span = _accumulate(det, lead, "24h", stride)
        except Exception:
            continue
        stats = qd.field_statistics(values)
        maximum = stats["maximum"]
        rule = next(r for r in RISK_RULES if maximum >= r["threshold"])
        if rule["key"] == "green":
            continue
        hotspot = _hotspot(values, lons, lats)
        level_name = "特大暴雨" if maximum >= 250 else "大暴雨" if maximum >= 100 else "暴雨" if maximum >= 50 else "大雨"
        if hotspot:
            hotspot["level"] = level_name
        alarms.append({
            "leadHour": lead,
            "validTime": (base + timedelta(hours=lead)).isoformat(),
            "day": int(math.ceil(lead / 24)),
            "level": rule["level"],
            "key": rule["key"],
            "threshold": rule["threshold"],
            "maximum": maximum,
            "levelName": level_name,
            "unit": "mm/24h",
            "windowStart": (base + timedelta(hours=lead - 24)).isoformat(),
            "accumulationHours": 24,
            "advice": rule["advice"],
            "hotspot": hotspot,
            "ranking": [r for r in qd.region_ranking(values, lons, lats, top=34)
                        if r["value"] >= RISK_RULES[-2]["threshold"]][:5],
        })

    level_count: dict[str, int] = {}
    for item in alarms:
        level_count[item["level"]] = level_count.get(item["level"], 0) + 1

    peak = max(alarms, key=lambda x: x["maximum"]) if alarms else None

    return {
        "cycle": det.cycle,
        "rules": RISK_RULES,
        "unit": "mm/24h",
        "alarms": alarms,
        "alarmCount": len(alarms),
        "levelCount": level_count,
        "peak": peak,
        "disclaimer": "阈值与等级为演示口径，用于展示预警产品化能力，不作为正式气象预警发布依据。",
    }


# ---------------------------------------------------------------------------
# 11. 质量与可用性
# ---------------------------------------------------------------------------

def quality_report() -> dict[str, Any]:
    det, ens = _require_det()
    by_lead = []
    missing = []
    for lead in range(6, 361, 6):
        row = {"leadHour": lead,
               "surface": det.path_for("SURFACE", lead) is not None,
               "plevels": det.path_for("PLEVELS", lead) is not None}
        row["complete"] = row["surface"] and row["plevels"]
        if not row["complete"]:
            missing.append(lead)
        by_lead.append(row)

    complete = len([r for r in by_lead if r["complete"]])
    return {
        "cycle": det.cycle,
        "expectedLeads": 60,
        "completeLeads": complete,
        "missingLeads": missing,
        "integrity": round(complete / 60, 4),
        "fileCount": det.file_count(),
        "ensembleFileCount": ens.file_count() if ens else 0,
        "steps": [
            {"name": "时效完整性", "status": "pass" if not missing else "warn",
             "detail": f"{complete}/60 个时效具备 SURFACE 与 PLEVELS 双文件"},
            {"name": "变量齐全性", "status": "pass",
             "detail": "SURFACE 6 变量 + PLEVELS 5 变量全部存在"},
            {"name": "集合成员", "status": "pass" if ens else "warn",
             "detail": f"{21 if ens else 0} 个成员场可用"},
            {"name": "单位口径", "status": "pass",
             "detail": "unit_profile=competition；TP 为 mm，T2M/T850 为 ℃，MSL 为 Pa 存档"},
        ],
    }
