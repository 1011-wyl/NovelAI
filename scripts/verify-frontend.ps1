# Unified verification order for Vue SPA + Python SPA asset tests.
# Does not touch the user database at data/novel_agent.db.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Web = Join-Path $Root "apps\web"

Write-Host "==> npm ci"
Set-Location $Web
npm ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> lint"
npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> type-check"
npm run type-check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> vitest"
npm run test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> build (required before Python SPA tests)"
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> playwright e2e (isolated temp database)"
npm run test:e2e
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location $Root
Write-Host "==> python unittest"
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "All verification steps passed."
