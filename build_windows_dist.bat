@echo off
setlocal
echo Building CuriousMD Windows Distribution with Bundled Python...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1]))"
if %errorlevel% neq 0 (
    echo Build failed.
)
echo.
pause
goto :EOF

#POWERSHELL_START#
$ErrorActionPreference = 'Stop'
$pyVersion = '3.12.3'
$pyZip = "python-$pyVersion-embed-amd64.zip"
$pyUrl = "https://www.python.org/ftp/python/$pyVersion/$pyZip"
$expectedSha = '38b265fc0612027a126ae54d2485101f041b61893e41ef4f421dee6ac618a99e'

if (-not (Test-Path $pyZip)) {
    Write-Host "Downloading $pyZip..."
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip
}

Write-Host 'Verifying SHA256 checksum...'
$hash = (Get-FileHash $pyZip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $expectedSha) {
    Write-Host "ERROR: SHA256 mismatch!" -ForegroundColor Red
    Write-Host "Expected: $expectedSha"
    Write-Host "Actual:   $hash"
    exit 1
}
Write-Host 'Checksum OK.'

Write-Host 'Extracting Python to python/...'
if (Test-Path 'python') { Remove-Item -Recurse -Force 'python' }
Expand-Archive -Path $pyZip -DestinationPath 'python' -Force

$distName = 'CuriousMD_Windows.zip'
Write-Host "Packaging $distName..."
if (Test-Path $distName) { Remove-Item -Force $distName }
$files = @('mdview.py', 'domains', 'python', 'install.bat', 'uninstall.bat', 'associate.bat', 'deassociate.bat', 'md_icon.png', 'README.md', 'LICENSE')
Compress-Archive -Path $files -DestinationPath $distName -Force

Write-Host "Done! The standalone Windows distribution is ready: $distName" -ForegroundColor Green
