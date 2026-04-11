$ErrorActionPreference = 'Stop'

Write-Host "Downloading build_it for Windows..." -ForegroundColor Cyan

$d="$env:USERPROFILE\.build_it\bin"
New-Item -ItemType Directory -Force -Path $d | Out-Null
Invoke-WebRequest -Uri "https://github.com/Dasero197/build_it/releases/latest/download/build_it-windows.exe" -OutFile "$d\build_it.exe"

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$d*") {
    [Environment]::SetEnvironmentVariable("Path", $userPath + ";$d", "User")
    Write-Host "Added $d to your user PATH variable." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ build_it installed successfully!" -ForegroundColor Green
Write-Host "Restart your terminal to use it, or run: `$env:Path += `";$d`"` in your current session." -ForegroundColor Yellow
Write-Host "Run 'build_it info' to get started."
