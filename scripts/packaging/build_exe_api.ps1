# QuantLoom — FastAPI（等价 uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090）

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot.Path

python -m pip install -q "pyinstaller>=6.0"

$configSrc = Join-Path $RepoRoot.Path "config"
$dataSpec = "${configSrc};config"

$args = @(
    "--name", "QuantLoomApi",
    "--clean",
    "--noconfirm",
    "--console",
    "--onedir",
    "--noupx",
    "--paths", $RepoRoot.Path,
    "--collect-submodules", "quant_loom",
    "--collect-all", "uvicorn",
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--add-data", $dataSpec
)
python -m PyInstaller @args "scripts\run_api.py"

Write-Host "输出: $RepoRoot\dist\QuantLoomApi\QuantLoomApi.exe"
Write-Host "监听 0.0.0.0:9090"
