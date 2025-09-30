@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: CI/otomasyon modunu algıla
set "IS_CI=0"
if /I "%~1"=="--ci" set "IS_CI=1"
if /I "%CI%"=="true" set "IS_CI=1"
if /I "%GITHUB_ACTIONS%"=="true" set "IS_CI=1"
if /I "%SETUP_ALL_NONINTERACTIVE%"=="1" set "IS_CI=1"

:: ==========================================================
:: setup_all.cmd — Windows tek dosya kurulum/çalıştırma
:: ==========================================================

:: 0) Konum ve venv yolları
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYVENV=%VENV_DIR%\Scripts\python.exe"
set "ACTIVATE=%VENV_DIR%\Scripts\activate"

echo(
echo [1/9] Python kontrol ediliyor...
set "PY_SYS="
where python >nul 2>nul && set "PY_SYS=python"
if "%PY_SYS%"=="" (
  where py >nul 2>nul && set "PY_SYS=py -3"
)
if "%PY_SYS%"=="" (
  echo( [HATA] Python bulunamadı. Lütfen Python 3.11+ kurup PATH'e ekleyin.
  goto :end
)

:: 1) Venv oluştur/aktif et
echo(
echo [2/9] Sanal ortam (.venv) hazırlanıyor...
if not exist "%PYVENV%" (
  %PY_SYS% -m venv ".venv"
  if errorlevel 1 (
    echo( [HATA] Sanal ortam olusturulamadi.
    goto :end
  )
)
call "%ACTIVATE%"
if errorlevel 1 (
  echo( [HATA] Sanal ortam aktif edilemedi.
  goto :end
)

:: 2) Paketler
echo(
echo [3/9] Python bagimliliklari yukleniyor...
"%PYVENV%" -m pip install -U pip >nul
if exist "requirements.txt" (
  "%PYVENV%" -m pip install -r requirements.txt
) else (
  "%PYVENV%" -m pip install fastapi "uvicorn[standard]" sqlalchemy python-dotenv redis openai httpx
)
if errorlevel 1 (
  echo( [HATA] Bagimlilik kurulumu basarisiz.
  goto :end
)

:: 3) .env olustur/guncelle
echo(
echo [4/9] .env ayarlaniyor...
if not exist ".env" (
  echo # Uygulama ayarlari> ".env"
  echo LOG_LEVEL=INFO>> ".env"
  echo LLM_MODEL=gpt-4o-mini>> ".env"
  echo # LLM_FALLBACK_MODEL=gpt-4o-mini>> ".env"
  echo # REDIS_URL=redis://localhost:6379/0>> ".env"
  echo # DATABASE_URL=sqlite:///./app.db>> ".env"
  echo # OPENAI_BASE_URL=>> ".env"
)

:: Yardımcı: .env anahtarını ayarla (varsa günceller)
set "HAS_PS=0"
where powershell >nul 2>nul && set "HAS_PS=1"
if "%IS_CI%"=="1" goto :ci_env
goto :ask_env

:set_env
set "KEY=%~1"
set "VAL=%~2"
if "%VAL%"=="" goto :eof
if "%HAS_PS%"=="1" (
  powershell -NoProfile -Command ^
    "$p='.env';$k='%KEY%';$v='%VAL%';" ^
    "if (Test-Path $p) {(Get-Content $p) ^| Where-Object {$_ -notmatch \"^$k=.*\"} ^| Set-Content $p};" ^
    "Add-Content $p \"$k=$v\";"
) else (
  if exist ".env" (
    > ".env.tmp" type nul
    for /f "usebackq delims=" %%L in (".env") do (
      echo %%L| findstr /B /I "%KEY%=" >nul || echo %%L>> ".env.tmp"
    )
    move /Y ".env.tmp" ".env" >nul
  )
  echo %KEY%=%VAL%>> ".env"
)
goto :eof

:ci_env
if not "%OPENAI_API_KEY%"=="" call :set_env OPENAI_API_KEY "%OPENAI_API_KEY%"
if not "%REDIS_URL%"=="" call :set_env REDIS_URL "%REDIS_URL%"
if not "%DATABASE_URL%"=="" call :set_env DATABASE_URL "%DATABASE_URL%"
if not "%OPENAI_BASE_URL%"=="" call :set_env OPENAI_BASE_URL "%OPENAI_BASE_URL%"
echo(
echo( [CI] Ortam degiskenleri kullanildi; etkileşimli sorular atlandi.
goto :after_env

:ask_env
echo(
echo( OpenAI API anahtarinizi yazin (sk- ile baslar). Bos birakirsaniz mevcut deger korunur.
set "OPENAI_KEY_INPUT="
set /p OPENAI_KEY_INPUT= OPENAI_API_KEY: 
if not "%OPENAI_KEY_INPUT%"=="" call :set_env OPENAI_API_KEY "%OPENAI_KEY_INPUT%"

echo(
echo( (Opsiyonel) REDIS_URL yazin (ornek: redis://localhost:6379/0) - bos birakabilirsiniz
set "REDIS_URL_INPUT="
set /p REDIS_URL_INPUT= REDIS_URL: 
if not "%REDIS_URL_INPUT%"=="" call :set_env REDIS_URL "%REDIS_URL_INPUT%"

echo(
echo( (Opsiyonel) DATABASE_URL yazin (bos birakirsaniz sqlite varsayılanı kullanılır)
echo(  Ornek Postgres: postgresql+psycopg://user:pass@localhost:5432/app
set "DB_URL_INPUT="
set /p DB_URL_INPUT= DATABASE_URL: 
if not "%DB_URL_INPUT%"=="" call :set_env DATABASE_URL "%DB_URL_INPUT%"

echo(
echo( (Opsiyonel) OPENAI_BASE_URL yazin (Azure ya da proxy kullaniyorsaniz)
set "OAI_BASE_INPUT="
set /p OAI_BASE_INPUT= OPENAI_BASE_URL:
if not "%OAI_BASE_INPUT%"=="" call :set_env OPENAI_BASE_URL "%OAI_BASE_INPUT%"

:after_env

:: 4) API ve Worker (venv python ile)
set "UVICORN_CMD=""%PYVENV%"" -m uvicorn main:app --host 0.0.0.0 --port 8000"
set "WORKER_CMD=""%PYVENV%"" worker.py"

echo(
echo [5/9] API ve Worker baslatiliyor (ayri pencerelerde)...
if "%IS_CI%"=="1" (
  echo( [CI] API saglik testi calistiriliyor...
  "%PYVENV%" -c "from fastapi.testclient import TestClient; from main import app; import sys; resp=TestClient(app).get('/healthz'); sys.exit(0 if resp.status_code==200 else 1)" >nul 2>nul
  if errorlevel 1 (
    echo( [UYARI] API saglik testi CI ortaminda basarisiz oldu.
    call :reset_errorlevel
  ) else (
    echo(     API saglik testi basarili.
  )
  echo( [CI] Worker modulu test ediliyor...
  "%PYVENV%" worker.py --check-only >nul 2>nul
  if errorlevel 1 (
    echo( [UYARI] Worker kontrolu CI ortaminda basarisiz oldu.
    call :reset_errorlevel
  ) else (
    echo(     Worker betigi kontrolu gecti.
  )
) else (
  start "API" cmd /k %UVICORN_CMD%
  call :wait_api
  start "WORKER" cmd /k %WORKER_CMD%
)

:: 5) Frontend (parantezsiz akış)
echo(
echo [6/9] Frontend kontrol ediliyor...
set "FRONT_STARTED=0"
if not exist "package.json" goto :front_no_pkg

where node >nul 2>nul
if errorlevel 1 goto :front_no_node

if "%IS_CI%"=="1" (
  echo( [CI] npm install --ignore-scripts calistiriliyor...
  call npm install --ignore-scripts
  if errorlevel 1 goto :front_npm_fail
  echo( [CI] npm run build ile frontend dogrulaniyor...
  call npm run build
  if errorlevel 1 goto :front_build_fail
  goto :front_done
) else (
  echo( npm install calistiriliyor - ilk kurulumda zaman alabilir...
  call npm install
  if errorlevel 1 goto :front_npm_fail

  echo( npm run dev baslatiliyor (ayri pencerede)...
  start "FRONTEND" cmd /k "npm run dev"
  set "FRONT_STARTED=1"
  goto :front_done
)

:front_no_pkg
echo( package.json yok; frontend adimi atlandi.
call :reset_errorlevel
goto :front_done

:front_no_node
echo( [UYARI] Node.js bulunamadi. Frontend calistirilmayacak.
call :reset_errorlevel
goto :front_done

:front_npm_fail
echo( [UYARI] npm install basarisiz; frontend atlandi.
call :reset_errorlevel
goto :front_done

:front_build_fail
echo( [UYARI] npm run build basarisiz oldu.
call :reset_errorlevel
goto :front_done

:front_done

:: 6) Tarayici kisayollari
echo(
echo [7/9] Tarayici kisayollari aciliyor...
if "%IS_CI%"=="1" (
  echo( [CI] Tarayici kisayollari atlandi.
) else (
  start "" http://localhost:8000/docs
  if "%FRONT_STARTED%"=="1" start "" http://localhost:5173
)

:: 7) Hızlı komut ipuçları
echo(
echo [8/9] Komut ipuclari:
echo   Baslat:  curl -X POST http://localhost:8000/control/start
echo   Durdur:  curl -X POST http://localhost:8000/control/stop
echo   Hiz:     curl -X POST -H "Content-Type: application/json" -d "{\"factor\":1.2}" http://localhost:8000/control/scale
echo   Loglar:  curl "http://localhost:8000/logs/recent?limit=20"
echo   Wizard:  Sol menuden "Kurulum (Wizard)" (frontend aciksa)

echo(
echo [9/9] Kurulum tamamlandi ✅
echo - API:            http://localhost:8000
echo - API (health):   http://localhost:8000/healthz
echo - API Docs:       http://localhost:8000/docs
if "%FRONT_STARTED%"=="1" echo - Panel (Vite):   http://localhost:5173

goto :end

:wait_api
echo(
echo [5a] API ayaga kalkmasi bekleniyor...
set "HAS_CURL=0"
where curl >nul 2>nul && set "HAS_CURL=1"

set "READY=0"
for /L %%G in (1,1,30) do (
  if "%HAS_CURL%"=="1" (
    >nul 2>nul curl -s http://localhost:8000/healthz | findstr /I "\"ok\": true" && (
      set "READY=1"
      goto :api_ok
    )
  ) else (
    powershell -NoProfile -Command ^
      "try{$r=Invoke-WebRequest -UseBasicParsing http://localhost:8000/healthz; if($r.StatusCode -eq 200 -and $r.Content -match '""ok""\s*:\s*true'){exit 0}else{exit 1}}catch{exit 1}" >nul 2>nul
    if not errorlevel 1 (
      set "READY=1"
      goto :api_ok
    )
  )
  >nul timeout /t 1
)
:api_ok
if "%READY%"=="1" (
  echo(     API hazir.
) else (
  echo( [UYARI] API'dan cevap alinamadi. Pencereyi kontrol edin.
  call :reset_errorlevel
)
goto :eof

:reset_errorlevel
exit /b 0

:end
echo(
echo( [Bitti] Bu pencereyi kapatabilir veya acilan pencerelerden calismayi izleyebilirsiniz.
popd
endlocal
