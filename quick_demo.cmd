@echo off
REM ========================================
REM HIZLI DEMO BAŞLATMA SCRİPTİ
REM ========================================
REM
REM Bu script sunum için sistemi hızlıca başlatır
REM

echo.
echo ========================================
echo   PIYASA CHAT BOT - DEMO BAŞLATILIYOR
echo ========================================
echo.

REM 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi! Python 3.11+ yukleyin.
    pause
    exit /b 1
)
echo [OK] Python bulundu

REM 2. Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Node.js bulunamadi! Node 18+ yukleyin.
    pause
    exit /b 1
)
echo [OK] Node.js bulundu

REM 3. Install Python dependencies
echo.
echo [1/5] Python bagimliliklari kontrol ediliyor...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [HATA] Bagimliliklari yukleme hatasi!
    pause
    exit /b 1
)
echo [OK] Python bagimliliklari hazir

REM 4. Install Node dependencies
echo.
echo [2/5] Frontend bagimliliklari kontrol ediliyor...
call npm install >nul 2>&1
if errorlevel 1 (
    echo [HATA] npm install hatasi!
    pause
    exit /b 1
)
echo [OK] Frontend bagimliliklari hazir

REM 5. Check .env
if not exist .env (
    echo.
    echo [UYARI] .env dosyasi bulunamadi!
    echo         .env.example dosyasindan kopyalayin ve duzenleyin.
    pause
    exit /b 1
)
echo [OK] .env dosyasi mevcut

REM 6. Database init
echo.
echo [3/5] Veritabani baslat iliyor...
python -c "from database import create_tables, init_default_settings; create_tables(); init_default_settings(); print('[OK] Veritabani hazir')"
if errorlevel 1 (
    echo [HATA] Veritabani baslatilamadi!
    pause
    exit /b 1
)

REM 7. Auto setup (if config exists)
echo.
echo [4/5] Otomatik kurulum kontrol ediliyor...
if exist setup_config.json (
    echo setup_config.json bulundu, otomatik kurulum baslatiliyor...
    python auto_setup.py
    if errorlevel 1 (
        echo [UYARI] Otomatik kurulum tamamlanamadi.
    ) else (
        echo [OK] Otomatik kurulum tamamlandi
    )
) else (
    echo [BILGI] setup_config.json bulunamadi.
    echo          Ilk kurulum icin:
    echo          1. setup_config.json.example dosyasini setup_config.json olarak kopyalayin
    echo          2. Bot token'larini ekleyin
    echo          3. Bu scripti tekrar calistirin
    timeout /t 3 >nul
)

REM 8. Start services
echo.
echo [5/5] Servisler baslatiliyor...
echo.
echo ========================================
echo   SERVISLER AKTIF OLUYOR...
echo ========================================
echo.

REM Start API
echo [*] API baslatiliyor (port 8000)...
start "API Server" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 >nul

REM Start Worker
echo [*] Worker baslatiliyor...
start "Worker" cmd /k "python worker.py"
timeout /t 2 >nul

REM Start Frontend
echo [*] Frontend baslatiliyor (port 5173)...
start "Frontend" cmd /k "npm run dev"
timeout /t 3 >nul

echo.
echo ========================================
echo   SISTEM HAZIR!
echo ========================================
echo.
echo Dashboard: http://localhost:5173
echo API:       http://localhost:8000
echo Docs:      http://localhost:8000/docs
echo.
echo SUNUM ICIN YAPILACAKLAR:
echo 1. Dashboard'a gidin: http://localhost:5173
echo 2. Login olun (default: admin / .env'deki sifre)
echo 3. Settings'ten simulation_active = TRUE yapin
echo 4. Bot'lari Telegram grubuna ekleyin
echo 5. START SIMULATION butonuna basin!
echo.
echo SUNUM ONCESI KONTROL:
echo - Telegram grubunda botlar admin mi?
echo - Bot token'lari dogru mu?
echo - LLM_PROVIDER ayarli mi? (Groq oneriliyor)
echo - Ekran kaydedici hazir mi?
echo.
echo Herhangi bir terminal penceresi kapatilirsa servis durur!
echo.
pause
