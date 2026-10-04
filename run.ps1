$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$index = Join-Path $PSScriptRoot 'apps\web\dist\index.html'
if (-not (Test-Path $index)) {
    Write-Host '前端构建产物缺失：找不到 apps/web/dist/index.html'
    Write-Host '请先执行：'
    Write-Host '  cd apps/web'
    Write-Host '  npm ci'
    Write-Host '  npm run build'
    Write-Host '然后再运行本脚本或 python -m novel_agent serve'
    exit 1
}

python -m novel_agent serve
