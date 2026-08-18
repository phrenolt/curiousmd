@echo off
setlocal
echo Building CuriousMD Windows Distribution with Bundled Python...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1])) -ArgumentList '%~dp0'"
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)
echo.
pause
goto :EOF

#POWERSHELL_START#
param($scriptDir)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $scriptDir '..\..'))
if (-not (Test-Path (Join-Path $projectRoot 'mdview.py'))) {
    throw "Could not find project root from $scriptDir"
}
$pyVersion = '3.12.3'
$pyZip = "python-$pyVersion-embed-amd64.zip"
$pyUrl = "https://www.python.org/ftp/python/$pyVersion/$pyZip"
$expectedSha = '38b265fc0612027a126ae54d2485101f041b61893e41ef4f421dee6ac618a99e'
$pyZipPath = Join-Path $projectRoot $pyZip

if (-not (Test-Path $pyZipPath)) {
    Write-Host "Downloading $pyZip..."
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyZipPath
}

Write-Host 'Verifying SHA256 checksum...'
$hash = (Get-FileHash $pyZipPath -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $expectedSha) {
    Write-Host "ERROR: SHA256 mismatch!" -ForegroundColor Red
    Write-Host "Expected: $expectedSha"
    Write-Host "Actual:   $hash"
    exit 1
}
Write-Host 'Checksum OK.'

$distName = 'CuriousMD_Windows.zip'
$distPath = Join-Path $projectRoot $distName
$stagingDir = Join-Path ([IO.Path]::GetTempPath()) ("CuriousMD_" + [guid]::NewGuid().ToString('N'))

try {
    New-Item -ItemType Directory -Path $stagingDir | Out-Null
    $pythonDir = Join-Path $stagingDir 'python'
    Write-Host 'Extracting bundled Python...'
    Expand-Archive -Path $pyZipPath -DestinationPath $pythonDir -Force

    $pyMajorMinor = (($pyVersion -split '\.')[0..1] -join '')
    $pthFile = Join-Path $pythonDir "python$pyMajorMinor._pth"
    if (-not (Test-Path $pthFile)) {
        throw "Bundled Python path file not found: $pthFile"
    }
    $pthEntries = @(Get-Content -Path $pthFile)
    if ($pthEntries -notcontains '..') {
        Set-Content -Path $pthFile -Value ($pthEntries + '..') -Encoding ASCII
    }

    foreach ($entry in @('mdview.py', 'domains', 'md_icon.png', 'README.md', 'LICENSE')) {
        Copy-Item -Path (Join-Path $projectRoot $entry) -Destination $stagingDir -Recurse
    }
    foreach ($script in @('install.bat', 'uninstall.bat', 'associate.bat', 'deassociate.bat')) {
        Copy-Item -Path (Join-Path $scriptDir $script) -Destination $stagingDir
    }

    Write-Host "Packaging $distName..."
    if (Test-Path $distPath) { Remove-Item -Force $distPath }
    Compress-Archive -Path (Join-Path $stagingDir '*') -DestinationPath $distPath -Force
} finally {
    if (Test-Path $stagingDir) { Remove-Item -Recurse -Force $stagingDir }
}

Write-Host "Done! The standalone Windows distribution is ready: $distPath" -ForegroundColor Green
