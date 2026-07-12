param(
  [Parameter(Mandatory = $true)][string]$RunId,
  [string]$ApiBase = "http://127.0.0.1:8000",
  [string]$LogPath = "output/full-run-monitor.log"
)

$ErrorActionPreference = "Stop"
function Write-MonitorLog([string]$Message) {
  $line = "$(Get-Date -Format o) $Message"
  Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8
}
function Wait-Run([string]$Id) {
  while ($true) {
    $run = Invoke-RestMethod "$ApiBase/api/runs/$Id"
    $processed = $run.progress.items_processed
    $total = $run.progress.items_total
    Write-MonitorLog "run=$Id status=$($run.execution_status) processed=$processed total=$total failed=$($run.progress.items_failed)"
    if ($run.execution_status -notin @("queued", "running")) { return $run }
    Start-Sleep -Seconds 30
  }
}

try {
  $root = Wait-Run $RunId
  if ($root.execution_status -ne "completed") { throw "Root run ended with $($root.execution_status)" }
  if ([int]$root.progress.items_failed -gt 0) {
    $retry = Invoke-RestMethod -Method Post "$ApiBase/api/runs/$RunId/retry-failures" -ContentType "application/json" -Body "{}"
    Write-MonitorLog "retry_created=$($retry.run_id)"
    $retryResult = Wait-Run $retry.run_id
    Write-MonitorLog "retry_finished=$($retryResult.execution_status) failed=$($retryResult.progress.items_failed)"
  }
  $report = Invoke-RestMethod -Method Post "$ApiBase/api/runs/$RunId/report" -ContentType "application/json" -Body "{}"
  Write-MonitorLog "report_ready=$($report.report_ready) report_path=$($report.report_path)"
} catch {
  Write-MonitorLog "monitor_error=$($_.Exception.Message)"
  exit 1
}
