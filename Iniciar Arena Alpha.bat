@echo off
cd /d "%~dp0"
"C:\Users\Luiz Fernando Nunes\AppData\Local\Programs\Python\Python312\python.exe" main.py
if errorlevel 1 pause
