"""便携数据包抽取脚本

从完整产品目录中抽取单个起报时次的中国区域数据，用于随项目分发。

裁剪策略：
- 空间：全球 0.25° → 中国区域（70–140°E, 12–56°N），体积降至约 5%
- 变量：全要素保留（SURFACE 6 项 + PLEVELS 5 项）
- 时效：全时效保留（60 个）
- 压缩：zlib level 4，兼顾体积与读写速度

用法：
    python make_portable_data.py <源目录> <目标目录> <时次8位>
例：
    python make_portable_data.py D:/ZM/15GJQX/预测结果 ./data 20260928
"""

from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import xarray as xr

LAT_MIN, LAT_MAX = 12.0, 56.0
LON_MIN, LON_MAX = 70.0, 140.0


def open_ds(path: Path) -> xr.Dataset:
    """以字节流方式打开，规避 Windows 中文路径下 netCDF4 C 层的 ANSI 问题。"""
    with open(os.fspath(path), "rb") as handle:
        raw = handle.read()
    return xr.open_dataset(io.BytesIO(raw), engine="h5netcdf")


def subset(ds: xr.Dataset) -> xr.Dataset:
    """裁剪中国区域；兼容经度 0–360 与 -180–180 两种约定。"""
    lat = ds["lat"]
    lon = ds["lon"]
    lat_slice = slice(LAT_MIN, LAT_MAX) if float(lat[0]) < float(lat[-1]) else slice(LAT_MAX, LAT_MIN)

    lon_vals = lon.values
    if float(np.nanmax(lon_vals)) > 180.0:
        # 0–360 约定：中国区域落在 70–140，无需跨 0 度
        lon_slice = slice(LON_MIN, LON_MAX)
    else:
        lon_slice = slice(LON_MIN, LON_MAX)

    return ds.sel(lat=lat_slice, lon=lon_slice)


def process_file(src: Path, dst: Path) -> tuple[int, int]:
    """处理单个文件，返回 (原始字节, 新字节)。"""
    ds = open_ds(src)
    try:
        sub = subset(ds)
        encoding = {
            name: {"zlib": True, "complevel": 4, "shuffle": True}
            for name in sub.data_vars
            if sub[name].dtype.kind == "f"
        }
        dst.parent.mkdir(parents=True, exist_ok=True)
        sub.to_netcdf(dst, engine="h5netcdf", encoding=encoding)
    finally:
        ds.close()
    return src.stat().st_size, dst.stat().st_size


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    src_root = Path(sys.argv[1])
    dst_root = Path(sys.argv[2])
    cycle8 = sys.argv[3]

    total_src = total_dst = 0
    count = 0
    for product in ("DF", "ens"):
        src_dir = src_root / product / cycle8
        if not src_dir.is_dir():
            print(f"[跳过] 源目录不存在：{src_dir}")
            continue
        dst_dir = dst_root / product / cycle8
        files = sorted(src_dir.glob("*.nc"))
        print(f"[{product}] {len(files)} 个文件 → {dst_dir}")
        for i, src in enumerate(files, 1):
            a, b = process_file(src, dst_dir / src.name)
            total_src += a
            total_dst += b
            count += 1
            if i % 20 == 0 or i == len(files):
                print(f"  {i}/{len(files)}  已生成 {total_dst/1024/1024:.1f} MB")

    print(f"\n完成：{count} 个文件")
    print(f"原始 {total_src/1024/1024/1024:.2f} GB → 便携 {total_dst/1024/1024:.1f} MB"
          f"（压缩至 {total_dst/total_src*100:.1f}%）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
