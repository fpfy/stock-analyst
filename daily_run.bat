@echo off
cd /d C:\Users\Fengpeng\stock_analysis_system
C:\Users\Fengpeng\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe run_full_analysis.py --skip-selection >> C:\Users\Fengpeng\stock_analysis_system\logs\daily_run.log 2>&1
