@echo off
chcp 65001 >nul
title 15-Minute Crypto Quant Pipeline & Web Server

echo ======================================================================
echo    ETH 3x & Core 资金费率套利量化服务端 (15分钟统一流水线)
echo ======================================================================
echo.
echo [1/3] 正在检测 Python 运行环境...

set PYTHON_EXE=C:\Users\liuqi\anaconda3\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

"%PYTHON_EXE%" --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 未检测到有效的 Python 环境，请检查 PATH 或 Anaconda 安装。
    pause
    exit /b 1
)
echo       Python 路径: %PYTHON_EXE%

echo.
echo [2/3] 正在定位项目根目录...
cd /d "%~dp0\.."
echo       工作目录: %CD%

echo.
echo [3/3] 正在启动 15 分钟高频流水线与 Web 监控看板 (Port: 8088)...
echo       公网专属隧道: https://percolate-zipfile-corned.ngrok-free.dev
echo       本地访问地址: http://127.0.0.1:8088
echo.
echo 提示: 按 Ctrl + C 可安全停止服务。
echo ======================================================================
echo.

"%PYTHON_EXE%" -m server.main --port 8088 --interval 900

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] 服务端异常退出，错误码: %ERRORLEVEL%
    pause
)
