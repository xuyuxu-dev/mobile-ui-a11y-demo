# 两包离线校验（不需要真机）：lint 的 4 道闸门 + engine 的 1 道
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

$steps = @(
    @{ name = "lint/selftest";        args = @("$root\lint\tests\selftest.py") },
    @{ name = "lint/schema";          args = @("$root\lint\tests\schema_check.py", "$root\lint\data\lint.jsonl") },
    @{ name = "lint/privacy";         args = @("$root\lint\tests\privacy_scan.py", "$root\lint\data\lint.jsonl") },
    @{ name = "lint/baseline";        args = @("$root\lint\tests\baseline_check.py", "$root\lint\data\lint.jsonl") },
    @{ name = "engine/selftest";      args = @("$root\engine\tests\selftest_engine.py") },
    @{ name = "engine/cli-contract";  args = @("$root\engine\tests\test_cli.py") },
    @{ name = "lint/input-contract";  args = @("$root\lint\tests\test_inputs.py") },
    @{ name = "engine/overlay";       args = @("$root\engine\tests\test_overlay.py") },
    @{ name = "lint/lock";            args = @("$root\lint\tests\test_lock.py") },
    @{ name = "engine/pixel-hash";    args = @("$root\engine\tests\test_screen_hash.py") }
)

$fail = 0
foreach ($s in $steps) {
    Write-Host ("-- " + $s.name)
    & $py @($s.args)
    if ($LASTEXITCODE -ne 0) { $fail++; Write-Host ("   FAILED: " + $s.name) }
}
Write-Host ""
Write-Host ("结果: " + ($steps.Count - $fail) + "/" + $steps.Count + " 通过")
exit $fail