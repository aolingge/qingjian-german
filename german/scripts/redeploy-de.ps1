# 一条命令把「德语译文」补丁装回去（官方更新覆盖了二进制、或换了机器时用）。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File E:\codemain\qingjian-de\redeploy-de.ps1
#   ... -File redeploy-de.ps1 -Kit D:\somewhere\qingjian-de-kit -Install D:\application\Qingjian
#
# 做四件事：
#   1. 拿出补丁二进制（套件 bin\ 优先，没有就用同目录下现成的 qingjian-server.exe / qingjian-settings.exe）
#   2. 停 Server（输入法的宿主进程会自动把它拉起来，所以是「杀-立刻复制」的循环，最多重试 12 次）
#   3. 换 data\generated\glossary-de.qj（.qj 是 mmap 打开的，Server 一活着就换不动：ERROR_USER_MAPPED_FILE）
#   4. 把 config.toml 的 learning_language 改成 "de"，起 Server，最后跑 verify-de.ps1
param(
    [string]$Kit     = 'E:\codemain\qingjian-de\dist\qingjian-de-kit',
    [string]$Install = 'D:\application\Qingjian',
    [string]$Tools   = 'E:\codemain\qingjian-de',
    [bool]$ChineseFirst = $true,
    [switch]$NoStart,
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $Tools "backups\$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

function Kill-Server {
    $procs = @(Get-Process qingjian-server -ErrorAction SilentlyContinue)
    if ($procs.Count -gt 0) { $procs | Stop-Process -Force -ErrorAction SilentlyContinue }
    return $procs.Count
}
# Server 一停，输入法宿主进程会再拉一个起来并 mmap 住 .qj / .exe，所以每轮先杀再试。
function Copy-Live($from, $to, $max = 12) {
    if (-not (Test-Path -LiteralPath $from)) { throw "源文件不存在：$from" }
    for ($i = 1; $i -le $max; $i++) {
        Kill-Server | Out-Null
        Start-Sleep -Milliseconds 150
        try {
            Copy-Item -LiteralPath $from -Destination $to -Force -ErrorAction Stop
            return $i
        } catch {
            if ($i -eq $max) { throw }
            Start-Sleep -Milliseconds 600
        }
    }
}

Write-Output ''
Write-Output "青简德语补丁重装  套件 = $Kit  安装目录 = $Install"

# 1. 找输入
$serverSrc = Join-Path $Kit 'bin\qingjian-server.exe'
$settingsSrc = Join-Path $Kit 'bin\qingjian-settings.exe'
$qjSrc = Join-Path $Kit 'glossary\glossary-de.qj'
if (-not (Test-Path -LiteralPath $serverSrc)) {
    $alt = Join-Path $Tools 'qingjian-server.exe'
    if (Test-Path -LiteralPath $alt) { Write-Output "  [note] 套件里没有 Server，用 $alt"; $serverSrc = $alt }
    else { throw "既没有 $serverSrc，也没有 $alt —— 先跑 pack-de-kit.ps1 或把补丁二进制放回来" }
}
if (-not (Test-Path -LiteralPath $settingsSrc)) {
    Write-Output '  [note] 套件里没有设置程序，跳过（设置程序只影响「德语」下拉项，不影响候选译文）'
    $settingsSrc = $null
}
if (-not (Test-Path -LiteralPath $qjSrc)) {
    $alt = Join-Path $Tools 'de-glossary\out\glossary-de.qj'
    if (Test-Path -LiteralPath $alt) { Write-Output "  [note] 套件里没有释义表，用 $alt"; $qjSrc = $alt }
    else { throw "既没有 $qjSrc，也没有 $alt —— 先跑 pack-de-kit.ps1" }
}
$lvlSrc = Join-Path $Kit 'levels\levels-de.tsv'
if (-not (Test-Path -LiteralPath $lvlSrc)) {
    $alt = Join-Path $Tools 'de-glossary\levels\levels-de.tsv'
    if (Test-Path -LiteralPath $alt) { Write-Output "  [note] 套件里没有等级表，用 $alt"; $lvlSrc = $alt }
    else { Write-Output '  [note] 没有 levels-de.tsv，跳过（只影响统计页的生词分级）'; $lvlSrc = $null }
}

# 2. 备份现有安装
Write-Output ''
Write-Output "2. 备份到 $backup"
foreach ($one in 'qingjian-server.exe','qingjian-settings.exe') {
    $live = Join-Path $Install $one
    if (Test-Path -LiteralPath $live) { Copy-Item -LiteralPath $live -Destination $backup -Force; Write-Output "   $one" }
}
$liveQj = Join-Path $Install 'data\generated\glossary-de.qj'
if (Test-Path -LiteralPath $liveQj) { Copy-Item -LiteralPath $liveQj -Destination $backup -Force; Write-Output '   glossary-de.qj' }

# 3. 装二进制与释义表
Write-Output ''
Write-Output '3. 安装'
Kill-Server | Out-Null
Start-Sleep -Milliseconds 300
$tries = Copy-Live $serverSrc (Join-Path $Install 'qingjian-server.exe')
Write-Output ("   qingjian-server.exe   OK（第 {0} 次尝试）" -f $tries)
if ($settingsSrc) {
    $tries = Copy-Live $settingsSrc (Join-Path $Install 'qingjian-settings.exe')
    Write-Output ("   qingjian-settings.exe OK（第 {0} 次尝试）" -f $tries)
}
$tries = Copy-Live $qjSrc $liveQj
Write-Output ("   glossary-de.qj        OK（第 {0} 次尝试）" -f $tries)
if ($lvlSrc) {
    $lvlDir = Join-Path $Install 'assets\levels'
    New-Item -ItemType Directory -Force -Path $lvlDir | Out-Null
    $tries = Copy-Live $lvlSrc (Join-Path $lvlDir 'levels-de.tsv')
    Write-Output ("   levels-de.tsv         OK（第 {0} 次尝试）" -f $tries)
}

# 4. 配置
Write-Output ''
Write-Output '4. 配置'
$cfg = Join-Path $env:APPDATA 'Qingjian\config.toml'
if (-not (Test-Path -LiteralPath $cfg)) {
    Write-Output "   [warn] 没有 $cfg：先启动一次设置程序让它生成，再重跑本脚本"
} else {
    Copy-Item -LiteralPath $cfg -Destination (Join-Path $backup 'config.toml') -Force
    $raw = [IO.File]::ReadAllText($cfg)
    $new = [regex]::Replace($raw, '(?m)^\s*learning_language\s*=.*$', 'learning_language = "de"')
    if ($ChineseFirst) { $new = [regex]::Replace($new, '(?m)^\s*chinese_first\s*=.*$', 'chinese_first = true') }
    if ($new -ne $raw) {
        [IO.File]::WriteAllText($cfg, $new, (New-Object Text.UTF8Encoding($false)))
        Write-Output '   learning_language = "de" 已写入（备份见 config.toml）'
    } else {
        Write-Output '   learning_language 已经是 "de"，未改动'
    }
}

# 5. 起 Server
if (-not $NoStart) {
    Write-Output ''
    Write-Output '5. 启动 Server'
    Start-Process -FilePath (Join-Path $Install 'qingjian-server.exe') -WorkingDirectory $Install
    Start-Sleep -Seconds 3
    $procs = @(Get-Process qingjian-server -ErrorAction SilentlyContinue)
    if ($procs.Count -gt 0) { Write-Output ("   PID {0}" -f ($procs.Id -join ',')) } else { Write-Output '   [warn] 没起来，看日志 C:\Users\aolin\AppData\Local\Qingjian\logs\server.*.log' }
}

if (-not $SkipVerify) {
    Write-Output ''
    & pwsh -NoProfile -File (Join-Path $Tools 'verify-de.ps1') -Install $Install -Tools $Tools -Kit $Kit
    exit $LASTEXITCODE
}
Write-Output ''
Write-Output '完成（未验证）。'
