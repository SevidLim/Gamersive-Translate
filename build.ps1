# 建置 Gamersive-Translate：pyside6-deploy（Nuitka standalone）輸出到 build\，
# 完成後把 llama.cpp-cuda\ 與 assets\ 複製到建置資料夾（exe 所在資料夾），再逐項檢查建置結果。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Get-Process -Name Gamersive-Translate -ErrorAction SilentlyContinue) {
    Write-Host "請先從托盤結束 Gamersive-Translate"
    exit 1
}
$out = "build\Gamersive-Translate.dist"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }   # pyside6-deploy 以 copytree(dirs_exist_ok=True) 複製，舊檔會留下
New-Item -ItemType Directory -Force build | Out-Null
& .\.venv\Scripts\pyside6-deploy -c pysidedeploy.spec -f
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$dist = Get-ChildItem build -Directory -Filter *.dist | Select-Object -First 1
if (-not $dist) { throw "找不到建置資料夾 build\*.dist" }
foreach ($name in "llama.cpp-cuda", "assets") {
    $target = Join-Path $dist.FullName $name
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }   # 目的地已有同名資料夾時先刪除
    Copy-Item $name -Destination $dist.FullName -Recurse -Force
}
$required = @(
    "Gamersive-Translate.exe",
    "llama.cpp-cuda\llama-server.exe",
    "assets\icon.png",
    "assets\icon.ico",
    "rapidocr\config.yaml",
    "rapidocr\default_models.yaml",
    "rapidocr\models\PP-OCRv6_det_small.onnx",
    "rapidocr\models\PP-OCRv6_rec_small.onnx",
    "rapidocr\models\ch_PP-OCRv5_det_mobile.onnx",
    "rapidocr\models\ch_PP-OCRv5_rec_mobile.onnx",
    "rapidocr\models\ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    "uroman\data"
)
$missing = 0
foreach ($item in $required) {
    if (Test-Path (Join-Path $dist.FullName $item)) { Write-Host "OK    $item" }
    else { Write-Host "缺少  $item"; $missing++ }
}
if ($missing -gt 0) {
    Write-Host "缺少 $missing 項"
    exit 1
}
Write-Host "全部檢查通過：$($dist.FullName)"
