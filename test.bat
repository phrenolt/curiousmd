@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content '%~f0' -Raw) -split '#START#', 2; Invoke-Command -ScriptBlock ([scriptblock]::Create($s[1])) -ArgumentList '%~dp0'"
goto :EOF
#START#
param($dir)
Write-Host "Directory is $dir"
