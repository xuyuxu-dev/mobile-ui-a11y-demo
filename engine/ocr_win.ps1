# Windows 自带 OCR（Windows.Media.Ocr），输出 JSON：每个词 + 包围盒
# 用法： powershell -File ocr_win.ps1 -Path <png> [-Json]
param([string]$Path, [switch]$Json)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType=WindowsRuntime]

$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($op, $type) {
    $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $t.Wait(-1) | Out-Null
    $t.Result
}

try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync(0)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) { Write-Output '{"error":"no-engine"}'; exit 2 }
    $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    if ($Json) {
        $words = @()
        foreach ($line in $res.Lines) {
            foreach ($w in $line.Words) {
                $r = $w.BoundingRect
                $words += [pscustomobject]@{
                    text = $w.Text
                    x = [int]$r.X; y = [int]$r.Y
                    w = [int]$r.Width; h = [int]$r.Height
                }
            }
        }
        $obj = [pscustomobject]@{ language = $engine.RecognizerLanguage.LanguageTag; words = $words }
        Write-Output ($obj | ConvertTo-Json -Depth 4 -Compress)
    } else {
        Write-Output "---- 识别结果 ----"
        Write-Output $res.Text
    }
} catch {
    Write-Output ('{"error":"' + $_.Exception.Message.Replace('"','') + '"}')
    exit 1
}