@echo off
setlocal
echo Uninstalling CuriousMD from Windows...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1]))"

echo.
echo CuriousMD uninstallation complete!
pause
goto :EOF

#POWERSHELL_START#
$binDir = Join-Path $env:LOCALAPPDATA 'CuriousMD\bin'
if (Test-Path $binDir) { 
    Remove-Item -Recurse -Force $binDir
    Write-Host "Removed bin directory." 
}

$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -like "*$binDir*") {
    $newPath = ($userPath -split ';' | Where-Object { $_ -ne $binDir }) -join ';'
    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
    Write-Host "Removed $binDir from User PATH."
}

$startMenu = [Environment]::GetFolderPath('Programs')
$shortcutPath = Join-Path $startMenu 'CuriousMD.lnk'
if (Test-Path $shortcutPath) { 
    Remove-Item -Force $shortcutPath
    Write-Host "Removed Start Menu shortcut." 
}

Remove-Item -Path 'HKCU:\Software\Classes\.md' -Force -Recurse -ErrorAction Ignore
Remove-Item -Path 'HKCU:\Software\Classes\.markdown' -Force -Recurse -ErrorAction Ignore
Remove-Item -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Force -Recurse -ErrorAction Ignore
Write-Host "Removed registry file associations."
