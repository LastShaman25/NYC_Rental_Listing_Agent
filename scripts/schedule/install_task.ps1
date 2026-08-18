# Registers the weekday 6:00 AM refresh with Windows Task Scheduler (08 §15).
# Run once from an elevated-or-normal PowerShell in the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\schedule\install_task.ps1
# Inspect:  schtasks /Query /TN "RentalAgent Weekday Refresh" /V /FO LIST
# Pause:    schtasks /Change /TN "RentalAgent Weekday Refresh" /DISABLE
# Resume:   schtasks /Change /TN "RentalAgent Weekday Refresh" /ENABLE
# Remove:   schtasks /Delete /TN "RentalAgent Weekday Refresh" /F

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "local_data\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c cd /d `"$projectRoot`" && uv run --no-sync python -m rental_agent.jobs.weekday_refresh >> `"$logDir\scheduler.log`" 2>&1" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 6:00AM

# StartWhenAvailable: if the desktop was off at 6:00 AM, run when it wakes
# (08 §22 risk control); the run key still makes the day idempotent.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 5) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "RentalAgent Weekday Refresh" `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "NYC/NJ Rental Listing Agent weekday inventory refresh (6:00 AM, America/New_York local)" `
    -Force

Write-Host "Task registered: 'RentalAgent Weekday Refresh' (weekdays 6:00 AM, runs-when-available)."
