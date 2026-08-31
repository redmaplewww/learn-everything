@echo off
chcp 65001 >nul
title 学习 Agent - 打包 exe

cd /d "%~dp0"

echo ============================================================
echo   学习 Agent - 打包 launcher.exe
echo   (便携版核心，只含启动逻辑 + PyWebView)
echo ============================================================
echo.

set PYINSTALLER=kotaemon\.venv\Scripts\pyinstaller.exe

if not exist "%PYINSTALLER%" (
    echo [错误] 未找到 PyInstaller，请先运行 setup.bat
    exit /b 1
)

echo [1/2] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [2/3] 构建 Next.js 静态前端...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo [错误] Next.js 静态前端构建失败
    exit /b 1
)
popd

echo.
echo [3/3] PyInstaller 打包中 (约 1-3 分钟)...
"%PYINSTALLER%" ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "LearnEverything" ^
    --hidden-import "webview" ^
    --hidden-import "webview.platforms.edgechromium" ^
    --collect-submodules "webview" ^
    --add-data "%CD%\frontend\out;frontend\out" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    launcher.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请查看上方日志
    exit /b 1
)

echo.
echo ============================================================
echo   打包成功！
echo   产物: dist\LearnEverything\LearnEverything.exe
echo.
echo   便携版组装:
echo     1. 复制 dist\LearnEverything\ 下的所有文件到分发目录
echo     2. 把 api\、learning_ext\、frontend\out\、kotaemon\.venv\ 一并复制
echo     3. 双击 LearnEverything.exe 即可运行
echo ============================================================
exit /b 0
