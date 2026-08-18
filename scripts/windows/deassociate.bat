@echo off
setlocal
echo Removing file associations for CuriousMD...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#POWERSHELL_START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1]))"

echo.
pause
goto :EOF

#POWERSHELL_START#
Remove-Item -Path 'HKCU:\Software\Classes\.md' -Force -Recurse -ErrorAction Ignore
Remove-Item -Path 'HKCU:\Software\Classes\.markdown' -Force -Recurse -ErrorAction Ignore
Remove-Item -Path 'HKCU:\Software\Classes\CuriousMD.Markdown' -Force -Recurse -ErrorAction Ignore

Write-Host "Successfully deassociated .md and .markdown files from CuriousMD."
