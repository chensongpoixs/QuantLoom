# QuantLoom — Celery Worker（threads 池，并发 2）
# 等价: celery -A quant_loom.tasks.celery_app worker -l info --pool=threads --concurrency=2

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot.Path

python -m pip install -q "pyinstaller>=6.0"

$configSrc = Join-Path $RepoRoot.Path "config"
$dataSpec = "${configSrc};config"

$args = @(
    "--name", "QuantLoomCeleryWorker",
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
python -m PyInstaller @args "scripts\run_celery_worker.py"

Write-Host "输出: $RepoRoot\dist\QuantLoomCeleryWorker\QuantLoomCeleryWorker.exe"
