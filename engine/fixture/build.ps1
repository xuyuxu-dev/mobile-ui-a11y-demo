# 构建可交互 Canvas 夹具 APK（demo 专用）
# 用法： powershell -ExecutionPolicy Bypass -File .\build.ps1 [-Sdk <android sdk 路径>]
param([string]$Sdk = "")

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Sdk) {
    # SDK 只用于构建期；按环境变量/常见位置自动找，找不到就要求显式传 -Sdk
    foreach ($c in @($env:ANDROID_SDK_ROOT, $env:ANDROID_HOME,
                     "$env:LOCALAPPDATA\Android\Sdk",
                     "C:\Android\Sdk", "C:\Program Files\Android\Sdk")) {
        if ($c -and (Test-Path (Join-Path $c "platforms\android-29\android.jar"))) { $Sdk = $c; break }
    }
}
$Sdk = (Resolve-Path $Sdk -ErrorAction SilentlyContinue)
if (-not $Sdk) { throw "找不到 Android SDK：请用 -Sdk 指定（需要 build-tools 与 platforms/android-29）" }
$bt   = Join-Path $Sdk "build-tools\34.0.0"
$plat = Join-Path $Sdk "platforms\android-29\android.jar"
if (-not (Test-Path $plat)) { throw "缺少 $plat" }

$out = Join-Path $root "out"
$res = Join-Path $root "res"
$src = Join-Path $root "src"
$man = Join-Path $root "AndroidManifest.xml"

function Find-Jdk {
    $cands = @()
    if ($env:JAVA_HOME) { $cands += $env:JAVA_HOME }
    $cands += "C:\Program Files\Android\openjdk\jdk-21.0.8"
    foreach ($d in (Get-ChildItem "C:\Program Files\Android\openjdk" -Directory -ErrorAction SilentlyContinue)) { $cands += $d.FullName }
    foreach ($d in (Get-ChildItem "$env:USERPROFILE\Apps" -Directory -ErrorAction SilentlyContinue)) { $cands += $d.FullName }
    foreach ($d in (Get-ChildItem "$env:USERPROFILE\.jdks" -Directory -ErrorAction SilentlyContinue)) { $cands += $d.FullName }
    foreach ($c in $cands) {
        if (-not $c) { continue }
        if (Test-Path (Join-Path $c "bin\javac.exe")) { return $c }
        $sub = Join-Path $c "jbr"
        if (Test-Path (Join-Path $sub "bin\javac.exe")) { return $sub }
    }
    return $null
}
$jdk = Find-Jdk
if (-not $jdk) { throw "找不到 JDK" }
$env:JAVA_HOME = $jdk
Write-Host ("[jdk] " + $jdk)

function Run($exe, $argv, $label) {
    $o = & $exe @argv 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "---- $label FAILED ----"
        $o | Select-Object -Last 15 | ForEach-Object { Write-Host $_ }
        throw "$label failed"
    }
    return $o
}

Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $out, "$out\classes", "$out\gen" | Out-Null

Run "$bt\aapt2.exe" @("compile", "--dir", $res, "-o", "$out\res.zip") "aapt2 compile"
Run "$bt\aapt2.exe" @("link", "-o", "$out\base.apk", "-I", $plat, "--manifest", $man, "--java", "$out\gen", "$out\res.zip") "aapt2 link"

$javaFiles = @(Get-ChildItem -Path $src, "$out\gen" -Recurse -Filter *.java | ForEach-Object { $_.FullName })
Run (Join-Path $env:JAVA_HOME "bin\javac.exe") (@("-source","8","-target","8","-encoding","UTF-8","-classpath",$plat,"-d","$out\classes") + $javaFiles) "javac"

$classes = @(Get-ChildItem "$out\classes" -Recurse -Filter *.class | ForEach-Object { $_.FullName })
Run "$bt\d8.bat" (@("--lib",$plat,"--min-api","24","--output",$out) + $classes) "d8"
if (-not (Test-Path "$out\classes.dex")) { throw "d8 没有产出 classes.dex" }

# 注入 dex：不用 jar.exe（换 JDK 后它可能不存在，且失败是静默的）
Copy-Item "$out\base.apk" "$out\unsigned.apk" -Force
Add-Type -AssemblyName System.IO.Compression | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null
$zip = [System.IO.Compression.ZipFile]::Open("$out\unsigned.apk", "Update")
try {
    $entry = $zip.CreateEntry("classes.dex", [System.IO.Compression.CompressionLevel]::Optimal)
    $es = $entry.Open()
    $bytes = [System.IO.File]::ReadAllBytes("$out\classes.dex")
    $es.Write($bytes, 0, $bytes.Length)
    $es.Close()
} finally { $zip.Dispose() }

$ks = Join-Path $root "fixture.jks"
if (-not (Test-Path $ks)) {
    Run (Join-Path $env:JAVA_HOME "bin\keytool.exe") @("-genkeypair","-keystore",$ks,"-alias","fixture","-keyalg","RSA",
        "-keysize","2048","-validity","3650","-storepass","canvasdemo","-keypass","canvasdemo",
        "-dname","CN=Canvas Fixture, OU=Demo, O=Demo, L=NA, S=NA, C=CN") "keytool"
}

Run "$bt\zipalign.exe" @("-f","4","$out\unsigned.apk","$out\aligned.apk") "zipalign"
Run "$bt\apksigner.bat" @("sign","--ks",$ks,"--ks-pass","pass:canvasdemo","--key-pass","pass:canvasdemo",
    "--out","$out\canvas-fixture.apk","$out\aligned.apk") "apksigner"

$apk = Get-Item "$out\canvas-fixture.apk"
$zipc = [System.IO.Compression.ZipFile]::OpenRead($apk.FullName)
try { $dex = $zipc.Entries | Where-Object { $_.FullName -eq "classes.dex" } | Select-Object -First 1 } finally { $zipc.Dispose() }
if (-not $dex) { throw "POSTCHECK 失败：APK 里没有 classes.dex" }
Write-Host ("BUILD OK: {0}  ({1} KB, dex {2} 字节)" -f $apk.FullName, [math]::Round($apk.Length/1KB), $dex.Length)