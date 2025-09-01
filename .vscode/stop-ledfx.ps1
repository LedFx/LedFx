#!/usr/bin/env powershell

# Stop LedFx Processes
# This script safely stops only Python LedFx processes to prevent file locking issues during builds

Write-Host "Checking for running Python LedFx processes..." -ForegroundColor Yellow

$stopped = $false
$currentPid = $PID

# Only target Python processes running LedFx specifically
try {
    $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $currentPid }
    foreach ($proc in $pythonProcesses) {
        try {
            $commandLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            # Only match actual LedFx Python execution patterns
            if ($commandLine -and (
                $commandLine -like "*ledfx*__main__.py*" -or
                $commandLine -like "*LedFx*__main__.py*" -or
                ($commandLine -like "*ledfx\__main__.py*") -or
                ($commandLine -like "*LedFx\__main__.py*") -or
                ($commandLine -like "*python*" -and $commandLine -like "*ledfx*" -and $commandLine -like "*--open-ui*")
            )) {
                Write-Host "Found Python LedFx process: PID $($proc.Id)" -ForegroundColor Red
                Write-Host "Command: $commandLine" -ForegroundColor Gray
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process $($proc.Id)" -ForegroundColor Green
                $stopped = $true
            }
        } catch {
            # Silent fail for processes we can't access
        }
    }
} catch {
    Write-Host "Could not check python processes: $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($stopped) {
    Write-Host "Waiting 3 seconds for processes to fully terminate..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    Write-Host "Python LedFx processes stopped successfully" -ForegroundColor Green
} else {
    Write-Host "No running Python LedFx processes found" -ForegroundColor Cyan
}
