@echo off
setlocal EnableDelayedExpansion
title 穹宇气象演示系统 - 停止服务

echo ============================================================
echo   穹宇气象大模型演示系统  -  停止服务
echo ============================================================
echo.

set "FOUND=0"

REM ---------- 停止后端（8001 端口） ----------
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    echo   停止后端进程 PID=%%p ...
    taskkill /f /pid %%p >nul 2>nul
    set "FOUND=1"
)

REM ---------- 停止前端（5173 端口） ----------
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo   停止前端进程 PID=%%p ...
    taskkill /f /pid %%p >nul 2>nul
    set "FOUND=1"
)

REM ---------- 关闭残留的标题窗口 ----------
taskkill /f /fi "WINDOWTITLE eq 穹宇-后端服务*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq 穹宇-前端服务*" >nul 2>nul

echo.
if "!FOUND!"=="1" (
    echo   [OK] 服务已停止。
) else (
    echo   未发现正在运行的服务（端口 8001 / 5173 均空闲）。
)
echo.
ping -n 4 127.0.0.1 >nul
endlocal
