#!/usr/bin/env powershell

# Stop LedFx Processes
# This script safely stops only Python LedFx processes to prevent file locking issues during builds

Write-Host "Checking for running Python LedFx processes..." -ForegroundColor Yellow

$stopped = $false
$currentPid = $PID

# Only target Python processes running LedFx specifically
try {
    # Enumerate all Python processes once via CIM, excluding the current PID
    $procs = Get-CimInstance Win32_Process `
        -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe'" `
        -ErrorAction SilentlyContinue

    foreach ($p in $procs | Where-Object { $_.ProcessId -ne $currentPid }) {
        try {
            $commandLine = $p.CommandLine
            # Match:
            #  - python -m ledfx
            #  - any __main__.py under a ledfx path
            #  - a --open-ui flag
            if ($commandLine -and ($commandLine -match '(?i)(^|\s)-m\s+ledfx(\s|$)|ledfx[\\\/]+__main__\.py|--open-ui')) {
                Write-Host "Found Python LedFx process: PID $($p.ProcessId)" -ForegroundColor Red
                Write-Host "Command: $commandLine" -ForegroundColor Gray
                Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process $($p.ProcessId)" -ForegroundColor Green
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
