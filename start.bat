@echo off
setlocal EnableDelayedExpansion
title 穹宇气象演示系统

set "ROOT=%~dp0"
set "PY=%ROOT%backend\.venv\Scripts\python.exe"

echo ============================================================
echo   穹宇气象大模型演示系统  -  0-15 天降水预报
echo ============================================================
echo.

REM ---------- 环境自检 ----------
if not exist "%PY%" (
    echo   [失败] 未找到后端运行环境。
    echo.
    echo   请先双击运行 install.bat 完成环境安装。
    echo.
    pause
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules\vite" (
    echo   [失败] 未找到前端依赖。
    echo.
    echo   请先双击运行 install.bat 完成环境安装。
    echo.
    pause
    exit /b 1
)

REM ---------- 端口占用检查 ----------
netstat -ano | findstr ":8001 " | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo   [警告] 提示：端口 8001 已被占用，可能演示系统已在运行。
    echo     如需重启，请先运行 stop.bat 停止旧服务。
    echo.
)

REM ---------- 启动后端 ----------
echo   [1/3] 正在启动后端服务（端口 8001）...
start "穹宇-后端服务" /min cmd /c "cd /d "%ROOT%backend" && "%PY%" run.py"

REM 等待后端就绪（最多 30 秒）
set "BACKEND_UP=0"
for /l %%i in (1,1,30) do (
    if "!BACKEND_UP!"=="0" (
        >nul 2>nul (echo. | powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8001/api/health;exit 0}catch{exit 1}")
        if not errorlevel 1 (
            set "BACKEND_UP=1"
        ) else (
            ping -n 2 127.0.0.1 >nul
        )
    )
)

if "!BACKEND_UP!"=="1" (
    echo         [OK] 后端已就绪（http://127.0.0.1:8001）
) else (
    echo         [警告] 后端启动较慢或失败，请查看「穹宇-后端服务」窗口中的提示。
    echo           常见原因：数据目录缺失、依赖未装完整。
)

REM ---------- 启动前端 ----------
echo   [2/3] 正在启动前端服务（端口 5173）...
start "穹宇-前端服务" /min cmd /c "cd /d "%ROOT%frontend" && node node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173"

REM 等待前端就绪
set "FRONT_UP=0"
for /l %%i in (1,1,25) do (
    if "!FRONT_UP!"=="0" (
        >nul 2>nul (echo. | powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:5173;exit 0}catch{exit 1}")
        if not errorlevel 1 (
            set "FRONT_UP=1"
        ) else (
            ping -n 2 127.0.0.1 >nul
        )
    )
)

echo   [3/3] 正在打开浏览器 ...
if "!FRONT_UP!"=="1" (
    start "" http://127.0.0.1:5173
    echo         [OK] 前端已就绪
) else (
    echo         [警告] 前端启动较慢，请稍后手动在浏览器打开： http://127.0.0.1:5173
    start "" http://127.0.0.1:5173
)

echo.
echo ============================================================
echo   [OK] 演示系统已启动
echo.
echo     访问地址： http://127.0.0.1:5173
echo     接口文档： http://127.0.0.1:8001/docs
echo.
echo   关闭服务：双击 stop.bat
echo   本窗口可最小化，请勿直接关闭（关闭不影响后台服务）。
echo ============================================================
echo.
ping -n 7 127.0.0.1 >nul
endlocal
