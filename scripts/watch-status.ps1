param(
    [string]$BaseUrl = "http://127.0.0.1:8188",
    [int]$RefreshSeconds = 1
)
$ErrorActionPreference = "Stop"
$uri = "$($BaseUrl.TrimEnd('/'))/framepack-pause/status"
Write-Host "Watching FramePack Pause at $uri (Ctrl+C to stop)" -ForegroundColor Cyan
while ($true) {
    try {
        $s = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 5
        $pct = [double]$s.progress_percent
        $section = if ($s.total_sections) { "$($s.section)/$($s.total_sections)" } else { "-/-" }
        $step = if ($s.total_steps) { "$($s.step)/$($s.total_steps)" } else { "-/-" }
        $state = if ($s.paused) { "PAUSED" } elseif ($s.pause_requested) { "PAUSE REQUESTED" } else { $s.phase }
        $line = "{0,5:N1}% | Section {1,-7} | Step {2,-8} | {3,-18} | hooks S:{4} P:{5} N:{6}" -f $pct, $section, $step, $state, $s.sampler_patched, $s.pipeline_patched, $s.node_patched
        $color = if ($s.paused) { "Yellow" } elseif ($s.phase -eq "interrupted") { "Red" } else { "Green" }
        Write-Host ("{0:HH:mm:ss}  {1}" -f (Get-Date), $line) -ForegroundColor $color
    }
    catch {
        Write-Host ("{0:HH:mm:ss}  API error: {1}" -f (Get-Date), $_.Exception.Message) -ForegroundColor Red
    }
    Start-Sleep -Seconds ([Math]::Max(1, $RefreshSeconds))
}
