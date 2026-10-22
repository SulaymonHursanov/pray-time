# Сборка: dist\PrayTime\PrayTime.exe (PyInstaller) и dist\PrayTime-Setup-*.exe (Inno Setup)
# Запуск:  powershell -ExecutionPolicy Bypass -File build.ps1 [-Version 1.2.3]
# без -Version берётся версия из installer\PrayTime.iss
param([string]$Version)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".venv-build\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -3 -m venv .venv-build
    & $py -m pip install -q pyinstaller comtypes pystray pillow
}

# обёртка UI Automation для comtypes генерируется заранее, чтобы попасть в exe
& $py -c "import comtypes.client as c; c.GetModule('UIAutomationCore.dll')"
& $py installer\make_icon.py

& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name PrayTime `
    --icon installer\PrayTime.ico `
    --collect-submodules comtypes.gen `
    --hidden-import pystray._win32 `
    --distpath dist --workpath build `
    prayer_tray.py
if ($LASTEXITCODE) { throw "PyInstaller завершился с ошибкой" }

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Не найден Inno Setup 6 (ISCC.exe). Установите: https://jrsoftware.org/isdl.php" }

$isccArgs = @("installer\PrayTime.iss")
if ($Version) { $isccArgs = @("/DAppVersion=$Version") + $isccArgs }
& $iscc @isccArgs
if ($LASTEXITCODE) { throw "ISCC завершился с ошибкой" }
# копия без версии в названии — на неё ведёт ссылка «Скачать» в README (releases/latest/download/...)
$setup = Get-ChildItem dist\PrayTime-Setup-*.exe | Sort-Object LastWriteTime | Select-Object -Last 1
Copy-Item $setup.FullName dist\PrayTime-Setup.exe -Force
Get-ChildItem dist\PrayTime-Setup*.exe
