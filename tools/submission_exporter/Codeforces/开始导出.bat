@echo off
chcp 65001 >nul
title Codeforces Submission Exporter
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 cf_export_click.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python cf_export_click.py
    ) else (
        echo.
        echo 未找到 Python。
        echo 请先安装 Python 3，并在安装时勾选 Add Python to PATH。
        echo.
        pause
        exit /b 1
    )
)
