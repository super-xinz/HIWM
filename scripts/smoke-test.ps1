param(
    [string]$BaseUrl = "http://127.0.0.1:8283",
    [string]$AccessCode = $env:DEMO_ACCESS_CODE
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")
$stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$userId = "smoke-$stamp"
$sessionId = "smoke-session-$stamp"
$turnId = "smoke-turn-$stamp"
$smokeMessage = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("5Lul5ZCO5Zue562U55+t5LiA54K577yM5oiR5pyA6L+R5Zyo5YeG5aSH5LiA5Liq6YeN6KaB5Yaz5a6a44CC"))

Write-Host "[1/5] aggregate health"
$health = Invoke-RestMethod -Uri "$BaseUrl/api/health"
if ($health.services.application -ne "ok") { throw "application health failed" }

$webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
if ($AccessCode) {
    Write-Host "[2/5] server-side access login"
    $loginBody = @{ code = $AccessCode } | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri "$BaseUrl/api/v1/access/login" -Method Post -WebSession $webSession `
        -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($loginBody)) | Out-Null
} else {
    Write-Host "[2/5] access login skipped (DEMO_ACCESS_CODE empty)"
}

Write-Host "[3/5] read or initialize profile"
$before = Invoke-RestMethod -Uri "$BaseUrl/api/v1/companion/profile/$userId" -WebSession $webSession
$beforeVersion = $before.profile.profile_version

Write-Host "[4/5] complete profile-aware chat"
$chatBody = @{
    user_id = $userId
    session_id = $sessionId
    turn_id = $turnId
    message = $smokeMessage
    profile_enabled = $true
} | ConvertTo-Json -Compress
$chat = Invoke-RestMethod -Uri "$BaseUrl/api/v1/companion/chat" -Method Post `
    -WebSession $webSession -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($chatBody))
if (-not $chat.reply) { throw "chat reply is empty" }
if ($chat.turn_id -ne $turnId) { throw "turn_id mismatch" }
if ($chat.profile_update.status -ne "updated") { throw "expected profile update, got $($chat.profile_update.status)" }

Write-Host "[5/5] verify persisted messages and refreshed profile"
$messages = Invoke-RestMethod -Uri "$BaseUrl/api/v1/companion/sessions/$sessionId/messages" -WebSession $webSession
if ($messages.messages.Count -ne 2) { throw "expected two persisted messages" }
$after = Invoke-RestMethod -Uri "$BaseUrl/api/v1/companion/profile/$userId" -WebSession $webSession
if ($after.profile.profile_version -le $beforeVersion) { throw "profile version did not advance" }

Write-Host "Smoke test passed"
Write-Host "user=$userId before_profile_version=$beforeVersion after_profile_version=$($after.profile.profile_version)"
Write-Host "profile_update=$($chat.profile_update.status) model=$($chat.model)"
