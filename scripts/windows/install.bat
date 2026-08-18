@echo off
setlocal
echo Installing CuriousMD for Windows...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1])) -ArgumentList '%~dp0'"
if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
)

echo.
echo CuriousMD installation complete!
echo You may need to restart your terminal for the 'md' command to become available.
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
$binDir = Join-Path $env:LOCALAPPDATA 'CuriousMD\bin'

if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Force -Path $binDir | Out-Null }

$bundledPython = Join-Path $appDir 'python\python.exe'
if (Test-Path $bundledPython) { $pythonExe = $bundledPython } else { $pythonExe = 'python.exe' }

Set-Content -Path (Join-Path $binDir 'md.bat') -Value "@`"$pythonExe`" `"$mdviewScript`" %*" -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -notlike "*$binDir*") {
    if ($userPath -and $userPath -notmatch ';$') { $userPath += ';' }
    [Environment]::SetEnvironmentVariable('PATH', $userPath + $binDir, 'User')
    Write-Host "Added $binDir to User PATH."
} else { 
    Write-Host "Command 'md' already in PATH." 
}

$startMenu = [Environment]::GetFolderPath('Programs')
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut((Join-Path $startMenu 'CuriousMD.lnk'))
$shortcut.TargetPath = $pythonExe
$shortcut.Arguments = "`"$mdviewScript`""
$shortcut.IconLocation = Join-Path $appDir 'md_icon.png'
$shortcut.Save()
Write-Host 'Created Start Menu shortcut.'

New-Item -Path 'HKCU:\Software\Classes\.md' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\.md' -Name '(default)' -Value 'CuriousMD.Markdown' -Force | Out-Null
New-Item -Path 'HKCU:\Software\Classes\.markdown' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\.markdown' -Name '(default)' -Value 'CuriousMD.Markdown' -Force | Out-Null
New-Item -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Name '(default)' -Value 'Markdown Document' -Force | Out-Null
$cmdPath = 'HKCU:\Software\Classes\CuriousMD.Markdown\shell\open\command'
New-Item -Path $cmdPath -Force | Out-Null
New-ItemProperty -Path $cmdPath -Name '(default)' -Value "`"`"$pythonExe`"`" `"$mdviewScript`" `"%1`"" -Force | Out-Null
Write-Host 'Registered .md file associations.'
