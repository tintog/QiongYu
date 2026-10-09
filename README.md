# 穹宇气象大模型演示系统

新增“3D大屏”入口：本地三维地球、真实气象场、集合概率、时间轴、区域与单点联动、巡航和全屏。详见[3D大屏使用说明](docs/3D大屏使用说明.md)。

一套读取已生成的逐6小时预报产品的可视化演示系统，支持数据导入、批次启用、降水落区、单点演变、集合概率、风险提示与系统状态。产品对比页面及其接口已移除。
系统不执行模型推理；无匹配参考数据时，检验看板不输出准确性评分或排名。

数据管理的操作、格式限制及测试说明，请阅读[数据导入说明](docs/数据导入与产品对比说明.md)。修改后请重启后端并刷新前端。

## 快速开始

> 详细步骤、常见问题与开发注意事项，请阅读 **《使用说明书.md》**。
> 未安装 Node.js？请看 **《先读我-安装Node.js.md》**。

**前置条件**（两项都必须装）：

```bat
python --version    REM 需要 3.10+，安装时务必勾选 "Add python.exe to PATH"
node -v             REM 需要 18+，安装后必须重启电脑
```

1. 安装环境（首次，双击执行一次）：

   ```bat
   install.bat
   ```

2. 启动系统（自动打开浏览器）：

   ```bat
   start.bat
   ```

3. 停止系统：

   ```bat
   stop.bat
   ```

访问地址：`http://127.0.0.1:5173`　｜　接口文档：`http://127.0.0.1:8001/docs`

## 环境要求

- Python 3.10 或更高版本（安装时**务必勾选** "Add python.exe to PATH"）
- Node.js 18 或更高版本（建议 LTS，安装后**必须重启电脑**）
- Chrome / Edge 最新版浏览器

## 项目结构

```
├── install.bat / start.bat / stop.bat   一键脚本
├── 使用说明书.md                        完整使用文档
├── backend/                            后端（FastAPI + xarray）
│   ├── run.py                          启动入口（端口 8001）
│   └── app/
│       ├── main.py                     API 路由
│       ├── qiongyu_data.py             数据读取（含数据根自动探测）
│       ├── qiongyu_service.py          业务组装
│       └── realtime.py                 实时扫描与版本号
├── frontend/                           前端（Vue 3 + Vite + ECharts 6）
│   └── src/
│       ├── App.vue                     主壳、导航、实时轮询
│       ├── api.js                      接口封装
│       ├── chartKit.js                 图表工具集
│       └── components/                 各功能模块组件
├── data/                               便携数据包（DF 确定性 + ens 集合）
├── tools/make_portable_data.py         数据裁剪脚本
└── docs/                               开发文档
```

## 数据说明

系统按以下优先级自动探测数据目录：

1. 环境变量 `QIONGYU_DATA_ROOT`
2. 项目内 `data/`（便携数据包默认位置）
3. `D:\ZM\15GJQX\预测结果`（本机完整产品目录）

项目自带一份 **抽样便携数据包**（约 522 MB）：已裁剪至中国区域（70—140°E，12—56°N），
保留全部预报时效与全要素，起报时次 20260928（另含 20260927 作为检验参考场）。
原始全量数据约 179 GB，压缩至 5% 后所有模块功能完整可用。

数据层级：`DF` 为确定性预报主链，`ens` 为集合预报（21 个成员）。
降水单位为 **6 小时累计降水量（mm/6h）**。

## 技术栈

- 后端：FastAPI 0.116 + Uvicorn + xarray + h5netcdf / netCDF4 + numpy
- 前端：Vue 3.5 + Vite 7 + ECharts 6
- 接口统一返回 `{ code, message, data }` 结构

## 二次开发

结构按"一个模块一个组件、一个功能一组接口"拆分，改造很直观：

- 调整页面展示逻辑 → 改 `frontend/src/components/` 下对应组件
- 调整数据结构 → 改 `backend/app/qiongyu_service.py`
- 接入新数据源 → 改 `backend/app/qiongyu_data.py` 或设置 `QIONGYU_DATA_ROOT`

开发时的关键注意事项（中文路径读 NetCDF、ECharts geo heatmap 陷阱、
图表容器初始化时序等）已整理在《使用说明书.md》第七节。
