# Review a git diff from any repo against a running Local Copilot API server.
#
# Examples:
#   .\review-diff.ps1                                   # working-tree diff of the current repo
#   .\review-diff.ps1 -Repo C:\dev\upi-mesh -GitRef HEAD~1
#   .\review-diff.ps1 -Staged                           # staged changes only
#   .\review-diff.ps1 -Model mistral:7b
param(
    [string]$Repo = ".",
    [string]$GitRef = "HEAD",
    [string]$Server = "http://127.0.0.1:8000",
    [string]$Model,
    [switch]$Staged
)

$diffArgs = @("-C", $Repo, "diff")
if ($Staged) { $diffArgs += "--staged" } else { $diffArgs += $GitRef }
$diff = (git @diffArgs | Out-String)

if (-not $diff.Trim()) {
    Write-Error "No diff found in '$Repo' (ref: $(if ($Staged) { '--staged' } else { $GitRef }))."
    exit 1
}

$payload = @{ diff = $diff }
if ($Model) { $payload.model = $Model }

try {
    $resp = Invoke-RestMethod -Uri "$Server/review" -Method Post -ContentType 'application/json' `
        -Body ($payload | ConvertTo-Json -Compress) -TimeoutSec 300
} catch {
    Write-Error "Review request failed: $($_.Exception.Message). Is the server running? Start it with: uvicorn app.api:app"
    exit 1
}

$resp.review | ConvertTo-Json -Depth 5
