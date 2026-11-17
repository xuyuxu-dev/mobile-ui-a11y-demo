# 一条命令跑完：离线自测 -> 采集 -> 分析 -> 隐私自检
# 用法： powershell -ExecutionPolicy Bypass -File .\run_all.ps1 [-Serial SN]
param([string]$Serial = "")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
function Resolve-Python {
    foreach ($c in @($env:PYTHON, $env:DSH_PYTHON, "python3", "python")) {
        if (-not $c) { continue }
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        if (Test-Path $c) { return $c }
    }
    throw "找不到 Python 解释器：请把 python 加入 PATH，或设置环境变量 PYTHON 指向解释器"
}
$py = Resolve-Python
$out = Join-Path $root "data\lint.jsonl"

Write-Host "== 1/5 离线自测（无需手机）=="
& $py (Join-Path $root "tests\selftest.py")
if ($LASTEXITCODE -ne 0) { throw "selftest failed" }

if ($Serial) {
    Write-Host "== 2/5 采集（按 collectors\pages.json）=="
    & $py (Join-Path $root "collectors\collect_batch.py") --serial $Serial --fresh
} else {
    Write-Host "== 2/5 跳过采集（未提供 -Serial）=="
}

Write-Host "== 3/5 分析 =="
& $py (Join-Path $root "analyze\analyze.py") $out --outdir (Join-Path $root "data")

Write-Host "== 4/5 隐私自检 =="
& $py (Join-Path $root "tests\privacy_scan.py") $out

Write-Host "== 5/5 指标基线 =="
& $py (Join-Path $root "tests\baseline_check.py") $out

Write-Host ""
Write-Host "报告: $(Join-Path $root 'data\report.md')"