# 注册 / 查看 / 卸载「青简德语开机自检」计划任务。
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File register-selfcheck.ps1            # 注册（登录时跑）
#   ... -File register-selfcheck.ps1 -At '09:00'                                          # 也可以每天定时跑
#   ... -File register-selfcheck.ps1 -RunNow                                              # 注册完立刻试跑一次
#   ... -File register-selfcheck.ps1 -Remove                                              # 卸载
#   ... -File register-selfcheck.ps1 -Status                                              # 看状态与上次结果
param(
    [string]$At,
    [switch]$RunNow,
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$name = 'QingjianGermanSelfCheck'
$root = 'E:\codemain\qingjian-de'
$check = Join-Path $root 'selfcheck.ps1'

if ($Status) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) { Write-Output "任务 $name 未注册"; exit 1 }
    $i = Get-ScheduledTaskInfo -TaskName $name
    Write-Output "任务 $name：$($t.State)"
    Write-Output ("上次运行 {0}，结果 0x{1:X}；下次 {2}" -f $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime)
    $last = Join-Path $root 'logs\selfcheck-last.txt'
    if (Test-Path -LiteralPath $last) { Write-Output ''; Get-Content -LiteralPath $last | Select-Object -First 12 }
    exit 0
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "已卸载 $name"
    exit 0
}

if (-not (Test-Path -LiteralPath $check)) { throw "找不到 $check" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $check)
if ($At) {
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    Write-Output "触发器：每天 $At"
} else {
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $trigger.Delay = 'PT30S'
    Write-Output '触发器：登录后 30 秒'
}
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force `
    -Description '登录后跑 verify-de.ps1 检查青简德语补丁（词表/配置/进程/协议），不合格弹窗提示。' | Out-Null
Write-Output "已注册计划任务 $name → $check"

if ($RunNow) {
    Write-Output '立刻试跑（最多等 3 分钟）…'
    Start-ScheduledTask -TaskName $name
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        $i = Get-ScheduledTaskInfo -TaskName $name
    } while ($i.LastTaskResult -eq 267009 -and (Get-Date) -lt $deadline)
    Get-ScheduledTaskInfo -TaskName $name | Select-Object LastRunTime, LastTaskResult | Format-List
}

