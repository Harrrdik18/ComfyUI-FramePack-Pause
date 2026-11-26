param([string]$BaseUrl = "http://127.0.0.1:8188")
$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")
$statusUrl = "$BaseUrl/framepack-pause/status"
Write-Host "Checking FramePack Pause API at $BaseUrl" -ForegroundColor Cyan
$s = Invoke-RestMethod -Uri $statusUrl -Method Get -TimeoutSec 5
$s | Format-List sampler_patched,pipeline_patched,node_patched,phase,section,total_sections,step,total_steps,progress_percent
$missing = @()
if (-not $s.sampler_patched) { $missing += "sampler_patched" }
if (-not $s.pipeline_patched) { $missing += "pipeline_patched" }
if (-not $s.node_patched) { $missing += "node_patched" }
if ($missing.Count -gt 0) { throw "Missing hooks: $($missing -join ', '). Check ComfyUI startup logs." }
Write-Host "All three hooks are detected." -ForegroundColor Green
Write-Host "Testing pause/resume API while idle (no generation is started or interrupted)." -ForegroundColor Yellow
$pause = Invoke-RestMethod -Uri "$BaseUrl/framepack-pause/pause" -Method Post -TimeoutSec 5
if (-not $pause.pause_requested) { throw "Pause endpoint did not set pause_requested." }
$resume = Invoke-RestMethod -Uri "$BaseUrl/framepack-pause/resume" -Method Post -TimeoutSec 5
if ($resume.pause_requested) { throw "Resume endpoint did not clear pause_requested." }
Write-Host "API smoke test passed. Run a real FramePack job to test sampler pause and progress." -ForegroundColor Green
