# 依次打包：扫描(全参数) / Celery Beat / Celery Worker / FastAPI(Uvicorn)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

& "$here\build_exe_scanner.ps1"
& "$here\build_exe_celery_beat.ps1"
& "$here\build_exe_celery_worker.ps1"
& "$here\build_exe_api.ps1"

Write-Host "全部完成。dist 下: QuantLoomScanner / QuantLoomCeleryBeat / QuantLoomCeleryWorker / QuantLoomApi"
