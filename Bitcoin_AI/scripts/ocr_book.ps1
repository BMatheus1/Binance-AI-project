param([Parameter(Mandatory=$true)][string]$Pdf,[Parameter(Mandatory=$true)][string]$Output,[int]$First=1,[int]$Last)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await-WinRT($Operation, [Type]$ResultType) {
    $task = $asTask.MakeGenericMethod($ResultType).Invoke($null,@($Operation))
    $task.Wait()
    return $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw 'Nenhum idioma OCR instalado' }
$outDir = [System.IO.Path]::GetFullPath($Output)
[System.IO.Directory]::CreateDirectory($outDir) | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
for ($page=$First; $page -le $Last; $page++) {
    $stem = Join-Path $outDir ('{0:D4}' -f $page)
    if (Test-Path -LiteralPath ($stem+'.ocr.json')) { continue }
    & pdftoppm -f $page -l $page -singlefile -scale-to 2400 -png $Pdf $stem
    if ($LASTEXITCODE -ne 0) { throw "Falha ao renderizar pagina $page" }
    $file = Await-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($stem+'.png')) ([Windows.Storage.StorageFile])
    $stream = Await-WinRT ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = @($result.Lines | ForEach-Object { $_.Text })
    [System.IO.File]::WriteAllText($stem+'.ocr.txt',($lines -join "`n"),$utf8)
    $record = @{pdf_page=$page; engine='Windows.Media.Ocr'; language=$engine.RecognizerLanguage.LanguageTag; chars=($lines -join "`n").Length; lines=$lines; semantic_review=$false; note='OCR local; erros em inglês, fórmulas, ordem e gráficos exigem conferência visual'}
    [System.IO.File]::WriteAllText($stem+'.ocr.json',($record | ConvertTo-Json -Depth 5),$utf8)
    $bitmap.Dispose()
    $stream.Dispose()
    if ($page % 10 -eq 0 -or $page -eq $First -or $page -eq $Last) { Write-Output "OCR $page / $Last, chars $($record.chars)" }
}
