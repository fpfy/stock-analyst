$action = New-ScheduledTaskAction -Execute 'C:\Users\Fengpeng\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe' -Argument 'run_full_analysis.py --skip-selection' -WorkingDirectory 'C:\Users\Fengpeng\stock_analysis_system'
$trigger = New-ScheduledTaskTrigger -Daily -At 17:30
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'StockAnalysisDailyRun' -Action $action -Trigger $trigger -Settings $settings -Force
