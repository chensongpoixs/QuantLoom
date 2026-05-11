# QuantLoom — 全链路扫描（入口 scripts/run_scanner.py，exe 支持与脚本相同的命令行参数）
#
# 若 exe 运行报 ModuleNotFoundError：在下方 $args 追加 "--hidden-import","模块名" 或 "--collect-all","包名"，查看 build\*\warn-*.txt

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot.Path

python -m pip install -q "pyinstaller>=6.0"

$configSrc = Join-Path $RepoRoot.Path "config"
$dataSpec = "${configSrc};config"

$args = @(
    "--name", "QuantLoomScanner",
    "--clean",
    "--noconfirm",
    "--console",
    "--onedir",
    "--noupx",
    "--paths", $RepoRoot.Path,
    "--paths", (Join-Path $RepoRoot.Path "scripts"),
    "--collect-submodules", "quant_loom",
    "--collect-all", "akshare",
    "--add-data", $dataSpec
)
python -m PyInstaller @args "scripts\run_scanner.py"

Write-Host "输出: $RepoRoot\dist\QuantLoomScanner\QuantLoomScanner.exe"
Write-Host "用法与 python scripts/run_scanner.py 相同，例如: QuantLoomScanner.exe --top 0 --dry-run"
