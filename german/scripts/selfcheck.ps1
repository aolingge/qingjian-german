# 青简德语版「开机自检」：登录后自动跑一次 verify-de.ps1，坏了就弹窗告诉你。
#
# 由计划任务 QingjianGermanSelfCheck 在登录时调用（见 register-selfcheck.ps1）。
# 手动跑：
#   powershell -NoProfile -ExecutionPolicy Bypass -File E:\codemain\qingjian-de\selfcheck.ps1
#   ... -File selfcheck.ps1 -NoPopup      # 不弹窗（只写日志，方便手工/脚本调用）
param(
    [switch]$NoPopup,
    [int]$DelaySeconds = 20
)

$ErrorActionPreference = 'Continue'
$root = 'E:\codemain\qingjian-de'
$logDir = Join-Path $root 'logs'
$null = New-Item -ItemType Directory -Force -Path $logDir
$stamp = Get-Date
$log = Join-Path $logDir ("selfcheck-{0:yyyyMMdd}.log" -f $stamp)
$last = Join-Path $logDir 'selfcheck-last.txt'
$verify = Join-Path $root 'verify-de.ps1'

# 开机后等一会儿：输入法/Server 都是登录后才起来的
if ($DelaySeconds -gt 0) { Start-Sleep -Seconds $DelaySeconds }

if (-not (Test-Path -LiteralPath $verify)) {
    $text = "找不到 $verify —— 自检脚本被删了？"
    $code = 2
} else {
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify 2>&1 | Out-String
    $code = $LASTEXITCODE
    $text = $out
}

$failed = @($text -split "`r?`n" | Where-Object { $_ -match '\[FAIL\]' })
$ok = ($code -eq 0)

$header = @(
    "===== 青简德语自检 $(if ($ok) { '通过' } else { '不合格' })  $($stamp.ToString('yyyy-MM-dd HH:mm:ss')) =====",
    "verify-de.ps1 退出码 = $code"
) -join "`r`n"

Add-Content -LiteralPath $log -Value ($header + "`r`n" + $text) -Encoding UTF8
[IO.File]::WriteAllText($last, ($header + "`r`n" + ($failed -join "`r`n") + "`r`n"),
    (New-Object Text.UTF8Encoding($false)))

if (-not $ok -and -not $NoPopup) {
    $body = if ($failed.Count -gt 0) { ($failed -join "`n") } else { ($text -split "`r?`n" | Select-Object -Last 4) -join "`n" }
    $msg = "青简德语补丁自检没通过：`n`n$body`n`n修复：跑 E:\codemain\qingjian-de\redeploy-de.ps1 重装补丁`n日志：$log"
    try {
        $sh = New-Object -ComObject WScript.Shell
        $null = $sh.Popup($msg, 180, '青简德语自检', 16)   # 16 = 停止图标
    } catch {
        Add-Content -LiteralPath $log -Value "（弹窗失败：$_）" -Encoding UTF8
    }
}

exit ([int](-not $ok))
