# lixity-start.ps1 — Start, stop and status for Lixity on Windows.
#
# Usage:
#   .\scripts\lixity-start.ps1 [start|stop|restart|status] [-Port 8765] [-Open] [-Dir PATH]
#
# Compatible with Windows PowerShell 5.1 and PowerShell 7+ (no PS7-only syntax).
#
# A PID file is written to %LOCALAPPDATA%\lixity\lixity.pid so that stop/status
# can locate the running instance.  Log output goes to %LOCALAPPDATA%\lixity\lixity.log
# (stdout) and lixity.log.err (stderr); both are truncated on every start.
#
# Environment variables (defaults for the matching parameters):
#   LIXITY_PORT   Port to listen on (default: 8765)
#   LIXITY_HOST   Bind address     (default: 127.0.0.1)
#   LIXITY_DIR    Project path to open (optional)
#
# Run once to allow execution (user scope only):
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

[CmdletBinding()]
param(
    [ValidateSet("start","stop","restart","status")]
    [string]$Command = "start",

    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:LIXITY_PORT) { [int]$env:LIXITY_PORT } else { 8765 }),

    # NOTE: this must not be called $Host -- $Host is a read-only automatic
    # variable in PowerShell and would make the script fail to parse.
    [string]$BindHost = $(if ($env:LIXITY_HOST) { $env:LIXITY_HOST } else { "127.0.0.1" }),

    [string]$Dir = $(if ($env:LIXITY_DIR) { $env:LIXITY_DIR } else { "" }),

    [switch]$Open
)

$ErrorActionPreference = "Stop"

$RuntimeDir = Join-Path $env:LOCALAPPDATA "lixity"
$PidFile    = Join-Path $RuntimeDir "lixity.pid"
$LogFile    = Join-Path $RuntimeDir "lixity.log"
$ErrFile    = Join-Path $RuntimeDir "lixity.log.err"

function Get-LixityProcess {
    <#
      Returns the running lixity process, or $null.

      The process-name check guards against PID reuse: a recycled PID would
      otherwise make stop/status target an unrelated process.
    #>
    if (-not (Test-Path $PidFile)) { return $null }
    $ProcessId = [int](Get-Content $PidFile -Raw).Trim()
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return $null }
    if ($proc.ProcessName -notlike "lixity*") { return $null }
    return $proc
}

function Test-PortAccepts {
    <#
      True once the port accepts a TCP connection.

      Deliberately not a log grep. The server prints its banner with Write-Output,
      and redirected stdout is block-buffered, so for a long-running process the
      banner may sit in the buffer indefinitely and a log-based readiness check
      would never succeed. Connecting is direct and buffering-independent.
    #>
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync($BindHost, $Port)
        if (-not $task.Wait(500)) { return $false }
        return $client.Connected
    }
    catch { return $false }
    finally { $client.Close() }
}

function Test-PortInUse {
    # Get-NetTCPConnection ships with Windows 8/Server 2012 and newer.  If the
    # NetTCPIP module is unavailable, report "free" and let lixity report the
    # real bind error instead of failing the whole script.
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) { return $false }
    $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Resolve-Lixity {
    $local = Join-Path (Get-Location) ".venv\Scripts\lixity.exe"
    if (Test-Path $local) { return $local }
    $global = Get-Command lixity -ErrorAction SilentlyContinue
    if ($global) { return $global.Source }
    throw "[ERR] lixity not found. Install with: uv tool install 'git+https://github.com/mfahsold/lixity.git'"
}

function Start-Lixity {
    $running = Get-LixityProcess
    if ($running) {
        Write-Host "[OK]  Lixity is already running (PID $($running.Id)) -> http://${BindHost}:${Port}/"
        return
    }
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force }

    if (Test-PortInUse) {
        $owner = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
        throw "[ERR] Port $Port is in use by PID $owner.`n" +
              "      Choose another port:  .\scripts\lixity-start.ps1 -Port <PORT> start"
    }

    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

    $lixity = Resolve-Lixity
    $serveArgs = @("serve","--host",$BindHost,"--port","$Port")
    if ($Dir)  { $serveArgs += $Dir }
    if ($Open) { $serveArgs += "--open" }

    # -RedirectStandardOutput truncates the log, so the readiness check below
    # can never match a line left over from a previous run.
    $startArgs = @{
        FilePath               = $lixity
        ArgumentList           = $serveArgs
        RedirectStandardOutput = $LogFile
        RedirectStandardError  = $ErrFile
        PassThru               = $true
    }
    # Start-Process rejects -WindowStyle on non-Windows hosts.  $env:OS is set on
    # both Windows PowerShell 5.1 and PowerShell 7 on Windows.
    if ($env:OS -eq "Windows_NT") { $startArgs["WindowStyle"] = "Hidden" }
    $proc = Start-Process @startArgs

    # Give it up to 15 s to accept connections.
    $deadline = (Get-Date).AddSeconds(15)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if (Test-PortAccepts) { $ready = $true; break }
        if ($proc.HasExited) { break }
    }

    $proc.Id | Set-Content $PidFile

    if ($ready) {
        Write-Host "[OK]  Lixity started (PID $($proc.Id)) -> http://${BindHost}:${Port}/"
        Write-Host "      Log: $LogFile"
    } else {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        $why = if ($proc.HasExited) { "exited with code $($proc.ExitCode)" }
                else { "did not start accepting connections on ${BindHost}:${Port}" }
        throw "[ERR] Lixity $why. Check: $ErrFile"
    }
}

function Stop-Lixity {
    $running = Get-LixityProcess
    if (-not $running) {
        if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
        Write-Host "[--]  Lixity is not running."
        return
    }
    # Windows has no SIGINT delivery for console apps via Stop-Process, so this
    # terminates the process.  Use `systemctl`-style graceful stops on Linux/macOS.
    Stop-Process -Id $running.Id
    $running.WaitForExit(5000) | Out-Null
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "[OK]  Lixity stopped (PID $($running.Id))."
}

function Get-LixityStatus {
    $running = Get-LixityProcess
    if ($running) {
        Write-Host "[OK]  Lixity is running (PID $($running.Id)) -> http://${BindHost}:${Port}/"
    } else {
        Write-Host "[--]  Lixity is not running."
        exit 1
    }
}

switch ($Command) {
    "start"   { Start-Lixity }
    "stop"    { Stop-Lixity }
    "restart" { Stop-Lixity; Start-Sleep -Seconds 1; Start-Lixity }
    "status"  { Get-LixityStatus }
}
