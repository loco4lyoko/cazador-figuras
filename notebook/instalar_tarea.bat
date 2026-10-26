@echo off
REM Instala las librerias y programa la revision de Goofish cada 30 minutos.
cd /d "%~dp0.."
python -m pip install -r requirements.txt
schtasks /Create /SC MINUTE /MO 30 /TN "Cazador Goofish" /TR "\"%~dp0goofish_notebook.bat\"" /F
echo.
echo Listo: Goofish se revisara cada 30 minutos mientras el notebook este encendido.
echo Para probar ahora mismo ejecuta: goofish_notebook.bat
pause
