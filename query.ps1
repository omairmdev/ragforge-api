param(
    [Parameter(Mandatory=$true)][string]$Question,
    [string]$ConversationId = "s1"
)

$body = @{ question = $Question; conversation_id = $ConversationId } | ConvertTo-Json
$url = "http://localhost:8000/query"

Write-Host ""
Write-Host "Q: $Question" -ForegroundColor Yellow
Write-Host ""

curl.exe -N -s -X POST $url -H "Content-Type: application/json" -d ($body -replace '"','\"') | ForEach-Object {
    if ($_ -match '^event: (.+)$') {
        $eventType = $matches[1].Trim()
    }
    if ($_ -match '^data: (.+)$') {
        $data = $matches[1]
        switch ($eventType) {
            "token" {
                $token = $data.Trim('"') -replace '\\n', "`n" -replace '\\t', "`t"
                Write-Host $token -NoNewline -ForegroundColor White
            }
            "sources" {
                Write-Host "`n`n=== Sources ===" -ForegroundColor Cyan
                $sources = $data | ConvertFrom-Json
                $i = 1
                foreach ($s in $sources) {
                    Write-Host "`n[$i] " -NoNewline -ForegroundColor Cyan
                    Write-Host "file: $($s.file_name)  |  page: $($s.page)  |  score: $([math]::Round($s.score, 3))" -ForegroundColor Gray
                    Write-Host "    $($s.text.Substring(0, [math]::Min(120, $s.text.Length)))..." -ForegroundColor DarkGray
                    $i++
                }
            }
            "done" {
                Write-Host "`n`n=== Done ===" -ForegroundColor Green
            }
            "error" {
                Write-Host "`nERROR: $data" -ForegroundColor Red
            }
        }
    }
}
Write-Host ""