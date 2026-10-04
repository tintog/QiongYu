@echo off
setlocal EnableDelayedExpansion
title 穹宇气象演示系统 - 环境安装

echo ============================================================
echo   穹宇气象大模型演示系统  -  环境安装向导
echo ============================================================
echo.
echo   本脚本会自动检测 Python / Node.js，并安装项目依赖。
echo   首次安装大约需要 3-10 分钟（取决于网速）。
echo.
echo ------------------------------------------------------------

set "ROOT=%~dp0"
set "PY_OK=0"
set "NODE_OK=0"

REM ============================ 1. 检测 Python ============================
echo.
echo [1/3] 检测 Python ...
where python >nul 2>nul
if errorlevel 1 (
    echo       [缺失] 未检测到 python 命令。
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
    echo       [已安装] Python !PYVER!
    set "PY_OK=1"
)

if "!PY_OK!"=="0" (
    echo.
    echo   [警告] 需要先安装 Python 3.10 或更高版本。
    echo     下载地址： https://www.python.org/downloads/
    echo     安装时请务必勾选 "Add python.exe to PATH"。
    echo.
    echo     若已安装但本窗口检测不到，请关闭本窗口后重新双击运行。
    echo.
    pause
    exit /b 1
)

REM ============================ 2. 检测 Node.js ============================
echo.
echo [2/3] 检测 Node.js ...
where node >nul 2>nul
if errorlevel 1 (
    echo       [缺失] 未检测到 node 命令。
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do set "NODEVER=%%v"
    echo       [已安装] Node.js !NODEVER!
    set "NODE_OK=1"
)

if "!NODE_OK!"=="0" (
    echo.
    echo   [警告] 需要先安装 Node.js 18 或更高版本。
    echo     下载地址： https://nodejs.org/zh-cn  （选 LTS 长期支持版）
    echo     安装时一路默认下一步即可。
    echo.
    pause
    exit /b 1
)

REM ============================ 3. 安装依赖 ============================
echo.
echo [3/3] 安装项目依赖 ...
echo.

REM ---- 后端：创建虚拟环境并安装 Python 包 ----
if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
    echo   [后端] 正在创建 Python 虚拟环境 ...
    python -m venv "%ROOT%backend\.venv"
    if errorlevel 1 (
        echo   [失败] 虚拟环境创建失败。
        pause
        exit /b 1
    )
    echo   [后端] 虚拟环境创建完成。
) else (
    echo   [后端] 已存在虚拟环境，跳过创建。
)

echo   [后端] 正在安装 Python 依赖（首次较慢）...
"%ROOT%backend\.venv\Scripts\python.exe" -m pip install --upgrade pip -q

REM 依次尝试：阿里云 -> 清华 -> 官方源（任一成功即通过）
set "PIP_OK=0"
"%ROOT%backend\.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt" -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com
if not errorlevel 1 set "PIP_OK=1"

if "!PIP_OK!"=="0" (
    echo   [后端] 阿里云源失败，改用清华源重试 ...
    "%ROOT%backend\.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
    if not errorlevel 1 set "PIP_OK=1"
)

if "!PIP_OK!"=="0" (
    echo   [后端] 国内镜像均失败，改用官方源重试 ...
    "%ROOT%backend\.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt"
    if not errorlevel 1 set "PIP_OK=1"
)

if "!PIP_OK!"=="0" (
    echo   [失败] Python 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)
echo   [后端] Python 依赖安装完成。

REM ---- 前端：安装 npm 包 ----
if exist "%ROOT%frontend\node_modules\vite" (
    echo   [前端] node_modules 已存在，跳过安装。
) else (
    echo   [前端] 正在安装前端依赖（首次较慢）...
    pushd "%ROOT%frontend"
    call npm install --registry=https://registry.npmmirror.com
    if errorlevel 1 (
        echo   [前端] 镜像源安装失败，改用官方源重试 ...
        call npm install
        if errorlevel 1 (
            popd
            echo   [失败] 前端依赖安装失败，请检查网络后重试。
            pause
            exit /b 1
        )
    )
    popd
    echo   [前端] 前端依赖安装完成。
)

echo.
echo ============================================================
echo   [OK] 环境安装全部完成！
echo.
echo   请双击 start.bat 启动演示系统。
echo ============================================================
echo.
pause
