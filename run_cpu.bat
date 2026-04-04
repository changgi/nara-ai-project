@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=%~dp0
set NARA_MODE=cpu
set CUDA_VISIBLE_DEVICES=
python run.py --cpu %*
if errorlevel 1 pause
