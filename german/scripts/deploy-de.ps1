#Requires -Version 5.1
<#
deploy-de.ps1 - hand-deploy the German-capable Qingjian build over the 0.1.4 install.

What it does, in order:
  1. backs up the four 0.1.4 binaries (+ icon) into backup-0.1.4-<timestamp>\
  2. stops qingjian-server.exe
  3. installs data\generated\glossary-de.qj from ..\..\Roaming\Qingjian\custom\glossary-de-hd.qj
  4. copies the freshly built qingjian-server.exe / qingjian-settings.exe / qingjian_tsf-0.1.5{,-x86}.dll
  5. registers the new TSF DLLs with regsvr32 and repairs the CLSID InprocServer32
     entries (regsvr32 exit codes are unreliable - verify by reading the registry)
  6. sets [general] learning_language = "de" in config.toml
  7. starts qingjian-server.exe again

Run with -DryRun to only print what would happen.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$RegisterTsf,
    [string]$InstallDir = 'D:\application\Qingjian',
    [string]$BuildDir   = 'C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926\target\release',
    [string]$ConfigPath = "$env:APPDATA\Qingjian\config.toml",
    [string]$GermanQj   = "$env:APPDATA\Qingjian\custom\glossary-de-hd.qj",
    [string]$WorkDir    = 'E:\codemain\qingjian-de'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Version   = '0.1.5'
$Clsid     = '{4FDCA82D-E923-49BF-9E75-BB906B93B8BB}'
$BackupDir = Join-Path $WorkDir ("backup-0.1.4-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Step($text) { Write-Host ""; Write-Host "=== $text" -ForegroundColor Cyan }
function Say($text)  { Write-Host "    $text" }
function Run($desc, [scriptblock]$action) {
    if ($DryRun) { Say "[dry-run] $desc" } else { Say $desc; & $action }
}

# ---------------------------------------------------------------- 0. sanity
Step 'preflight'
$serverSrc   = Join-Path $BuildDir 'qingjian-server.exe'
$settingsSrc = Join-Path $BuildDir 'qingjian-settings.exe'
$tsfSrc      = Join-Path $BuildDir 'qingjian_tsf.dll'
$tsfSrc32    = Join-Path $BuildDir '..\i686-pc-windows-msvc\release\qingjian_tsf.dll'
$expected = @($serverSrc, $settingsSrc, $tsfSrc, $tsfSrc32, $GermanQj, (Join-Path $InstallDir 'qingjian-server.exe'))
foreach ($path in $expected) {
    $full = [IO.Path]::GetFullPath($path)
    if (-not (Test-Path -LiteralPath $full)) { throw "missing: $full" }
    $len = (Get-Item -LiteralPath $full).Length
    Say ("ok  {0,12:N0} B  {1}" -f $len, $full)
}

# ---------------------------------------------------------------- 1. backup
Step 'backup 0.1.4 binaries'
Run "create $BackupDir" { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }
$backupList = @(
    'qingjian-server.exe',
    'qingjian-settings.exe',
    'qingjian_tsf-0.1.4.dll',
    'qingjian_tsf-0.1.4-x86.dll',
    'qingjian.ico'
)
foreach ($name in $backupList) {
    $from = Join-Path $InstallDir $name
    if (-not (Test-Path -LiteralPath $from)) { Say "skip (absent) $name"; continue }
    Run "copy $name -> backup" { Copy-Item -LiteralPath $from -Destination (Join-Path $BackupDir $name) -Force }
}

# ---------------------------------------------------------------- 2. stop server
Step 'stop qingjian-server'
$running = Get-Process -Name 'qingjian-server' -ErrorAction SilentlyContinue
if ($running) {
    foreach ($p in $running) {
        Say ("pid {0} started {1}" -f $p.Id, $p.StartTime)
        Run "stop pid $($p.Id)" { Stop-Process -Id $p.Id -Force; $p.WaitForExit(10000) | Out-Null }
    }
} else { Say 'not running' }
$settings = Get-Process -Name 'qingjian-settings' -ErrorAction SilentlyContinue
if ($settings) { foreach ($p in $settings) { Run "stop settings pid $($p.Id)" { Stop-Process -Id $p.Id -Force } } }

# ---------------------------------------------------------------- 3. glossary
Step 'install glossary-de.qj'
$glossaryDst = Join-Path $InstallDir 'data\generated\glossary-de.qj'
Run "copy $(Split-Path -Leaf $GermanQj) -> $glossaryDst" { Copy-Item -LiteralPath $GermanQj -Destination $glossaryDst -Force }

# ---------------------------------------------------------------- 4. binaries
Step 'install binaries'
Run "qingjian-server.exe"   { Copy-Item -LiteralPath $serverSrc   -Destination (Join-Path $InstallDir 'qingjian-server.exe')   -Force }
Run "qingjian-settings.exe" { Copy-Item -LiteralPath $settingsSrc -Destination (Join-Path $InstallDir 'qingjian-settings.exe') -Force }
$tsfDst   = Join-Path $InstallDir "qingjian_tsf-$Version.dll"
$tsfDst32 = Join-Path $InstallDir "qingjian_tsf-$Version-x86.dll"
Run "qingjian_tsf-$Version.dll"     { Copy-Item -LiteralPath $tsfSrc   -Destination $tsfDst   -Force }
Run "qingjian_tsf-$Version-x86.dll" { Copy-Item -LiteralPath ([IO.Path]::GetFullPath($tsfSrc32)) -Destination $tsfDst32 -Force }

# ---------------------------------------------------------------- 5. register TSF
Step 'register TSF DLLs'
# The TSF shim is language-agnostic (no Language / gloss / learning_language use anywhere in
# apps\windows\tsf\src) - the Server produces the gloss text and the TSF only draws what it
# receives - so the installed 0.1.4 TSF DLL keeps working with the new Server.  Registering the
# new DLL needs an elevated process (HKLM\SOFTWARE\Classes\CLSID\...), so by default the DLLs are
# merely copied and the registration is left alone.  -RegisterTsf writes a per-user override
# under HKCU\Software\Classes, which COM prefers and which needs no admin rights.
if ($RegisterTsf) {
    $pairs = @(
        @{ Dll = $tsfDst;   Regsvr = 'regsvr32.exe';                     View = 'HKLM' },
        @{ Dll = $tsfDst32; Regsvr = "$env:WINDIR\SysWOW64\regsvr32.exe"; View = 'HKLM' }
    )
    foreach ($p in $pairs) {
        if ($DryRun) { Say "[dry-run] would register $($p.Dll)"; continue }
        try {
            $userKey = "HKCU:\Software\Classes\CLSID\$Clsid\InprocServer32"
            if (-not (Test-Path -LiteralPath $userKey)) { New-Item -Path $userKey -Force | Out-Null }
            Set-ItemProperty -LiteralPath $userKey -Name '(default)' -Value $p.Dll
            Set-ItemProperty -LiteralPath $userKey -Name 'ThreadingModel' -Value 'Apartment'
            Say "per-user CLSID -> $($p.Dll)"
        } catch { Say "per-user registration failed: $($_.Exception.Message)" }
    }
    if (-not $DryRun) {
        foreach ($probe in @("HKLM:\SOFTWARE\Classes\CLSID\$Clsid\InprocServer32",
                             "HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID\$Clsid\InprocServer32")) {
            $current = (Get-ItemProperty -LiteralPath $probe -ErrorAction SilentlyContinue).'(default)'
            Say "machine registration (unchanged): $probe -> $current"
        }
    }
} else {
    Say 'skipped - the installed 0.1.4 TSF DLL stays registered (German comes from the Server)'
    Say "new DLLs are on disk if a later elevated run wants them: $tsfDst / $tsfDst32"
}

# ---------------------------------------------------------------- 6. config
Step 'config.toml learning_language = "de"'
if (-not $DryRun) {
    $text = Get-Content -LiteralPath $ConfigPath -Raw
    if ($text -match '(?m)^\s*learning_language\s*=\s*"de"') {
        Say 'already "de"'
    } else {
        $new = [regex]::Replace($text, '(?m)^(\s*learning_language\s*=\s*)"[^"]*"', '${1}"de"')
        if ($new -eq $text) { throw "learning_language line not found in $ConfigPath" }
        Copy-Item -LiteralPath $ConfigPath -Destination "$ConfigPath.bak-de" -Force
        # Write without a BOM unless the original had one (PowerShell 5.1's -Encoding UTF8 adds a BOM,
        # which a strict TOML parser may reject).
        $bytes = [IO.File]::ReadAllBytes($ConfigPath)
        $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
        [IO.File]::WriteAllText($ConfigPath, $new, (New-Object Text.UTF8Encoding($hasBom)))
        Say "updated (backup: $ConfigPath.bak-de, bom: $hasBom)"
    }
} else { Say '[dry-run] set learning_language = "de"' }

# ---------------------------------------------------------------- 7. start server
Step 'start qingjian-server'
$serverExe = Join-Path $InstallDir 'qingjian-server.exe'
Run "start $serverExe" { Start-Process -FilePath $serverExe -WorkingDirectory $InstallDir | Out-Null }
Start-Sleep -Seconds 3

Step 'result'
Get-Process -Name 'qingjian-server' -ErrorAction SilentlyContinue | Select-Object Id, StartTime, Path | Format-List
$logDir = Join-Path $env:LOCALAPPDATA 'Qingjian\logs'
$log = Get-ChildItem -LiteralPath $logDir -Filter 'server.*.log' -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) {
    Say "log: $($log.FullName)"
    Get-Content -LiteralPath $log.FullName -Tail 25 | Where-Object { $_ -match 'glossary|language|就绪|error|ERROR' }
} else { Say "no server log under $logDir" }
Say "backup dir: $BackupDir"
