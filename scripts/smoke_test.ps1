# scripts/smoke_test.ps1 - End-to-end smoke test for clean installs (Windows PowerShell)
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$HostName = "127.0.0.1"
$Port = if ($env:PORT) { [int]$env:PORT } else { 8000 }
$BaseUrl = "http://${HostName}:${Port}"
$DbPath = Join-Path $RepoRoot "output\apophenic.db"
$OutputDir = Join-Path $RepoRoot "output"
$LogPathOut = Join-Path $OutputDir "smoke_server_out.log"
$LogPathErr = Join-Path $OutputDir "smoke_server_err.log"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "=== Starting Apophenic Memory Smoke Test ===" -ForegroundColor Cyan

# 1. Start the FastAPI server in the background
Write-Host "[1/6] Starting FastAPI server on $BaseUrl..." -ForegroundColor Yellow

$UvicornCmd = $null
if ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\uvicorn.exe")) {
    $UvicornCmd = "$env:VIRTUAL_ENV\Scripts\uvicorn.exe"
} elseif (Test-Path (Join-Path $RepoRoot ".venv\Scripts\uvicorn.exe")) {
    $UvicornCmd = (Join-Path $RepoRoot ".venv\Scripts\uvicorn.exe")
} elseif (Test-Path (Join-Path $RepoRoot "..\.venv\Scripts\uvicorn.exe")) {
    $UvicornCmd = (Resolve-Path (Join-Path $RepoRoot "..\.venv\Scripts\uvicorn.exe")).Path
} elseif (Get-Command uvicorn.exe -ErrorAction SilentlyContinue) {
    $UvicornCmd = (Get-Command uvicorn.exe).Source
}

if ($UvicornCmd) {
    $ServerProcess = Start-Process -FilePath $UvicornCmd `
        -ArgumentList "apophenic_memory.api.main:app --host $HostName --port $Port" `
        -RedirectStandardOutput $LogPathOut `
        -RedirectStandardError $LogPathErr `
        -PassThru -WindowStyle Hidden
} else {
    $PythonCmd = "python"
    if ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
        $PythonCmd = "$env:VIRTUAL_ENV\Scripts\python.exe"
    } elseif (Test-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")) {
        $PythonCmd = (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    } elseif (Test-Path (Join-Path $RepoRoot "..\.venv\Scripts\python.exe")) {
        $PythonCmd = (Resolve-Path (Join-Path $RepoRoot "..\.venv\Scripts\python.exe")).Path
    }
    $ServerProcess = Start-Process -FilePath $PythonCmd `
        -ArgumentList "-m uvicorn apophenic_memory.api.main:app --host $HostName --port $Port" `
        -RedirectStandardOutput $LogPathOut `
        -RedirectStandardError $LogPathErr `
        -PassThru -WindowStyle Hidden
}

try {
    # Wait for server to become responsive
    Write-Host "Waiting for server to become ready..."
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "${BaseUrl}/timeline" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        $errLog = if (Test-Path $LogPathErr) { Get-Content $LogPathErr -Raw } else { "" }
        throw "FastAPI server failed to start or did not respond within 30 seconds.`nServer Error Log:`n$errLog"
    }
    Write-Host "Server is ready!" -ForegroundColor Green

    # 2. Hit GET /timeline and assert 200
    Write-Host "[2/6] Testing GET /timeline..." -ForegroundColor Yellow
    $timelineResponse = (curl.exe -s -o NUL -w "%{http_code}" "${BaseUrl}/timeline").Trim()
    if ($timelineResponse -ne "200") {
        throw "GET /timeline returned HTTP $timelineResponse, expected 200"
    }
    Write-Host "GET /timeline returned 200 OK." -ForegroundColor Green

    # 3. Hit POST /memories/generate and assert 200
    Write-Host "[3/6] Testing POST /memories/generate (calling LLM via Ollama)..." -ForegroundColor Yellow
    $genResponse = (curl.exe -s -o NUL -w "%{http_code}" `
        -X POST "${BaseUrl}/memories/generate" `
        -H "Content-Type: application/json" `
        -d "{\`"gap_start\`": \`"2012-03-02\`", \`"gap_end\`": \`"2012-03-26\`"}").Trim()

    if ($genResponse -ne "200") {
        throw "POST /memories/generate returned HTTP $genResponse, expected 200"
    }
    Write-Host "POST /memories/generate returned 200 OK." -ForegroundColor Green

    # 4. Check that output/apophenic.db exists on disk
    Write-Host "[4/6] Checking for output/apophenic.db..." -ForegroundColor Yellow
    if (-not (Test-Path $DbPath)) {
        throw "Database file $DbPath does not exist on disk after generation!"
    }
    Write-Host "Database file confirmed on disk: $DbPath" -ForegroundColor Green

    # 5. Hit POST /data/wipe with {"confirm": true}
    Write-Host "[5/6] Testing POST /data/wipe..." -ForegroundColor Yellow
    $wipeResponse = (curl.exe -s -o NUL -w "%{http_code}" `
        -X POST "${BaseUrl}/data/wipe" `
        -H "Content-Type: application/json" `
        -d "{\`"confirm\`": true}").Trim()

    if ($wipeResponse -ne "200") {
        throw "POST /data/wipe returned HTTP $wipeResponse, expected 200"
    }
    Write-Host "POST /data/wipe returned 200 OK." -ForegroundColor Green

    # 6. Assert that output/apophenic.db no longer exists on disk
    Write-Host "[6/6] Verifying output/apophenic.db deletion..." -ForegroundColor Yellow
    if (Test-Path $DbPath) {
        throw "Database file $DbPath still exists on disk after wipe!"
    }
    Write-Host "Database file confirmed deleted." -ForegroundColor Green

    Write-Host "=== All Smoke Tests Passed Successfully! ===" -ForegroundColor Green
} finally {
    # 7. Kill the server
    Write-Host "Stopping FastAPI server (PID: $($ServerProcess.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $LogPathOut -Force -ErrorAction SilentlyContinue
    Remove-Item $LogPathErr -Force -ErrorAction SilentlyContinue
}
