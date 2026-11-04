# Share Off Script on the internet through an ngrok tunnel.
#
#   .\share.ps1          # live AI (uses the keys in .env)
#   .\share.ps1 -Mock    # no AI keys used: rule-based characters and template replies
#
# It builds the game, starts the server on port 8000 in its own window, opens an ngrok tunnel in
# another window, and prints the public https:// link. Close those two windows to stop sharing.
param([switch]$Mock)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Pick up PATH changes made by installers since this terminal opened.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) { throw "ngrok is not installed (winget install Ngrok.Ngrok)." }
ngrok config check *> $null
if ($LASTEXITCODE -ne 0) { throw "ngrok has no authtoken yet. Run: ngrok config add-authtoken <your token>" }

Write-Host "Building the game..." -ForegroundColor Cyan
npm --prefix "$root\frontend" run build --silent
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

# Free port 8000 (an old server there would serve stale code).
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

if ($Mock) { $env:AI_PROVIDER = "mock" } else { Remove-Item Env:AI_PROVIDER -ErrorAction SilentlyContinue }
Write-Host "Starting the game server..." -ForegroundColor Cyan
Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" -WorkingDirectory "$root\backend" `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"

$ok = $false
for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
  Start-Sleep -Milliseconds 500
  try { $ok = (Invoke-RestMethod http://127.0.0.1:8000/api/health).status -eq "ok" } catch { }
}
if (-not $ok) { throw "The game server did not start. Check its window for errors." }

Write-Host "Opening the ngrok tunnel..." -ForegroundColor Cyan
Start-Process -FilePath ngrok -ArgumentList "http", "8000"

$url = $null
for ($i = 0; $i -lt 40 -and -not $url; $i++) {
  Start-Sleep -Milliseconds 500
  try { $url = ((Invoke-RestMethod http://127.0.0.1:4040/api/tunnels).tunnels | Where-Object proto -eq "https").public_url } catch { }
}
if (-not $url) { throw "ngrok did not report a public URL. Check the ngrok window." }

Write-Host ""
Write-Host "  Off Script is live at:  $url" -ForegroundColor Green
Write-Host "  Share this link. Visitors may see an ngrok notice first: click 'Visit Site'." -ForegroundColor Green
Write-Host "  To stop sharing, close the ngrok and server windows." -ForegroundColor Yellow
