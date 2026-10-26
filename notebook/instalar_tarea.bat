@echo off
REM Instala las librerias y programa la revision cada 30 minutos.
cd /d "%~dp0.."
python -m pip install -r requirements.txt
schtasks /Create /SC MINUTE /MO 30 /TN "Cazador Figuras Notebook" /TR "\"%~dp0rastrear_notebook.bat\"" /F
echo.
echo Listo: los sitios del notebook se revisaran cada 30 minutos mientras el notebook este encendido.
echo Para probar ahora mismo ejecuta: rastrear_notebook.bat
pause
