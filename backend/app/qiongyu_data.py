"""穹宇气象大模型演示系统 —— 真实预报产品数据接入层。

数据来源：AIM-FDP 竞赛产品流水线（青龙超算 / 本机镜像）
    <root>/DF/<YYYYMMDD>/*.nc          确定性预报（IFS 主链）
    <root>/ens/<YYYYMMDD>/*.nc         集合预报（盘古轻量级集合 V2.0）

每个起报时次 120 个 NetCDF：
    PLEVELS  60 个（006..360，间隔 6h）：Z500 / Q700 / T850 / U850 / V850
    SURFACE  60 个（006..360，间隔 6h）：T2M / U10 / V10 / Q2M / MSL / TP

重要实现说明
------------
产品路径含中文（如 `预测结果`），netCDF4 / h5py 的 C 层在 Windows 上按 ANSI 打开
路径会失败（报 FileNotFoundError）。因此本模块统一采用
`open(path, 'rb').read()` → `io.BytesIO` → `h5netcdf` 引擎的方式打开，
在 Python 层完成路径解析，彻底规避该问题。
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

UTC8 = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 路径配置
#
# 数据根目录按以下优先级自动探测（第一个存在的即生效）：
#   1) 环境变量 QIONGYU_DATA_ROOT（显式指定，优先级最高）
#   2) 项目内 data/ 目录（便携数据包，随项目分发，解压即用）
#   3) 本机完整产品目录 D:\ZM\15GJQX\预测结果（开发机原始数据）
#
# 这样同一份代码既能在开发机读全量数据，也能在他人机器上读便携数据包。
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_LEGACY_DATA_ROOT = Path(r"D:\ZM\15GJQX\预测结果")

_CANDIDATE_ROOTS: list[tuple[str, Path]] = [
    ("环境变量 QIONGYU_DATA_ROOT", Path(os.environ["QIONGYU_DATA_ROOT"]))
    if os.environ.get("QIONGYU_DATA_ROOT")
    else ("", Path()),
    ("项目内便携数据包 data/", PROJECT_ROOT / "data"),
    ("本机完整产品目录", _LEGACY_DATA_ROOT),
]


def _resolve_data_root() -> tuple[Path, str]:
    """返回 (数据根目录, 来源说明)。首个存在且含产品子目录的候选生效。"""
    fallback: tuple[Path, str] | None = None
    for label, path in _CANDIDATE_ROOTS:
        if not label or not path:
            continue
        if path.is_dir():
            # 目录存在：优先选真正含产品数据的
            has_product = any((path / name).is_dir() for name in ("DF", "ens"))
            if has_product:
                return path, label
            if fallback is None:
                fallback = (path, f"{label}（暂未发现产品子目录）")
    if fallback:
        return fallback
    return PROJECT_ROOT / "data", "项目内便携数据包 data/（默认，目录尚不存在）"


DATA_ROOT, DATA_ROOT_SOURCE = _resolve_data_root()

# 产品目录：确定性主链 / 集合
PRODUCT_DIRS = {
    "DF": ("deterministic", "IFS 主链确定预报"),
    "ens": ("ensemble", "集合预报"),
}

# 中国区域裁剪范围（用于地图展示，留少量余量）
CHINA_LON_MIN, CHINA_LON_MAX = 70.0, 140.0
CHINA_LAT_MIN, CHINA_LAT_MAX = 12.0, 56.0

# 输出网格步长（0.25° 原始数据直接给前端过重，按此步长抽稀）
DEFAULT_STRIDE = 1  # 1 → 0.25°，2 → 0.5°，4 → 1.0°

# 要素字典：变量名 → (中文名, 单位, 类型, 所属文件)
VARIABLES: list[dict[str, Any]] = [
    {
        "key": "tp",
        "var": "TP",
        "name": "6小时累计降水",
        "shortName": "降水",
        "unit": "mm/6h",
        "kind": "precipitation",
        "file": "SURFACE",
        "palette": "precip",
        "description": "起报时刻后每6小时累计降水量，用于强降水落区与量级判断",
    },
    {
        "key": "t2m",
        "var": "T2M",
        "name": "2米气温",
        "shortName": "气温",
        "unit": "℃",
        "kind": "scalar",
        "file": "SURFACE",
        "palette": "temp",
        "description": "地面2米高度气温，用于冷空气、高温与雨雪相态判识",
    },
    {
        "key": "msl",
        "var": "MSL",
        "name": "海平面气压",
        "shortName": "气压",
        "unit": "hPa",
        "kind": "scalar",
        "file": "SURFACE",
        "palette": "pressure",
        "description": "海平面气压场，用于识别高压脊、低压槽与天气系统位置",
    },
    {
        "key": "q2m",
        "var": "Q2M",
        "name": "2米比湿",
        "shortName": "比湿",
        "unit": "g/kg",
        "kind": "scalar",
        "file": "SURFACE",
        "palette": "moisture",
        "description": "地面2米比湿，反映近地面水汽含量，是降水潜势的关键因子",
    },
    {
        "key": "wind10",
        "var": "U10/V10",
        "name": "10米风场",
        "shortName": "10米风",
        "unit": "m/s",
        "kind": "wind",
        "file": "SURFACE",
        "palette": "wind",
        "u": "U10",
        "v": "V10",
        "description": "地面10米全风速与风向，用于大风预报和低层辐合分析",
    },
    {
        "key": "z500",
        "var": "Z500",
        "name": "500hPa位势高度",
        "shortName": "500高度",
        "unit": "gpm",
        "kind": "scalar",
        "file": "PLEVELS",
        "palette": "height",
        "description": "中层环流形势，用于判断槽脊活动、副高位置与冷空气路径",
    },
    {
        "key": "t850",
        "var": "T850",
        "name": "850hPa温度",
        "shortName": "850温度",
        "unit": "℃",
        "kind": "scalar",
        "file": "PLEVELS",
        "palette": "temp",
        "description": "低层温度场，用于判断冷暖平流强度与降水相态",
    },
    {
        "key": "q700",
        "var": "Q700",
        "name": "700hPa比湿",
        "shortName": "700比湿",
        "unit": "g/kg",
        "kind": "scalar",
        "file": "PLEVELS",
        "palette": "moisture",
        "description": "中层水汽条件，与低层水汽输送配合决定降水效率",
    },
    {
        "key": "wind850",
        "var": "U850/V850",
        "name": "850hPa风场",
        "shortName": "850风",
        "unit": "m/s",
        "kind": "wind",
        "file": "PLEVELS",
        "palette": "wind",
        "u": "U850",
        "v": "V850",
        "description": "低空急流与低层风场，是水汽输送和强对流触发的重要指标",
    },
]

VARIABLE_MAP = {item["key"]: item for item in VARIABLES}

# 色标定义（低 → 高）
PALETTES: dict[str, list[str]] = {
    "precip": ["#cfe8ff", "#7fc4f5", "#38a6dc", "#3ed69a", "#b9db4a", "#f1d14f", "#f08b3e", "#e84b5f", "#a03050"],
    "temp": ["#2b3f95", "#3f6fc4", "#57a8de", "#8fd8e0", "#e8e6a0", "#f4c05a", "#ee8443", "#d4485c", "#8f2247"],
    "pressure": ["#2b3f95", "#3f6fc4", "#6fb3e0", "#cfe4ef", "#f0e6c0", "#f0b45a", "#e07a45", "#c0405a"],
    "moisture": ["#5b4326", "#9b8b52", "#a8c05c", "#3fd0a8", "#2f9fe0", "#4a6fd8", "#7b52c8"],
    "height": ["#4a2f7d", "#315fb0", "#29a1cf", "#59d0af", "#e4cf62", "#e08a4a", "#c94d61"],
    "wind": ["#1f3f8f", "#2f7fc8", "#4fc8dd", "#8fe8b8", "#e8e07a", "#f0a04f", "#e05555"],
}

# 降水分级（mm/6h）
PRECIP_LEVELS = [
    {"label": "小雨", "min": 0.1, "max": 3.0, "color": "#7fc4f5"},
    {"label": "中雨", "min": 3.0, "max": 10.0, "color": "#38a6dc"},
    {"label": "大雨", "min": 10.0, "max": 20.0, "color": "#3ed69a"},
    {"label": "暴雨", "min": 20.0, "max": 35.0, "color": "#f1d14f"},
    {"label": "大暴雨", "min": 35.0, "max": 60.0, "color": "#f08b3e"},
    {"label": "特大暴雨", "min": 60.0, "max": 1e9, "color": "#e84b5f"},
]

# 中国行政区（省级）参考中心，用于区域排行与下钻定位
REGION_ANCHORS = [
    {"name": "北京", "lon": 116.41, "lat": 39.90, "region": "华北"},
    {"name": "天津", "lon": 117.20, "lat": 39.13, "region": "华北"},
    {"name": "河北", "lon": 114.50, "lat": 38.05, "region": "华北"},
    {"name": "山西", "lon": 112.55, "lat": 37.87, "region": "华北"},
    {"name": "内蒙古", "lon": 111.75, "lat": 40.84, "region": "华北"},
    {"name": "辽宁", "lon": 123.43, "lat": 41.80, "region": "东北"},
    {"name": "吉林", "lon": 125.32, "lat": 43.90, "region": "东北"},
    {"name": "黑龙江", "lon": 126.64, "lat": 45.76, "region": "东北"},
    {"name": "上海", "lon": 121.47, "lat": 31.23, "region": "华东"},
    {"name": "江苏", "lon": 118.78, "lat": 32.06, "region": "华东"},
    {"name": "浙江", "lon": 120.15, "lat": 30.28, "region": "华东"},
    {"name": "安徽", "lon": 117.28, "lat": 31.86, "region": "华东"},
    {"name": "福建", "lon": 119.30, "lat": 26.08, "region": "华东"},
    {"name": "江西", "lon": 115.89, "lat": 28.68, "region": "华东"},
    {"name": "山东", "lon": 117.02, "lat": 36.67, "region": "华东"},
    {"name": "河南", "lon": 113.65, "lat": 34.76, "region": "华中"},
    {"name": "湖北", "lon": 114.30, "lat": 30.59, "region": "华中"},
    {"name": "湖南", "lon": 112.98, "lat": 28.19, "region": "华中"},
    {"name": "广东", "lon": 113.28, "lat": 23.13, "region": "华南"},
    {"name": "广西", "lon": 108.32, "lat": 22.82, "region": "华南"},
    {"name": "海南", "lon": 110.35, "lat": 20.02, "region": "华南"},
    {"name": "重庆", "lon": 106.55, "lat": 29.56, "region": "西南"},
    {"name": "四川", "lon": 104.07, "lat": 30.67, "region": "西南"},
    {"name": "贵州", "lon": 106.71, "lat": 26.57, "region": "西南"},
    {"name": "云南", "lon": 102.71, "lat": 25.05, "region": "西南"},
    {"name": "西藏", "lon": 91.13, "lat": 29.66, "region": "西南"},
    {"name": "陕西", "lon": 108.95, "lat": 34.27, "region": "西北"},
    {"name": "甘肃", "lon": 103.82, "lat": 36.06, "region": "西北"},
    {"name": "青海", "lon": 101.78, "lat": 36.62, "region": "西北"},
    {"name": "宁夏", "lon": 106.27, "lat": 38.47, "region": "西北"},
    {"name": "新疆", "lon": 87.62, "lat": 43.79, "region": "西北"},
    {"name": "台湾", "lon": 121.51, "lat": 25.04, "region": "华东"},
    {"name": "香港", "lon": 114.17, "lat": 22.32, "region": "华南"},
    {"name": "澳门", "lon": 113.55, "lat": 22.20, "region": "华南"},
]

BIG_REGIONS = ["华北", "东北", "华东", "华中", "华南", "西南", "西北"]


# ---------------------------------------------------------------------------
# NetCDF 读取（规避中文路径）
# ---------------------------------------------------------------------------

def _open_dataset(path: Path):
    """以内存字节流方式打开 NetCDF/HDF5，规避 Windows 中文路径问题。"""
    import xarray as xr

    with open(os.fspath(path), "rb") as handle:
        raw = handle.read()
    return xr.open_dataset(io.BytesIO(raw), engine="h5netcdf")


def read_variable(path: Path, var: str) -> np.ndarray:
    """读取指定变量，返回去掉 time/dtime 维度的 2D 场。"""
    ds = _open_dataset(path)
    try:
        data = ds[var]
        # 按需压掉 length-1 维度
        if "member" in data.dims:
            data = data.isel(member=0)
        for dim in ("time", "dtime"):
            if dim in data.dims:
                data = data.isel({dim: 0})
        return np.asarray(data.values, dtype=np.float32)
    finally:
        ds.close()


def read_coords(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """读取经纬度坐标。"""
    ds = _open_dataset(path)
    try:
        return np.asarray(ds["lon"].values), np.asarray(ds["lat"].values)
    finally:
        ds.close()


# ---------------------------------------------------------------------------
# 产品扫描与索引
# ---------------------------------------------------------------------------

_FILE_RE = re.compile(
    r"^(?P<prefix>.+?_(?P<kind>PLEVELS|SURFACE))(?:_.+?)?_(?P<lead>\d{3})\.nc$",
    re.IGNORECASE,
)
# 从文件名前缀中提取起报时次，如 AIMB_V3.3_GLB_SURFACE_OP25_6HOR_FCST_2026092800
_CYCLE_RE = re.compile(r".*?(?P<cycle>\d{10})")


class ProductIndex:
    """某个起报时次的完整文件清单。"""

    def __init__(self, root: Path, day: str, product: str):
        self.root = root
        self.day = day  # YYYYMMDD
        self.product = product  # DF / ens
        self.files: dict[tuple[str, int], Path] = {}
        self.leads: list[int] = []
        self.prefix = ""
        self.cycle = f"{day}00"  # 缺省按 00 UTC 起报，扫描时以文件名为准
        self.init_hour = 0
        self.product_name = ""
        self.product_version = ""

    def path_for(self, kind: str, lead: int) -> Path | None:
        return self.files.get((kind.upper(), int(lead)))

    def file_count(self) -> int:
        return len(self.files)

    def kinds(self) -> list[str]:
        return sorted({kind for kind, _ in self.files})


def scan_product_dir(root: Path, day: str, product: str) -> ProductIndex | None:
    """扫描单个产品的起报日期目录，返回文件索引。"""
    directory = root / product / day
    if not directory.is_dir():
        return None

    index = ProductIndex(root, day, product)
    for entry in directory.iterdir():
        if not entry.name.lower().endswith(".nc"):
            continue
        match = _FILE_RE.match(entry.name)
        if not match:
            continue
        kind = match.group("kind").upper()
        lead = int(match.group("lead"))
        index.files[(kind, lead)] = entry
        if not index.prefix:
            index.prefix = match.group("prefix")
            cycle_match = _CYCLE_RE.match(index.prefix)
            if cycle_match:
                index.cycle = cycle_match.group("cycle")
                index.init_hour = int(index.cycle[8:10])

    if not index.files:
        return None
    index.leads = sorted({lead for _, lead in index.files})

    # 解析产品代号与版本，如 AIMB_V3.3_GLB_SURFACE_...
    parts = index.prefix.split("_")
    if len(parts) >= 2:
        index.product_name = parts[0]
        index.product_version = parts[1]
    return index


def list_available_cycles(root: Path | None = None) -> dict[str, list[str]]:
    """列出各产品可用的起报时次（按日期倒序）。"""
    root = root or DATA_ROOT
    result: dict[str, list[str]] = {}
    for product in PRODUCT_DIRS:
        directory = root / product
        cycles: list[str] = []
        if directory.is_dir():
            for day_dir in directory.iterdir():
                if day_dir.is_dir() and re.fullmatch(r"\d{8}", day_dir.name):
                    cycles.append(day_dir.name)
        result[product] = sorted(set(cycles), reverse=True)
    return result


def _to_cycle(day: str) -> str:
    """日期目录 → 默认起报时次。AIM-FDP 流水线每日起报为 00 UTC。"""
    return f"{day}00"


def resolve_latest(root: Path | None = None, use_active: bool = True) -> tuple[ProductIndex | None, ProductIndex | None]:
    """找出最新的确定性产品与集合产品索引。"""
    root = root or DATA_ROOT
    available = list_available_cycles(root)
    det = ens = None

    for day in available.get("DF", []):
        candidate = scan_product_dir(root, day, "DF")
        if candidate and candidate.file_count() >= 4:
            det = candidate
            break

    for day in available.get("ens", []):
        candidate = scan_product_dir(root, day, "ens")
        if candidate and candidate.file_count() >= 4:
            ens = candidate
            break

    if use_active and root == DATA_ROOT:
        from app import dataset_manager as dm
        det = dm.active_index("DF", det)
        ens = dm.active_index("ens", ens)
        if ens and (det is None or ens.cycle != det.cycle):
            ens = None
    return det, ens


def resolve_cycle(day: str, root: Path | None = None,
                  product: str = "DF") -> ProductIndex | None:
    """按日期解析指定产品的起报索引。"""
    root = root or DATA_ROOT
    return scan_product_dir(root, day, product)


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

class _TTLCache:
    def __init__(self, ttl_seconds: float = 900.0, max_items: int = 256):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            stamp, value = item
            if time.time() - stamp > self.ttl:
                self._store.pop(key, None)
                return None
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self.max_items:
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                self._store.pop(oldest, None)
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


FIELD_CACHE = _TTLCache(ttl_seconds=1800.0, max_items=512)
POINT_CACHE = _TTLCache(ttl_seconds=900.0, max_items=256)
INDEX_CACHE = _TTLCache(ttl_seconds=120.0, max_items=16)


# ---------------------------------------------------------------------------
# 场数据读取与抽稀
# ---------------------------------------------------------------------------

def _china_slice(lon: np.ndarray, lat: np.ndarray, stride: int = DEFAULT_STRIDE):
    """返回中国区域的行列切片索引与对应坐标。"""
    lon_mask = (lon >= CHINA_LON_MIN) & (lon <= CHINA_LON_MAX)
    lat_mask = (lat >= CHINA_LAT_MIN) & (lat <= CHINA_LAT_MAX)
    rows = np.flatnonzero(lat_mask)[::stride]
    cols = np.flatnonzero(lon_mask)[::stride]
    return rows, cols, lon[cols], lat[rows]


def normalize_display_units(values: np.ndarray, var: str, units: str) -> np.ndarray:
    """按文件元数据换算为显示单位，已换算产品不会重复转换。"""
    unit = str(units).lower().replace(" ", "")
    if var == "MSL":
        if unit in ("pa", "pascal", "pascals"):
            return values / 100.0
        if unit in ("hpa", "mb", "mbar"):
            return values
        raise ValueError(f"MSL 单位无法识别：{units!r}")
    if var in ("Q2M", "Q700"):
        if unit in ("g/g", "kg/kg", "kgkg-1", "kgkg^-1", "1"):
            return values * 1000.0
        if unit in ("g/kg", "gkg-1", "gkg^-1"):
            return values
        raise ValueError(f"{var} 单位无法识别：{units!r}")
    return values


def read_china_field(path: Path, var: str, stride: int = DEFAULT_STRIDE):
    """读取变量在中国区域的抽稀场，返回 (values, lons, lats)。"""
    ds = _open_dataset(path)
    try:
        data = ds[var]
        if "member" in data.dims:
            data = data.isel(member=0)
        for dim in ("time", "dtime"):
            if dim in data.dims:
                data = data.isel({dim: 0})
        values = normalize_display_units(np.asarray(data.values, dtype=np.float32), var, data.attrs.get("units", ""))
        lon = np.asarray(ds["lon"].values)
        lat = np.asarray(ds["lat"].values)
    finally:
        ds.close()

    # 经度可能为 0..360，转换为 -180..180 便于中国区域切片
    if lon.max() > 180:
        shift = lon > 180
        lon = np.where(shift, lon - 360.0, lon)
        order = np.argsort(lon)
        lon = lon[order]
        values = values[:, order]

    rows, cols, out_lon, out_lat = _china_slice(lon, lat, stride)
    return values[np.ix_(rows, cols)], out_lon, out_lat


def field_to_points(values: np.ndarray, lons: np.ndarray, lats: np.ndarray,
                    precision: int = 2) -> list[list[float]]:
    """场 → 稀疏点集 [lon, lat, value]，跳过全零值以压缩载荷。"""
    points: list[list[float]] = []
    for i, lat in enumerate(lats):
        row = values[i]
        for j, lon in enumerate(lons):
            value = float(row[j])
            if not math.isfinite(value):
                continue
            points.append([round(float(lon), precision), round(float(lat), precision),
                           round(value, precision)])
    return points


def field_statistics(values: np.ndarray) -> dict[str, Any]:
    """计算场的统计指标。"""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"maximum": 0.0, "minimum": 0.0, "average": 0.0,
                "gridCount": 0, "wetGridCount": 0, "heavyGridCount": 0}
    return {
        "maximum": round(float(finite.max()), 2),
        "minimum": round(float(finite.min()), 2),
        "average": round(float(finite.mean()), 2),
        "gridCount": int(finite.size),
        "wetGridCount": int((finite >= 0.1).sum()),
        "heavyGridCount": int((finite >= 20.0).sum()),
        "p95": round(float(np.percentile(finite, 95)), 2),
        "p99": round(float(np.percentile(finite, 99)), 2),
    }


# ---------------------------------------------------------------------------
# 时间轴
# ---------------------------------------------------------------------------

def cycle_to_datetime(cycle: str) -> datetime:
    """YYYYMMDDHH → 带 +08:00 的 datetime（起报时刻已换算为北京时）。"""
    day = cycle[:8]
    hour = int(cycle[8:10]) if len(cycle) >= 10 else 0
    dt = datetime(int(day[:4]), int(day[4:6]), int(day[6:8]), hour, tzinfo=timezone.utc)
    return dt.astimezone(UTC8)


def build_timeline(cycle: str, leads: list[int]) -> list[dict[str, Any]]:
    """构建 0—360h 时间轴（含 +000h 起报时刻）。"""
    base = cycle_to_datetime(cycle)
    rows = [{
        "index": 0,
        "leadHour": 0,
        "validTime": base.isoformat(),
        "label": "+000h",
        "day": 0,
        "phase": "analysis",
        "phaseLabel": "起报时刻",
    }]
    for i, lead in enumerate(leads, start=1):
        valid = base + timedelta(hours=lead)
        rows.append({
            "index": i,
            "leadHour": int(lead),
            "validTime": valid.isoformat(),
            "label": f"+{lead:03d}h",
            "day": int(math.ceil(lead / 24)),
            "phase": "forecast",
            "phaseLabel": f"第{int(math.ceil(lead / 24))}天",
        })
    return rows


# ---------------------------------------------------------------------------
# 区域统计（排行 / 下钻）
# ---------------------------------------------------------------------------

def region_ranking(values: np.ndarray, lons: np.ndarray, lats: np.ndarray,
                   radius_deg: float = 1.6, top: int = 12) -> list[dict[str, Any]]:
    """按省级中心取邻域最大值，生成区域排行。"""
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    rows: list[dict[str, Any]] = []
    for anchor in REGION_ANCHORS:
        distance = (lon_grid - anchor["lon"]) ** 2 + (lat_grid - anchor["lat"]) ** 2
        mask = distance <= radius_deg ** 2
        if not mask.any():
            continue
        window = values[mask]
        window = window[np.isfinite(window)]
        if window.size == 0:
            continue
        rows.append({
            "name": anchor["name"],
            "region": anchor["region"],
            "lon": anchor["lon"],
            "lat": anchor["lat"],
            "value": round(float(window.max()), 2),
            "mean": round(float(window.mean()), 2),
        })
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows[:top]


def big_region_summary(values: np.ndarray, lons: np.ndarray, lats: np.ndarray) -> list[dict[str, Any]]:
    """七大区域聚合统计。"""
    members = {name: [] for name in BIG_REGIONS}
    for anchor in REGION_ANCHORS:
        members.setdefault(anchor["region"], []).append(anchor)

    lon_grid, lat_grid = np.meshgrid(lons, lats)
    rows: list[dict[str, Any]] = []
    for name in BIG_REGIONS:
        anchors = members.get(name) or []
        if not anchors:
            continue
        mask = np.zeros(values.shape, dtype=bool)
        for anchor in anchors:
            mask |= ((lon_grid - anchor["lon"]) ** 2 + (lat_grid - anchor["lat"]) ** 2) <= 2.2 ** 2
        window = values[mask]
        window = window[np.isfinite(window)]
        if window.size == 0:
            continue
        rows.append({
            "name": name,
            "maximum": round(float(window.max()), 2),
            "average": round(float(window.mean()), 2),
            "wetRatio": round(float((window >= 0.1).mean()), 4),
        })
    rows.sort(key=lambda item: item["maximum"], reverse=True)
    return rows


def classify_precip(value: float) -> str:
    """按降水强度返回等级名称。"""
    for level in PRECIP_LEVELS:
        if level["min"] <= value < level["max"]:
            return level["label"]
    return "无降水"
