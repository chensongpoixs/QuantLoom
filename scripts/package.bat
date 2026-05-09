@echo off
REM ============================================================
REM QuantLoom·量梭 — Windows 打包脚本
REM 生成可分发的安装包: quant_loom-{version}-win.zip
REM ============================================================
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM ---- 版本信息 ----
if "%QUANT_LOOM_VERSION%"=="" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "VER=%%I"
    set "VERSION=!VER:~0,8!"
) else (
    set "VERSION=%QUANT_LOOM_VERSION%"
)
set "PACKAGE_NAME=quant_loom-%VERSION%-win"
set "BUILD_DIR=%PROJECT_ROOT%\build\%PACKAGE_NAME%"
set "DIST_DIR=%PROJECT_ROOT%\dist"

echo ============================================
echo  QuantLoom·量梭 — Windows 打包工具
echo  Version: %VERSION%
echo ============================================
echo.

REM ---- 1. 清理旧构建 ----
echo [1/5] 清理旧构建...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
mkdir "%BUILD_DIR%"

REM ---- 2. 复制前端 dist ----
echo [2/5] 检查前端构建...
if exist "%PROJECT_ROOT%\frontend\dist\index.html" (
    echo   前端 dist 已存在
) else (
    echo   [警告] 前端 dist 不存在，请先构建:
    echo     cd frontend ^&^& npm run build
    echo   继续打包 (不含前端)...
)
if exist "%PROJECT_ROOT%\frontend\dist" (
    xcopy /e /i /q "%PROJECT_ROOT%\frontend\dist" "%BUILD_DIR%\frontend\dist" >nul 2>&1
)

REM ---- 3. 复制项目文件 ----
echo [3/5] 复制项目文件...

xcopy /e /i /q "%PROJECT_ROOT%\quant_loom" "%BUILD_DIR%\quant_loom" >nul 2>&1
xcopy /e /i /q "%PROJECT_ROOT%\config" "%BUILD_DIR%\config" >nul 2>&1
xcopy /e /i /q "%PROJECT_ROOT%\scripts" "%BUILD_DIR%\scripts" >nul 2>&1
if exist "%PROJECT_ROOT%\tests" xcopy /e /i /q "%PROJECT_ROOT%\tests" "%BUILD_DIR%\tests" >nul 2>&1

for %%f in (requirements.txt pyproject.toml .env.example) do (
    if exist "%PROJECT_ROOT%\%%f" copy /y "%PROJECT_ROOT%\%%f" "%BUILD_DIR%\" >nul 2>&1
)

REM ---- 4. 生成 Windows 启动脚本 ----
echo [4/5] 生成启动脚本...

REM --- install.bat ---
(
echo @echo off
echo REM QuantLoom·量梭 — 一键安装 ^(Windows^)
echo setlocal enabledelayedexpansion
echo cd /d "%%~dp0"
echo.
echo echo ============================================
echo echo  QuantLoom·量梭 安装向导
echo echo ============================================
echo echo.
echo.
echo REM 检查 Python
echo where python >nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo [错误] 未找到 Python，请先安装 Python 3.12+
echo     echo   https://www.python.org/downloads/
echo     echo   安装时请勾选 "Add Python to PATH"
echo     pause
echo     exit /b 1
echo ^)
echo.
echo for /f "tokens=2" %%%%V in ^('python --version 2^>^&1'^) do set "PYVER=%%%%V"
echo echo [OK] Python %%PYVER%%
echo.
echo REM 创建虚拟环境
echo echo.
echo echo [1/3] 创建虚拟环境...
echo python -m venv .venv
echo call .venv\Scripts\activate.bat
echo.
echo REM 安装依赖
echo echo [2/3] 安装 Python 依赖...
echo pip install --upgrade pip -q
echo pip install -r requirements.txt -q
echo.
echo REM 初始化配置
echo echo [3/3] 初始化配置...
echo if not exist .env ^(
echo     copy .env.example .env ^>nul
echo     echo   [OK] 已创建 .env，请编辑填入数据库、LLM、邮箱等配置
echo     echo   必填项:
echo     echo     - MYSQL_HOST / MYSQL_PASSWORD
echo     echo     - LLM 配置 ^(LLAMA_BASE_URL 或 OPENAI_API_KEY^)
echo     echo     - SMTP 配置 ^(如需邮件通知^)
echo     echo.
echo     echo   请用记事本编辑: notepad .env
echo ^) else ^(
echo     echo   [OK] .env 已存在，跳过
echo ^)
echo.
echo echo ============================================
echo echo  安装完成！
echo echo ============================================
echo echo.
echo echo 配置数据库 ^(首次^):
echo echo   .venv\Scripts\activate
echo echo   python scripts\init_db.py
echo echo.
echo echo 启动服务:
echo echo   start_api.bat          # API 服务 ^(端口 9090^)
echo echo   start_scanner.bat      # 手动扫描
echo echo.
echo pause
) > "%BUILD_DIR%\install.bat"

REM --- start_api.bat ---
(
echo @echo off
echo REM QuantLoom·量梭 — FastAPI 服务
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo echo === QuantLoom·量梭 API Server ===
echo if "%%1"=="" ^(set PORT=9090^) else ^(set PORT=%%1^)
echo echo Starting on http://0.0.0.0:%%PORT%%
echo uvicorn quant_loom.api.app:app --host 0.0.0.0 --port %%PORT%%
echo pause
) > "%BUILD_DIR%\start_api.bat"

REM --- start_worker.bat ---
(
echo @echo off
echo REM QuantLoom·量梭 — Celery Worker
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo echo === QuantLoom·量梭 Celery Worker ===
echo celery -A quant_loom.tasks.celery_app worker -l info --pool=threads --concurrency=2
echo pause
) > "%BUILD_DIR%\start_worker.bat"

REM --- start_beat.bat ---
(
echo @echo off
echo REM QuantLoom·量梭 — Celery Beat
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo echo === QuantLoom·量梭 Celery Beat ===
echo celery -A quant_loom.tasks.celery_app beat -l info --scheduler celery.beat:PersistentScheduler
echo pause
) > "%BUILD_DIR%\start_beat.bat"

REM --- start_scanner.bat ---
(
echo @echo off
echo REM QuantLoom·量梭 — 单次扫描
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo echo === QuantLoom·量梭 Scanner ===
echo python scripts\run_scanner.py %%*
echo pause
) > "%BUILD_DIR%\start_scanner.bat"

REM ---- 5. 打包 ZIP ----
echo [5/5] 打包 %PACKAGE_NAME%.zip ...

REM 使用 PowerShell 压缩 (更好的 UTF-8 支持)
powershell -NoProfile -Command ^
    "Add-Type -AssemblyName System.IO.Compression.FileSystem; \
     [System.IO.Compression.ZipFile]::CreateFromDirectory('%BUILD_DIR%', '%DIST_DIR%\%PACKAGE_NAME%.zip')"

REM 清理临时目录
rmdir /s /q "%BUILD_DIR%"

echo.
echo   [OK] 打包完成!
echo.
echo   Package: %DIST_DIR%\%PACKAGE_NAME%.zip

REM 文件大小
for %%A in ("%DIST_DIR%\%PACKAGE_NAME%.zip") do echo   Size: %%~zA bytes
echo.
endlocal
