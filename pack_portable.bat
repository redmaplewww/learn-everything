@echo off
chcp 65001 >nul
title 学习 Agent - 组装便携版

cd /d "%~dp0"
setlocal

echo ============================================================
echo   学习 Agent - 组装可分发的便携版
echo ============================================================
echo.

REM 1. 每次都重建启动器，确保便携版包含最新 launcher.py
cmd.exe /c build_exe.bat
if errorlevel 1 (
    echo [错误] 启动器打包失败
    endlocal
    pause
    exit /b 1
)

REM 2. 组装便携版目录
set PORTABLE=dist\LearnEverything-Portable
echo [1/5] 清理旧的便携版目录...
if exist "%PORTABLE%" rmdir /s /q "%PORTABLE%"

echo [2/5] 复制 exe 和运行时...
mkdir "%PORTABLE%"
mkdir "%PORTABLE%\kotaemon"
xcopy /E /I /Y "dist\LearnEverything\*" "%PORTABLE%\" >nul

echo [3/5] 复制学习 Agent 代码...
copy /Y custom_app.py "%PORTABLE%\" >nul
xcopy /E /I /Y api "%PORTABLE%\api" >nul
xcopy /E /I /Y learning_ext "%PORTABLE%\learning_ext" >nul
if exist "frontend\out" xcopy /E /I /Y frontend\out "%PORTABLE%\frontend\out" >nul
copy /Y README.md "%PORTABLE%\" >nul
if exist "kotaemon\.env" copy /Y "kotaemon\.env" "%PORTABLE%\kotaemon\.env" >nul

REM 复制 Kotaemon 必需的非虚拟环境文件
copy /Y "kotaemon\flowsettings.py" "%PORTABLE%\kotaemon\" >nul
copy /Y "kotaemon\app.py" "%PORTABLE%\kotaemon\" >nul
xcopy /E /I /Y "kotaemon\libs" "%PORTABLE%\kotaemon\libs" >nul
if exist "kotaemon\templates" xcopy /E /I /Y "kotaemon\templates" "%PORTABLE%\kotaemon\templates" >nul

echo [4/5] 创建独立运行时 (首次约 5-15 分钟)...
set "UV=uv"
where uv >nul 2>&1
if errorlevel 1 if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
where "%UV%" >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 uv，请先运行 setup.bat
    endlocal
    pause
    exit /b 1
)

pushd kotaemon
set "UV_PROJECT_ENVIRONMENT=..\dist\LearnEverything-Portable\kotaemon\.venv"
"%UV%" sync --frozen --no-editable --no-dev --python 3.11
if errorlevel 1 goto :runtime_failed
"%UV%" pip install --python "%UV_PROJECT_ENVIRONMENT%\Scripts\python.exe" fsrs pywebview
if errorlevel 1 goto :runtime_failed
popd

echo [5/5] 校验便携运行时...
if not exist "%PORTABLE%\LearnEverything.exe" goto :runtime_failed
if not exist "%PORTABLE%\kotaemon\.venv\Scripts\python.exe" goto :runtime_failed

echo.
echo ============================================================
echo   便携版组装完成！
echo   位置: %PORTABLE%
echo.
echo   分发方式:
echo     把整个 LearnEverything-Portable 文件夹打包成 zip 即可分发
echo     用户解压后双击 LearnEverything.exe 直接运行 (首次需配 LLM key)
echo ============================================================
echo.
echo 提示: 便携版体积较大 (因含完整 Python venv)。
echo       请妥善保管 kotaemon\.env，其中可能包含 API Key。
endlocal
pause
exit /b 0

:runtime_failed
popd
echo [错误] 便携运行时创建或校验失败
endlocal
pause
exit /b 1
