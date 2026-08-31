@echo off
setlocal
chcp 65001 >nul
title 学习 Agent - 环境初始化

set "ROOT=%~dp0"
set "UV=uv"
set "VENV_PYTHON=%ROOT%kotaemon\.venv\Scripts\python.exe"

echo ============================================================
echo   学习 Agent - 首次环境初始化
echo   (需要联网下载依赖，预计 5-15 分钟)
echo ============================================================
echo.

REM 检查 uv；安装后优先使用用户目录中的可执行文件，避免 PATH 尚未刷新。
where uv >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo [安装] 未检测到 uv，正在安装 uv 包管理器...
        powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        if errorlevel 1 goto :uv_failed
        if exist "%USERPROFILE%\.local\bin\uv.exe" (
            set "UV=%USERPROFILE%\.local\bin\uv.exe"
        ) else (
            echo [错误] uv 安装完成但未找到可执行文件。
            goto :failed
        )
    )
)

echo.
echo [1/5] 创建 Kotaemon Python 虚拟环境并安装依赖 (这一步最久)...
pushd "%ROOT%kotaemon"
"%UV%" sync --python 3.11
if errorlevel 1 (
    popd
    echo [错误] Python 依赖安装失败
    goto :failed
)
popd

echo.
echo [2/5] 安装学习与桌面打包依赖...
"%UV%" pip install --python "%VENV_PYTHON%" fsrs pywebview pyinstaller
if errorlevel 1 (
    echo [错误] FSRS、PyWebView 或 PyInstaller 安装失败
    goto :failed
)

echo.
echo [3/5] 检查 Node.js 与 npm...
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js。请安装 Node.js 20+ 并确保 node 在 PATH 中。
    goto :failed
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm。请重新安装 Node.js 20+ 并确保 npm 在 PATH 中。
    goto :failed
)
set "NODE_MAJOR="
for /f %%V in ('node -p "process.versions.node.split('.')[0]" 2^>nul') do set "NODE_MAJOR=%%V"
if not defined NODE_MAJOR (
    echo [错误] 无法读取 Node.js 版本。
    goto :failed
)
if %NODE_MAJOR% LSS 20 (
    echo [错误] Node.js 版本过低，需要 20+，当前主版本为 %NODE_MAJOR%。
    goto :failed
)

echo.
echo [4/5] 安装 Next.js 前端依赖...
pushd "%ROOT%frontend"
call npm ci
if errorlevel 1 (
    popd
    echo [错误] 前端依赖安装失败
    goto :failed
)

echo.
echo [5/5] 执行前端 TypeScript 类型检查...
call npm run typecheck
if errorlevel 1 (
    popd
    echo [错误] 前端类型检查失败
    goto :failed
)
popd

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到 Python 虚拟环境: %VENV_PYTHON%
    goto :failed
)
if not exist "%ROOT%kotaemon\.venv\Scripts\pyinstaller.exe" (
    echo [错误] 未找到 PyInstaller 可执行文件。
    goto :failed
)
if not exist "%ROOT%frontend\node_modules\next\dist\bin\next" (
    echo [错误] 未找到 Next.js 可执行文件。
    goto :failed
)
"%VENV_PYTHON%" -c "import fsrs, webview"
if errorlevel 1 (
    echo [错误] Python 学习或桌面依赖校验失败
    goto :failed
)

echo.
echo ============================================================
echo   环境初始化完成！
echo   已准备 Python 后端、Next.js 前端和桌面打包依赖。
echo   未生成 frontend\out；静态构建由 build_exe.bat 负责。
echo ============================================================
echo.
echo 下一步: 编辑 kotaemon\.env 配置 LLM key，然后双击 start.bat
echo.
pause
endlocal
exit /b 0

:uv_failed
echo [错误] uv 安装失败，请手动安装: https://docs.astral.sh/uv/

:failed
pause
endlocal
exit /b 1
