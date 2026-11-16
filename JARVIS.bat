@echo off
rem JARVIS.bat - Doble clic para abrir el panel de JARVIS
rem %~dp0 es la carpeta donde esta este archivo
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" lanzador.py
