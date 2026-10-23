@echo off
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:8080/"
set "VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

set "PYTHON_COMMAND="%VENV_PYTHON%""
if not exist "%VENV_PYTHON%" (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_COMMAND=py -3"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo Python was not found. Install Python 3.10 or newer and run this launcher again.
            goto :failed
        )
        set "PYTHON_COMMAND=python"
    )
)

%PYTHON_COMMAND% -c "import flask, werkzeug" >nul 2>&1
if errorlevel 1 (
    echo Flask dependencies are missing. Internet is only needed to install them:
    echo   %PYTHON_COMMAND% -m pip install -r requirements.txt
    goto :failed
)

%PYTHON_COMMAND% -c "import sys, urllib.request; response=urllib.request.urlopen(sys.argv[1], timeout=2); sys.exit(0 if b'HostelConnect' in response.read() else 1)" "%APP_URL%" >nul 2>&1
if not errorlevel 1 goto :open_browser

echo Starting HostelConnect. Please wait for the local server...
start "" /B %PYTHON_COMMAND% app.py
for /L %%i in (1,1,30) do (
    %PYTHON_COMMAND% -c "import sys, urllib.request; response=urllib.request.urlopen(sys.argv[1], timeout=2); sys.exit(0 if b'HostelConnect' in response.read() else 1)" "%APP_URL%" >nul 2>&1
    if not errorlevel 1 goto :open_browser
    timeout /t 1 /nobreak >nul
)

echo The server did not respond. Read the Python startup error above. If dependencies are missing, install them with:
echo   %PYTHON_COMMAND% -m pip install -r requirements.txt
goto :failed

:open_browser
echo HostelConnect is ready at %APP_URL%
start "" "%APP_URL%"
echo Keep this window open while using HostelConnect.
pause
exit /b 0

:failed
echo.
pause
exit /b 1
