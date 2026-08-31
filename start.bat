@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title LearnEverything - 浏览器开发模式
cd /d "%~dp0"

REM 优先用打包的 exe 同目录 python (如果存在便携版 python)
if exist "%~dp0python\python.exe" (
    echo 学习 Agent 便携版启动中...
    "%~dp0python\python.exe" "%~dp0launcher.py"
) else (
    echo 学习 Agent 浏览器开发模式启动中...
    echo 前端地址：http://127.0.0.1:3000，API 地址：http://127.0.0.1:8000。
    echo.
    if not exist "kotaemon\.venv\Scripts\python.exe" (
        echo [错误] 未找到 Kotaemon Python 环境。请先运行 setup.bat。
        set "EXIT_CODE=1"
        goto :finished
    )
    "%~dp0kotaemon\.venv\Scripts\python.exe" "%~dp0scripts\start_frontend_dev.py"
)

set "EXIT_CODE=%ERRORLEVEL%"
:finished
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
