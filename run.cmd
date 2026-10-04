@echo off
cd /d "%~dp0"
if not exist "apps\web\dist\index.html" (
  echo 前端构建产物缺失：找不到 apps/web/dist/index.html
  echo 请先执行：
  echo   cd apps/web
  echo   npm ci
  echo   npm run build
  echo 然后再运行本脚本或 python -m novel_agent serve
  exit /b 1
)
python -m novel_agent serve
