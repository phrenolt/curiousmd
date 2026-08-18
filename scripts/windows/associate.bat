@echo off
setlocal
echo Associating file extensions for CuriousMD...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1])) -ArgumentList '%~dp0'"
if errorlevel 1 (
    echo Association failed.
    pause
    exit /b 1
)

echo.
pause
goto :EOF

#POWERSHELL_START#
param($scriptDir)
$scriptDir = $scriptDir.TrimEnd('\')
if (Test-Path (Join-Path $scriptDir 'mdview.py')) {
    $appDir = $scriptDir
} else {
    $appDir = [IO.Path]::GetFullPath((Join-Path $scriptDir '..\..'))
}
if (-not (Test-Path (Join-Path $appDir 'mdview.py'))) {
    throw "Could not find mdview.py from $scriptDir"
}
$mdviewScript = Join-Path $appDir 'mdview.py'

$bundledPython = Join-Path $appDir 'python\python.exe'
if (Test-Path $bundledPython) { $pythonExe = $bundledPython } else { $pythonExe = 'python.exe' }

New-Item -Path 'HKCU:\Software\Classes\.md' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\.md' -Name '(default)' -Value 'CuriousMD.Markdown' -Force | Out-Null
New-Item -Path 'HKCU:\Software\Classes\.markdown' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\.markdown' -Name '(default)' -Value 'CuriousMD.Markdown' -Force | Out-Null
New-Item -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Name '(default)' -Value 'Markdown Document' -Force | Out-Null
$cmdPath = 'HKCU:\Software\Classes\CuriousMD.Markdown\shell\open\command'
New-Item -Path $cmdPath -Force | Out-Null
New-ItemProperty -Path $cmdPath -Name '(default)' -Value "`"`"$pythonExe`"`" `"$mdviewScript`" `"%1`"" -Force | Out-Null

Write-Host "Successfully associated .md and .markdown files with CuriousMD."
