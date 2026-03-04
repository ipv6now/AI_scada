@echo off
chcp 65001 >nul
cd /d "C:\Users\TUX\source\repos\HMI"

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: 检查并安装 psutil
python -c "import psutil" 2>nul
if errorlevel 1 (
    echo Installing psutil...
    pip install psutil
)

:: 启动程序
echo Starting SCADA Application...
python run_scada.py

pause
