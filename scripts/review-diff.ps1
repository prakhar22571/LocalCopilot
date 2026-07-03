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

# git emits UTF-8; decode it as such regardless of the console's code page
$prevEnc = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { $diff = (git @diffArgs | Out-String) } finally { [Console]::OutputEncoding = $prevEnc }

if (-not $diff.Trim()) {
    Write-Error "No diff found in '$Repo' (ref: $(if ($Staged) { '--staged' } else { $GitRef }))."
    exit 1
}

$payload = @{ diff = $diff }
if ($Model) { $payload.model = $Model }

# Send explicit UTF-8 bytes: Invoke-RestMethod encodes string bodies as Latin-1,
# which corrupts any non-ASCII character in the diff and the server rejects the JSON
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Compress))
try {
    $resp = Invoke-RestMethod -Uri "$Server/review" -Method Post -ContentType 'application/json; charset=utf-8' `
        -Body $bodyBytes -TimeoutSec 300
} catch {
    Write-Error "Review request failed: $($_.Exception.Message). Is the server running? Start it with: uvicorn app.api:app"
    exit 1
}

$resp.review | ConvertTo-Json -Depth 5
