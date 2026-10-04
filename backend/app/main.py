"""穹宇气象大模型演示系统 API —— 10 大功能模块统一数据服务。

模块索引
--------
1. 全国态势总览      GET /api/module/overview
2. 多级下钻联动      GET /api/module/drilldown
3. 时间轴播放        GET /api/module/timeline
4. 多要素切换        GET /api/module/variable   ·   GET /api/module/variables
5. 单点预报详情      GET /api/module/point
6. 预报检验看板      GET /api/module/verification
7. 多模式对比        GET /api/module/comparison
8. 集合与概率预报    GET /api/module/ensemble
9. 预警与风险提示    GET /api/module/risk
10. 系统与任务管理   GET /api/module/system   ·   GET /api/module/lineage · GET /api/module/quality
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import qiongyu_data as qd
from app import qiongyu_service as svc
from app.realtime import MONITOR


@asynccontextmanager
async def lifespan(_: FastAPI):
    MONITOR.scan(force=True)
    MONITOR.start()
    yield
    MONITOR.stop()


app = FastAPI(
    title="穹宇气象大模型演示系统 API",
    version="2.0.0",
    description="0—15天逐6小时降水预报演示数据服务（真实 AIM-FDP 竞赛产品）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ok(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


def guard(fn, *args, **kwargs):
    """统一异常转译，保证前端总能拿到可读的错误信息。"""
    try:
        return ok(fn(*args, **kwargs))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"数据文件缺失：{exc}") from exc


# ---------------------------------------------------------------------------
# 健康检查与实时状态
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return ok({
        "status": "ok",
        "dataRoot": str(qd.DATA_ROOT),
        "dataRootExists": qd.DATA_ROOT.is_dir(),
        "dataRootSource": qd.DATA_ROOT_SOURCE,
        "cacheFields": qd.FIELD_CACHE.size(),
        "monitor": MONITOR.status()["running"],
    })


@app.get("/api/realtime/status")
def realtime_status():
    """实时数据状态：监控线程、扫描节奏、产品快照与更新事件。

    前端轮询此接口，发现 revision 变化即自动刷新全部模块。
    """
    return ok(MONITOR.status())


@app.post("/api/realtime/scan")
def realtime_scan():
    """手动触发一次数据目录扫描。"""
    return ok(MONITOR.scan(force=True))


# ---------------------------------------------------------------------------
# 模块 10：系统与任务管理
# ---------------------------------------------------------------------------

@app.get("/api/module/system")
def module_system():
    return guard(svc.system_info)


@app.get("/api/module/lineage")
def module_lineage():
    return guard(svc.data_lineage)


@app.get("/api/module/quality")
def module_quality():
    return guard(svc.quality_report)


# ---------------------------------------------------------------------------
# 模块 1：全国态势总览
# ---------------------------------------------------------------------------

@app.get("/api/module/overview")
def module_overview(
    lead_hour: int = Query(24, ge=0, le=360),
    accumulation: str = Query("24h", pattern="^(6h|24h|total)$"),
    stride: int = Query(qd.DEFAULT_STRIDE, ge=1, le=6),
):
    return guard(svc.overview, lead_hour, accumulation, stride)


# ---------------------------------------------------------------------------
# 模块 2：多级下钻联动
# ---------------------------------------------------------------------------

@app.get("/api/module/drilldown")
def module_drilldown(
    province: str = Query(..., min_length=1),
    lead_hour: int = Query(24, ge=0, le=360),
    stride: int = Query(1, ge=1, le=4),
):
    return guard(svc.drilldown, province, lead_hour, stride)


@app.get("/api/module/provinces")
def module_provinces():
    return ok([
        {"name": a["name"], "region": a["region"], "lon": a["lon"], "lat": a["lat"]}
        for a in qd.REGION_ANCHORS
    ])


# ---------------------------------------------------------------------------
# 模块 3：时间轴播放
# ---------------------------------------------------------------------------

@app.get("/api/module/timeline")
def module_timeline():
    return guard(svc.timeline)


@app.get("/api/module/cycles")
def module_cycles():
    return ok(qd.list_available_cycles())


# ---------------------------------------------------------------------------
# 模块 4：多要素切换
# ---------------------------------------------------------------------------

@app.get("/api/module/variables")
def module_variables():
    return guard(svc.variables)


@app.get("/api/module/variable")
def module_variable(
    key: str = Query("tp"),
    lead_hour: int = Query(24, ge=0, le=360),
    stride: int = Query(qd.DEFAULT_STRIDE, ge=1, le=6),
):
    return guard(svc.variable_field, key, lead_hour, stride)


# ---------------------------------------------------------------------------
# 模块 5：单点预报详情
# ---------------------------------------------------------------------------

@app.get("/api/module/point")
def module_point(
    lon: float = Query(..., ge=70, le=140),
    lat: float = Query(..., ge=12, le=56),
    variable: str = Query("tp"),
):
    return guard(svc.point_forecast, lon, lat, variable)


# ---------------------------------------------------------------------------
# 模块 6：预报检验看板
# ---------------------------------------------------------------------------

@app.get("/api/module/verification")
def module_verification(lead_hour: int = Query(24, ge=0, le=360)):
    return guard(svc.verification, lead_hour)


# ---------------------------------------------------------------------------
# 模块 7：多模式对比
# ---------------------------------------------------------------------------

@app.get("/api/module/comparison")
def module_comparison(
    lead_hour: int = Query(24, ge=0, le=360),
    stride: int = Query(2, ge=1, le=6),
):
    return guard(svc.mode_comparison, lead_hour, stride)


# ---------------------------------------------------------------------------
# 模块 8：集合与概率预报
# ---------------------------------------------------------------------------

@app.get("/api/module/ensemble")
def module_ensemble(
    lead_hour: int = Query(24, ge=0, le=360),
    threshold: float = Query(10.0, ge=0.1, le=100.0),
    stride: int = Query(2, ge=1, le=6),
):
    return guard(svc.ensemble_probability, lead_hour, threshold, stride)


# ---------------------------------------------------------------------------
# 模块 9：预警与风险提示
# ---------------------------------------------------------------------------

@app.get("/api/module/risk")
def module_risk(stride: int = Query(2, ge=1, le=6)):
    return guard(svc.risk_warnings, stride)
