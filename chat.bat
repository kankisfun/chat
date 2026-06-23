@echo off
REM Change directory to the folder containing the batch file
cd /d "%~dp0"
REM Launch the Python script
python chat.py
REM Optional: Pause to view any output before the window closes
pause
