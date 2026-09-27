# 德语版青简体检：一条命令确认「德语译文」补丁还在、能用。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File E:\codemain\qingjian-de\verify-de.ps1
#   powershell ... -File E:\codemain\qingjian-de\verify-de.ps1 -Quick     # 跳过协议探针（不起假 DLL）
#
# 检查项：
#   1. 安装目录里的 Server / 设置程序 = 打补丁的那两个（与 dist 套件里的副本逐字节一致，或用字符串特征兜底）
#   2. data\generated\glossary-de.qj 在位，且是「带定冠词」的那一版（META 里有 german-nouns 字样）；
#      assets\levels\levels-de.tsv（生词分级表）在不在
#   3. %APPDATA%\Qingjian\config.toml 里 learning_language = "de"
#   4. Server 进程在跑
#   5. 用假 DLL 走一遍协议：xuexiao 的候选帧里应出现 "die Schule"
param(
    [string]$Install = 'D:\application\Qingjian',
    [string]$Tools   = 'E:\codemain\qingjian-de',
    [string]$Kit     = 'E:\codemain\qingjian-de\dist\qingjian-de-kit',
    [switch]$Quick
)

$ErrorActionPreference = 'Stop'
$fail = 0
$warn = 0

function Say($ok, $text) {
    if ($ok) { Write-Output "  [ OK ] $text" }
    else { Write-Output "  [FAIL] $text"; $script:fail++ }
}
function Note($text) { Write-Output "  [note] $text" }
function Warn($text) { Write-Output "  [warn] $text"; $script:warn++ }

function Get-Bytes($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    return [IO.File]::ReadAllBytes($path)
}
# 二进制里有没有这段 UTF-8 文本（字体/本地化字符串都会以 UTF-8 常量躺在 .rdata / 数据段里）
function Has-Text($path, $needle) {
    $b = Get-Bytes $path
    if ($null -eq $b) { return $false }
    return ([Text.Encoding]::UTF8.GetString($b)).Contains($needle)
}
function Hash-Of($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}

Write-Output ''
Write-Output "青简德语版体检  安装目录 = $Install"

Write-Output ''
Write-Output '1. 二进制'
foreach ($one in @(
        @{ name = 'qingjian-server.exe';   marker = 'German'; kit = 'qingjian-server.exe' },
        @{ name = 'qingjian-settings.exe'; marker = '德语';   kit = 'qingjian-settings.exe' })) {
    $live = Join-Path $Install $one.name
    if (-not (Test-Path -LiteralPath $live)) { Say $false "$($one.name) 不在安装目录"; continue }
    $liveHash = Hash-Of $live
    $kitFile = Join-Path (Join-Path $Kit 'bin') $one.kit
    $kitHash = Hash-Of $kitFile
    $hasMarker = Has-Text $live $one.marker
    if ($kitHash -and $liveHash -eq $kitHash) {
        Say $true "$($one.name) 与套件里的补丁版逐字节一致（SHA256 $($liveHash.Substring(0,12))…）"
    } elseif ($hasMarker) {
        Warn "$($one.name) 含补丁特征「$($one.marker)」，但与套件副本不同（自己重新构建过？）"
    } else {
        Say $false "$($one.name) 看不到补丁特征「$($one.marker)」——官方更新很可能把它换回去了"
    }
}

Write-Output ''
Write-Output '2. 德语释义表'
$qj = Join-Path $Install 'data\generated\glossary-de.qj'
if (-not (Test-Path -LiteralPath $qj)) {
    Say $false "缺 $qj"
} else {
    $item = Get-Item -LiteralPath $qj
    Say $true ("glossary-de.qj 在位：{0:N0} B，{1}" -f $item.Length, $item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
    $head = [Text.Encoding]::UTF8.GetString((Get-Bytes $qj)[0..2047])
    if ($head.Contains('german-nouns')) {
        Say $true '是「带定冠词」的那一版（META 署名含 german-nouns）'
    } else {
        Warn '这一版没有名词定冠词（META 里没有 german-nouns）：重装或重新打包过？'
    }
}
$lvl = Join-Path $Install 'assets\levels\levels-de.tsv'
if (-not (Test-Path -LiteralPath $lvl)) {
    Warn '没有 assets\levels\levels-de.tsv：统计页德语不生词分级（不影响候选译文）'
} else {
    $lines = [IO.File]::ReadAllLines($lvl)
    $n = @($lines | Where-Object { $_ -ne '' -and -not $_.StartsWith('#') }).Count
    Note ("levels-de.tsv 在位：{0:N0} B，{1:N0} 条能定级" -f (Get-Item -LiteralPath $lvl).Length, $n)
}

Write-Output ''
Write-Output '2b. 引擎能加载这份词表（用套件里的 qingjian-cli）'
$cli = Join-Path $Kit 'bin\qingjian-cli.exe'
$dict = Join-Path $Install 'data\generated\dict.qj'
if (-not (Test-Path -LiteralPath $cli)) {
    Warn "找不到 $cli，跳过（不影响输入法）"
} elseif (-not (Test-Path -LiteralPath $dict)) {
    Warn "找不到 $dict，跳过"
} elseif (-not (Test-Path -LiteralPath $qj)) {
    Warn '词表不在位，跳过'
} else {
    # qingjian-cli 把日志写到 stderr，PS 5.1 在 ErrorActionPreference=Stop 下会当成致命错误；
    # 那句 `glosses=…` 是 INFO 级日志，必须显式打开 RUST_LOG=info 才会打（不然只剩查询结果，数不出条数）
    $eap = $ErrorActionPreference
    $rustLog = $env:RUST_LOG
    $ErrorActionPreference = 'Continue'
    $env:RUST_LOG = 'info'
    $tmp = Join-Path $env:TEMP ('qingjian-verify-cli-{0}.txt' -f $PID)
    try {
        # 不用 PowerShell 的 `2>&1`：native 程序写 stderr 会变成 ErrorRecord，
        # 它落进输出流/错误流的时机不受控（开机自检里曾因此偶发误报「词表加载条数不对」）；
        # 交给 cmd 重定向到文件，一定能同时拿到 INFO 日志与查询结果。
        $cmdLine = '"{0}" --dict "{1}" --glossary "{2}" --language de --limit 1 -- xuexiao > "{3}" 2>&1' -f $cli, $dict, $qj, $tmp
        & $env:ComSpec /c $cmdLine | Out-Null
        $cliOut = if (Test-Path -LiteralPath $tmp) { [IO.File]::ReadAllText($tmp) } else { '' }
    } finally {
        $ErrorActionPreference = $eap
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        if ($null -eq $rustLog) { Remove-Item Env:RUST_LOG -ErrorAction SilentlyContinue }
        else { $env:RUST_LOG = $rustLog }
    }
    $m = [regex]::Match($cliOut, 'glosses=(\d+)')
    if ($m.Success -and [int]$m.Groups[1].Value -ge 200000) {
        Say $true "引擎加载成功：glosses=$($m.Groups[1].Value)（≥200,000）"
    } else {
        Say $false '词表加载条数不对（期望 ≥200,000）'
        Write-Output $cliOut
    }
    if ($cliOut -match 'die Schule') { Say $true 'CLI 查 xuexiao → 学校 die Schule' }
    else { Say $false 'CLI 查 xuexiao 没看到 die Schule' }
}

Write-Output ''
Write-Output '3. 配置'
$cfg = Join-Path $env:APPDATA 'Qingjian\config.toml'
if (-not (Test-Path -LiteralPath $cfg)) {
    Say $false "缺 $cfg"
} else {
    $text = [IO.File]::ReadAllText($cfg)
    Say ([regex]::IsMatch($text, '(?m)^\s*learning_language\s*=\s*"de"')) 'learning_language = "de"'
    if ([regex]::IsMatch($text, '(?m)^\s*chinese_first\s*=\s*true')) { Note 'chinese_first = true（中文候选排英文前）' }
    else { Note 'chinese_first 不是 true：拼音像英文词时英文候选排第一（想要中文在前就改成 true）' }
}

Write-Output ''
Write-Output '4. Server 进程'
$procs = @(Get-Process qingjian-server -ErrorAction SilentlyContinue)
if ($procs.Count -gt 0) {
    Say $true ("在跑：PID {0}，启动于 {1}" -f ($procs.Id -join ','), $procs[0].StartTime.ToString('yyyy-MM-dd HH:mm:ss'))
} else {
    Warn '没在跑（打字时会由输入法自动拉起，也可以手工启动）'
}

if (-not $Quick) {
    Write-Output ''
    Write-Output '5. 协议探针（假 DLL，protocol 7 = 安装自带的 0.1.4 DLL）'
    $probe = Join-Path $Tools 'probe-dll.ps1'
    if (-not (Test-Path -LiteralPath $probe)) {
        Warn "找不到 $probe，跳过"
    } elseif ($procs.Count -eq 0) {
        Warn 'Server 没在跑，跳过'
    } else {
        $out = & pwsh -NoProfile -File $probe -Protocol 7 -Keys xuexiao -Expect 'die Schule' 2>&1 | Out-String
        if ($out -match 'expect\s+=\s+die Schule -> True') {
            Say $true '候选帧里带德语译文：学校 → die Schule'
        } else {
            Say $false '候选帧里没有 "die Schule"，看下面的原始输出'
            Write-Output $out
        }
    }
}

Write-Output ''
if ($fail -eq 0) { Write-Output "结论：通过（$warn 条提示）—— 德语译文可用。" }
else { Write-Output "结论：$fail 项不合格 —— 先跑 redeploy-de.ps1 重装补丁。" }
exit ([int]($fail -gt 0))
