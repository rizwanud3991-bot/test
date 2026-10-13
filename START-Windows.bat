@echo off
setlocal EnableExtensions
title BRD Solution Agent
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "KEYFILE=%APPDATA%\brd_agent\key.txt"
set "VPY=%~dp0.venv\Scripts\python.exe"

echo.
echo  ==========================================
echo     BRD SOLUTION AGENT
echo  ==========================================
echo.

rem ---- 1. Make sure Python is installed -------------------------------
set "PY="
py --version >nul 2>nul && set "PY=py"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo  Python is not installed on this computer.
    echo.
    echo  A web page will open now. Click the yellow "Download Python" button
    echo  and install it. IMPORTANT: tick the box "Add Python to PATH".
    echo  Then double-click START again.
    start "" "https://www.python.org/downloads/"
    echo.
    pause
    exit /b 1
)

rem ---- 2. First time only: install what the agent needs ---------------
if not exist "%~dp0.venv\installed.txt" (
    echo  First time setup. Please wait, this can take a few minutes...
    echo.
    %PY% -m venv "%~dp0.venv"
    if errorlevel 1 goto setupfailed
    "%VPY%" -m pip install --disable-pip-version-check -q -r "%~dp0requirements.txt"
    if errorlevel 1 goto setupfailed
    echo done> "%~dp0.venv\installed.txt"
    echo  Setup finished.
    echo.
)

rem ---- 3. Claude key (asked once, then remembered) --------------------
if not defined ANTHROPIC_API_KEY (
    if exist "%KEYFILE%" set /p ANTHROPIC_API_KEY=<"%KEYFILE%"
)
if not defined ANTHROPIC_API_KEY call :askkey

rem ---- 4. Menu ----------------------------------------------------------
:menu
echo.
echo  What do you want to do?
echo.
echo    1 = Make the solution pack from my documents
echo    2 = Ask a question about my project
echo    3 = Change my Claude key
echo    4 = Close
echo.
choice /c 1234 /n /m "  Press 1, 2, 3 or 4: "
if errorlevel 4 goto end
if errorlevel 3 (
    call :askkey
    goto menu
)
if errorlevel 2 goto ask
goto run

rem ---- Make the solution pack ------------------------------------------
:run
if not exist "%~dp0brds" mkdir "%~dp0brds"
:checkdocs
dir /b /a-d "%~dp0brds" 2>nul | findstr /r "." >nul
if errorlevel 1 (
    echo.
    echo  The "brds" folder is empty.
    echo  A folder window will open now. Copy your requirement documents into it
    echo  ^(Word, PDF or text files^). Then come back here and press any key.
    start "" explorer "%~dp0brds"
    echo.
    pause
    goto checkdocs
)
echo.
echo  Working... This can take 20 to 40 minutes. You can use your computer meanwhile.
echo  Do NOT close this window.
echo.
"%VPY%" -m brd_agent run -i "%~dp0brds" -o "%~dp0output"
if errorlevel 1 goto failed
echo.
echo  ==========================================
echo     DONE! Your solution pack is opening now.
echo  ==========================================
if exist "%~dp0output\solution_pack.html" start "" "%~dp0output\solution_pack.html"
start "" explorer "%~dp0output"
goto menu

rem ---- Ask a question ----------------------------------------------------
:ask
if not exist "%~dp0output\solution_pack.html" (
    echo.
    echo  First make the solution pack ^(press 1^), then you can ask questions.
    goto menu
)
echo.
echo  Who should the answer be for?
echo    1 = Boss / executive
echo    2 = Business team (simple words)
echo    3 = Technical team
choice /c 123 /n /m "  Press 1, 2 or 3: "
set "AUD=technical"
if errorlevel 1 set "AUD=executive"
if errorlevel 2 set "AUD=business"
if errorlevel 3 set "AUD=technical"
echo.
echo  Type your question and press Enter. Press Enter on an empty line to go back.
"%VPY%" -m brd_agent ask -i "%~dp0brds" -o "%~dp0output" --audience %AUD%
if errorlevel 1 goto failed
goto menu

rem ---- Problems ----------------------------------------------------------
:failed
echo.
echo  Something went wrong. Please read the message above.
echo  If it says "Authentication failed", your Claude key is wrong or has no credit.
echo  If the internet stopped, just try again: finished parts are kept.
echo.
choice /c YN /n /m "  Do you want to enter a new Claude key? Press Y (yes) or N (no): "
if errorlevel 2 goto menu
call :askkey
goto menu

:setupfailed
echo.
echo  Setup failed. Please check your internet connection and double-click START again.
if exist "%~dp0.venv" rmdir /s /q "%~dp0.venv"
pause
exit /b 1

rem ---- Ask for the key and save it for next time -------------------------
:askkey
echo.
echo  Paste your Claude key and press Enter.
echo  ^(It starts with sk-ant- . To paste: right-click inside this window.^)
set "ANTHROPIC_API_KEY="
set /p "ANTHROPIC_API_KEY=  Key: "
if not defined ANTHROPIC_API_KEY goto askkey
if /i not "%ANTHROPIC_API_KEY:~0,7%"=="sk-ant-" (
    echo  That does not look like a Claude key. It must start with sk-ant- . Try again.
    goto askkey
)
if not exist "%APPDATA%\brd_agent" mkdir "%APPDATA%\brd_agent"
>"%KEYFILE%" echo %ANTHROPIC_API_KEY%
echo  Key saved. You will not be asked again.
goto :eof

:end
endlocal
exit /b 0
