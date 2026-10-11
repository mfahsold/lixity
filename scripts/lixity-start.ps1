# Compatibility wrapper; the installed CLI owns all lifecycle behavior.
# Direct invocation preserves space-containing arguments without Start-Process.
[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Command = "start",
    [ValidateRange(1, 65535)]
    [int]$Port,
    [string]$BindHost,
    [string]$Dir,
    [string]$Language,
    [switch]$Open
)
$ErrorActionPreference = "Stop"
$executable = Get-Command lixity -CommandType Application -ErrorAction SilentlyContinue
if (-not $executable) {
    Write-Error "lixity is not on PATH. Follow https://mfahsold.github.io/lixity/guides/installation.html"
    exit 1
}
$arguments = @("service", $Command)
if ($PSBoundParameters.ContainsKey("Port")) { $arguments += @("--port", "$Port") }
if ($PSBoundParameters.ContainsKey("BindHost")) { $arguments += @("--host", $BindHost) }
if ($PSBoundParameters.ContainsKey("Language")) { $arguments += @("--language", $Language) }
if ($Open) { $arguments += "--open" }
if ($Dir) { $arguments += $Dir }
& $executable.Source @arguments
exit $LASTEXITCODE
