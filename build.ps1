# 建置 Gamersive-Translate：pyside6-deploy（Nuitka standalone）輸出到 build\，
# 完成後把 llama.cpp-cuda\ 與 assets\ 複製到建置資料夾（exe 所在資料夾）。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force build | Out-Null
& .\.venv\Scripts\pyside6-deploy -c pysidedeploy.spec -f
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$dist = Get-ChildItem build -Directory -Filter *.dist | Select-Object -First 1
if (-not $dist) { throw "找不到建置資料夾 build\*.dist" }
Copy-Item llama.cpp-cuda -Destination $dist.FullName -Recurse -Force
Copy-Item assets -Destination $dist.FullName -Recurse -Force
Write-Host "完成：$($dist.FullName)"
