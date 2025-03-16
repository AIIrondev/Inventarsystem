@echo off
REM filepath: c:\Users\User\repos\Inventarsystem\start-windows.cmd

echo Starting Inventarsystem...

REM Set up directories and variables
set APP_DIR=%~dp0
set LOGS_DIR=%APP_DIR%logs
set WEB_DIR=%APP_DIR%Web
set DC_DIR=%APP_DIR%DeploymentCenter
set TIMESTAMP=%date:~-4,4%-%date:~-7,2%-%date:~-10,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set WEB_LOG_FILE=%LOGS_DIR%\web_%TIMESTAMP%.log
set DC_LOG_FILE=%LOGS_DIR%\dc_%TIMESTAMP%.log

REM Create logs directory if it doesn't exist
if not exist "%LOGS_DIR%" (
    echo Creating logs directory...
    mkdir "%LOGS_DIR%"
)

REM Check if Python and pip are installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH.
    goto :error
)

where pip >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: pip is not installed or not in PATH.
    goto :error
)

REM Install required packages if they're not already installed
echo Checking required packages...
pip install waitress flask pymongo qrcode pillow >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Some packages could not be installed. The application might not work correctly.
)

REM Create temporary server scripts
echo from waitress import serve > "%WEB_DIR%\run_server.py"
echo import logging >> "%WEB_DIR%\run_server.py"
echo import app >> "%WEB_DIR%\run_server.py"
echo logging.basicConfig(filename=r'%WEB_LOG_FILE%', level=logging.DEBUG, format='%%(asctime)s %%(levelname)s: %%(message)s') >> "%WEB_DIR%\run_server.py"
echo print("Starting Web server on http://localhost:5000") >> "%WEB_DIR%\run_server.py"
echo serve(app.app, host='0.0.0.0', port=5000) >> "%WEB_DIR%\run_server.py"

echo from waitress import serve > "%DC_DIR%\run_server.py"
echo import logging >> "%DC_DIR%\run_server.py"
echo import app >> "%DC_DIR%\run_server.py"
echo logging.basicConfig(filename=r'%DC_LOG_FILE%', level=logging.DEBUG, format='%%(asctime)s %%(levelname)s: %%(message)s') >> "%DC_DIR%\run_server.py"
echo print("Starting DeploymentCenter server on http://localhost:5001") >> "%DC_DIR%\run_server.py"
echo serve(app.app, host='0.0.0.0', port=5001) >> "%DC_DIR%\run_server.py"

echo Starting Web server (Waitress)...
cd "%WEB_DIR%"
start /b conhost.exe --icon="%APP_DIR%web.ico" cmd /k "echo Web server log: %WEB_LOG_FILE% && python run_server.py"

echo Starting DeploymentCenter server (Waitress)...
cd "%DC_DIR%"
start /b conhost.exe --icon="%APP_DIR%deployment.ico" cmd /k "echo DeploymentCenter server log: %DC_LOG_FILE% && python run_server.py"

timeout /t 2 >nul
echo.
echo Servers are starting up...
echo Web interface will be available at: http://localhost:5000
echo DeploymentCenter will be available at: http://localhost:5001
echo.
echo Log files:
echo - Web: %WEB_LOG_FILE%
echo - DeploymentCenter: %DC_LOG_FILE%
echo.
echo Press any key to stop the servers...
pause >nul

REM Find and kill the Python processes
echo Stopping servers...
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" ^| find "python"') do (
    taskkill /pid %%p /f >nul 2>nul
)

REM Clean up temporary scripts
del "%WEB_DIR%\run_server.py" >nul 2>nul
del "%DC_DIR%\run_server.py" >nul 2>nul

REM Erstelle Verknüpfungen mit Icons
echo Creating shortcuts with icons...
set ICON_WEB=%APP_DIR%Web\static\favicon.ico
set ICON_DC=%APP_DIR%DeploymentCenter\static\favicon.ico

REM PowerShell-Befehl für Verknüpfungserstellung
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\Inventarsystem Web.lnk'); $Shortcut.TargetPath = 'http://localhost:5000'; $Shortcut.IconLocation = '%ICON_WEB%'; $Shortcut.Save()"

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\Inventarsystem DeploymentCenter.lnk'); $Shortcut.TargetPath = 'http://localhost:5001'; $Shortcut.IconLocation = '%ICON_DC%'; $Shortcut.Save()"

echo Servers stopped.
goto :end

:error
echo.
echo An error occurred. Please check the requirements and try again.
exit /b 1

:end
exit /b 0