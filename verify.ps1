# 两包离线校验（不需要真机）：lint 的 4 道闸门 + engine 的 1 道
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = $env:DSH_PYTHON
if (-not $py -or -not (Test-Path $py)) { $py = "python" }

$steps = @(
    @{ name = "lint/selftest";        args = @("$root\lint\tests\selftest.py") },
    @{ name = "lint/schema";          args = @("$root\lint\tests\schema_check.py", "$root\lint\data\lint.jsonl") },
    @{ name = "lint/privacy";         args = @("$root\lint\tests\privacy_scan.py", "$root\lint\data\lint.jsonl") },
    @{ name = "lint/baseline";        args = @("$root\lint\tests\baseline_check.py", "$root\lint\data\lint.jsonl") },
    @{ name = "engine/selftest";      args = @("$root\engine\tests\selftest_engine.py") }
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