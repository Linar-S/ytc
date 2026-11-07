# One-command launcher for Windows / PowerShell.
# Usage: .\scripts\start.ps1 [-NoSeed]

param(
    [switch]$NoSeed
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker is not installed"
}
docker compose version | Out-Null

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Starting containers..."
docker compose up -d --build

Write-Host "Waiting for backend health..."
$deadline = (Get-Date).AddMinutes(4)
while ($true) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) { break }
    } catch {
        if ((Get-Date) -gt $deadline) {
            docker compose ps
            docker compose logs --tail=120 backend
            throw "backend did not become healthy in time"
        }
        Start-Sleep -Seconds 2
    }
}

Write-Host "Applying migrations..."
docker compose exec -T backend alembic upgrade head

if (-not $NoSeed) {
    Write-Host "Seeding demo data..."
    docker compose exec -T backend python scripts/seed_demo.py
}

Write-Host ""
Write-Host "Ready: http://localhost:8000"
Write-Host "Swagger: http://localhost:8000/docs"
Write-Host "MinIO console: http://localhost:9001"
Write-Host "Demo users:"
Write-Host "  admin@example.com / Admin12345!"
Write-Host "  moderator@example.com / Moderator12345!"
Write-Host "  user@example.com / User12345!"