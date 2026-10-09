"""穹宇气象大模型演示系统 API —— 10 大功能模块统一数据服务。

模块索引
--------
1. 全国态势总览      GET /api/module/overview
2. 多级下钻联动      GET /api/module/drilldown
3. 时间轴播放        GET /api/module/timeline
4. 多要素切换        GET /api/module/variable   ·   GET /api/module/variables
5. 单点预报详情      GET /api/module/point
6. 预报检验看板      GET /api/module/verification
8. 集合与概率预报    GET /api/module/ensemble
9. 预警与风险提示    GET /api/module/risk
10. 系统与任务管理   GET /api/module/system   ·   GET /api/module/lineage · GET /api/module/quality
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app import qiongyu_data as qd
from app import qiongyu_service as svc
from app.realtime import MONITOR
from app import dataset_manager as dm
from app import auth
from app.scene_assets import router as scene_assets_router

upload_locks: dict[str, asyncio.Lock] = {}


class ImportRequest(BaseModel):
    product: str
    name: str = Field(default='', max_length=120)
    source: str = Field(default='', max_length=240)
    model: str = Field(default="未声明", max_length=120)
    expectedFiles: int = Field(ge=1, le=240)
    staged: bool = False


class ImportMetadataRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=240)
    model: str = Field(default='未声明', max_length=120)
    dataProduct: str = Field(default='未识别产品', max_length=120)
    institution: str = Field(default='未核实', max_length=120)
    remarks: str = Field(default='', max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    allowDuplicate: bool = False



@asynccontextmanager
async def lifespan(_: FastAPI):
    with auth.db():
        pass
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

app.include_router(scene_assets_router)

LOCAL_ORIGINS = [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 5175, 8001, 18001)]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_local_mutations(request: Request, call_next):
    # CORS alone does not prevent simple cross-origin POST side effects.
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in LOCAL_ORIGINS:
        return JSONResponse({"detail": "仅允许本地演示页面修改数据"}, status_code=403)
    path = request.url.path
    if path.startswith('/api/') and path not in ('/api/auth/login','/api/health') and request.method != 'OPTIONS':
        user = auth.current(request.cookies.get('qiongyu_session'))
        if not user:
            return JSONResponse({'detail':'请先登录，或登录已过期'}, status_code=401)
        request.state.user = user
        admin_only = path.startswith('/api/admin/') or path in ('/api/module/lineage','/api/module/quality','/api/realtime/scan') or (path.startswith('/api/data/batches/') and request.method != 'GET')
        if admin_only and user['role'] != 'admin':
            return JSONResponse({'detail':'此操作需要管理员权限'},status_code=403)
        if path.startswith('/api/data/imports/'):
            job_id=path.split('/')[4]
            try:
                value=dm.job(job_id)
            except (ValueError,FileNotFoundError) as exc:
                return JSONResponse({'detail':str(exc)},status_code=400)
            if user['role']!='admin' and value.get('owner')!=user['username']:
                return JSONResponse({'detail':'只能访问自己的上传任务'},status_code=403)
            if request.method!='GET' and value.get('reviewStatus')=='pending' and user['role']!='admin':
                return JSONResponse({'detail':'已提交审核，暂不可修改'},status_code=403)
        response = await call_next(request)
        if request.method not in ('GET','HEAD') and response.status_code<400:
            auth.audit(user['username'],request.method,path)
        return response
    return await call_next(request)


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
    return ok({'status':'ok'})


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
def module_verification(lead_hour: int = Query(24, ge=0, le=360), variable: str = 'tp', reference_id: str | None = None, forecast_id: str | None = None):
    from app import observation_data
    return data_guard(observation_data.verification, variable, reference_id, forecast_id)


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


# Unified local data import. One request per file keeps browser progress and limits explicit.
def data_guard(fn, *args):
    try:
        return ok(fn(*args))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@app.get("/api/data/batches")
def data_batches(request: Request):
    result = data_guard(dm.catalog)
    if request.state.user['role'] != 'admin':
        result['data']['jobs']=[j for j in result['data']['jobs'] if j.get('owner')==request.state.user['username']]
    return result


@app.post("/api/data/imports")
def data_import(body: ImportRequest, request: Request):
    result=data_guard(dm.create_job, body.product, body.name, body.source, body.model, body.expectedFiles, body.staged)
    with dm.LOCK:
        value=dm.job(result['data']['id'])
        value['owner']=request.state.user['username']
        dm._save(dm.job_path(value['id'])/'manifest.json',value)
    return ok(value)


@app.get('/api/data/imports/{job_id}/preview')
def data_import_preview(job_id: str):
    return data_guard(dm.preview,job_id)


@app.post('/api/data/imports/{job_id}/metadata')
def data_import_metadata(job_id: str, body: ImportMetadataRequest):
    return data_guard(dm.update_metadata,job_id,body.model_dump())


@app.get('/api/data/reference-options')
def data_reference_options(forecast_id: str | None = None):
    from app import observation_data
    return data_guard(observation_data.reference_options,forecast_id)


@app.get("/api/data/imports/{job_id}")
def data_import_status(job_id: str):
    return data_guard(dm.job, job_id)


@app.post("/api/data/imports/{job_id}/files")
async def data_upload(job_id: str, request: Request, filename: str = Query(..., max_length=180)):
    try:
        directory = dm.job_path(job_id)
        filename = dm.safe_filename(filename, dm.job(job_id)['product'])
        # A bounded, single-file import channel; no ZIP extraction or client directory paths.
        async with upload_locks.setdefault(job_id, asyncio.Lock()):
            value = dm.job(job_id)
            if value["status"] != "uploading" or len(value["files"]) >= value["expectedFiles"]:
                raise ValueError("任务已结束或达到声明文件数量")
            length = request.headers.get("content-length")
            if length is not None and (int(length) <= 0 or int(length) > dm.MAX_FILE or int(length) + value["bytes"] > dm.MAX_TOTAL):
                raise ValueError("上传大小为空或超过单文件128MiB/单批2GiB限制")
            directory = directory / "files"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / filename
            temp = directory / (filename + ".part")
            if path.exists() or temp.exists():
                raise ValueError("同名文件已上传，不允许覆盖；请创建新任务重试")
            size = 0
            try:
                with temp.open("xb") as handle:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > dm.MAX_FILE or size + value["bytes"] > dm.MAX_TOTAL:
                            raise ValueError("超过单文件128MiB或单批2GiB限制")
                        handle.write(chunk)
                if size == 0:
                    raise ValueError("不能上传空文件")
                os.rename(temp, path)
            except BaseException:
                if temp.exists():
                    temp.unlink()
                raise
            result = await run_in_threadpool(dm.record_file, job_id, filename, size)
            return ok(result)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@app.post("/api/data/imports/{job_id}/finalize")
def data_finalize(job_id: str, request: Request):
    if request.state.user['role'] != 'admin':
        with dm.LOCK:
            value=dm.job(job_id)
            if value['status']!='uploading' or value.get('reviewStatus')=='pending':
                raise HTTPException(400,detail='当前任务不能重复提交审核')
            preview=dm.preview(job_id)
            if not preview.get('complete') or preview.get('errors') or not value.get('metadataConfirmed'):
                raise HTTPException(400,detail='请完成文件校验并确认元数据后提交')
            value.update(reviewStatus='pending',reviewMessage='')
            dm._save(dm.job_path(job_id)/'manifest.json',value)
        return ok(value)
    result = data_guard(dm.finalize, job_id)
    with dm.LOCK:
        value=dm.job(job_id)
        value.update(reviewStatus='approved' if value['status']=='ready' else 'failed',reviewer=request.state.user['username'])
        dm._save(dm.job_path(job_id)/'manifest.json',value)
    upload_locks.pop(job_id, None)
    return ok(value)


@app.post("/api/data/batches/{batch_id}/activate")
def data_activate(batch_id: str):
    result = data_guard(dm.activate, batch_id)
    MONITOR.scan(force=True)
    return result


@app.post("/api/data/batches/{batch_id}/remove")
def data_remove(batch_id: str):
    return data_guard(dm.remove, batch_id)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1,max_length=64)
    password: str = Field(min_length=1,max_length=128)
    role: str

@app.post('/api/auth/login')
def login(body: LoginRequest):
    try: token,user=auth.login(body.username,body.password,body.role)
    except ValueError as exc: raise HTTPException(401,detail=str(exc))
    response=JSONResponse(ok(user))
    response.set_cookie('qiongyu_session',token,httponly=True,samesite='strict',max_age=8*3600,secure=os.environ.get('QIONGYU_COOKIE_SECURE')=='1')
    return response

@app.get('/api/auth/me')
def me(request: Request):return ok(request.state.user)

@app.post('/api/auth/logout')
def logout(request: Request):
    auth.logout(request.cookies.get('qiongyu_session',''))
    response=JSONResponse(ok({}))
    response.delete_cookie('qiongyu_session')
    return response

class AccountRequest(BaseModel):
    username: str = Field(min_length=1,max_length=64)
    role: str = 'user'
    enabled: bool = True
    password: str | None = None

@app.get('/api/admin/users')
def users():return ok(auth.users())

@app.post('/api/admin/users')
def create_user(body: AccountRequest):
    try:return ok(auth.save_user(body.username,body.role,body.enabled,body.password,True))
    except ValueError as exc:raise HTTPException(400,detail=str(exc))

@app.post('/api/admin/users/update')
def update_user(body: AccountRequest):
    try:return ok(auth.save_user(body.username,body.role,body.enabled,body.password))
    except ValueError as exc:raise HTTPException(400,detail=str(exc))

@app.get('/api/admin/logs')
def audit_logs():return ok(auth.logs())

class ReviewRequest(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)

@app.post('/api/admin/imports/{job_id}/reject')
def reject_import(job_id: str, body: ReviewRequest, request: Request):
    with dm.LOCK:
        try:value=dm.job(job_id)
        except ValueError as exc:raise HTTPException(400,detail=str(exc))
        if value.get('reviewStatus')!='pending':raise HTTPException(400,detail='任务不是待审核状态')
        value.update(reviewStatus='returned',reviewMessage=body.reason,reviewer=request.state.user['username'])
        dm._save(dm.job_path(job_id)/'manifest.json',value)
    return ok(value)
