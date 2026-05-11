# QuantLoom — Celery Beat（等价 celery -A quant_loom.tasks.celery_app beat -l info）
# 用法：.\scripts\packaging\build_exe_celery_beat.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot.Path

python -m pip install -q "pyinstaller>=6.0"

$configSrc = Join-Path $RepoRoot.Path "config"
$dataSpec = "${configSrc};config"

$args = @(
    "--name", "QuantLoomCeleryBeat",
    "--clean",
    "--noconfirm",
    "--console",
    "--onedir",
    "--noupx",
    "--paths", $RepoRoot.Path,
    "--collect-submodules", "quant_loom",
    "--collect-all", "celery",
    "--collect-all", "kombu",
    "--collect-all", "billiard",
    "--collect-all", "akshare",
    "--hidden-import", "celery.concurrency.thread",
    "--add-data", $dataSpec
)
python -m PyInstaller @args "scripts\run_celery_beat.py"

Write-Host "输出: $RepoRoot\dist\QuantLoomCeleryBeat\QuantLoomCeleryBeat.exe"
