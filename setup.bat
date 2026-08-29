@echo off
chcp 65001 >nul
title 学习 Agent - 环境初始化

echo ============================================================
echo   学习 Agent - 首次环境初始化
echo   (需要联网下载依赖，预计 5-15 分钟)
echo ============================================================
echo.

REM 检查 uv
where uv >nul 2>&1
if errorlevel 1 (
    echo [安装] 未检测到 uv，正在安装 uv 包管理器...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [错误] uv 安装失败，请手动安装: https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
    refreshenv >nul 2>&1
)

echo.
echo [1/3] 创建 Kotaemon Python 虚拟环境并安装依赖 (这一步最久)...
cd /d "%~dp0kotaemon"
uv sync --python 3.11
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/3] 安装 FSRS 间隔重复算法库...
set VIRTUAL_ENV=%cd%\.venv
uv pip install fsrs pywebview
if errorlevel 1 (
    echo [警告] pywebview 安装失败，将降级为浏览器模式
    set VIRTUAL_ENV=%cd%\.venv
    uv pip install fsrs
)

echo.
echo [3/3] 环境初始化完成！
echo.
echo 下一步: 双击 start.bat 启动程序
echo.
pause
