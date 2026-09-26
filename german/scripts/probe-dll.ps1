# 假 DLL：按协议跟 Server 说话，检查下发的帧里语言记号是什么。
# 用法: pwsh -File probe-dll.ps1 -Protocol 7 -Keys nihao
param(
    [int]$Protocol = 7,
    [string]$Keys = 'nihao',
    [string]$Expect = ''
)

$ErrorActionPreference = 'Stop'

$pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', 'qingjian', [System.IO.Pipes.PipeDirection]::InOut)
$pipe.Connect(5000)

function Send-Frame([string]$json) {
    $body = [Text.Encoding]::UTF8.GetBytes($json)
    $len = [BitConverter]::GetBytes([uint32]$body.Length)
    $pipe.Write($len, 0, 4)
    $pipe.Write($body, 0, $body.Length)
    $pipe.Flush()
}

function Receive-Frame {
    $lb = New-Object byte[] 4
    $got = 0
    while ($got -lt 4) {
        $n = $pipe.Read($lb, $got, 4 - $got)
        if ($n -le 0) { throw 'eof while reading length' }
        $got += $n
    }
    $len = [BitConverter]::ToUInt32($lb, 0)
    $buf = New-Object byte[] $len
    $got = 0
    while ($got -lt $len) {
        $n = $pipe.Read($buf, $got, $len - $got)
        if ($n -le 0) { throw 'eof while reading body' }
        $got += $n
    }
    return [Text.Encoding]::UTF8.GetString($buf)
}

$mods = @{ ctrl = $false; shift = $false; alt = $false; win = $false; caps = $false; english_mode = $false }
$vks = @{ a = 65; b = 66; c = 67; d = 68; e = 69; f = 70; g = 71; h = 72; i = 73; j = 74; k = 75; l = 76; m = 77
          n = 78; o = 79; p = 80; q = 81; r = 82; s = 83; t = 84; u = 85; v = 86; w = 87; x = 88; y = 89; z = 90 }

"protocol = $Protocol"
Send-Frame (@{ OpenSession = @{ session = 7; app = 'probe.exe'; protocol = $Protocol } } | ConvertTo-Json -Compress -Depth 6)
$opened = Receive-Frame
"OPENED  : $($opened.Substring(0, [Math]::Min(200, $opened.Length)))"

$frames = @()
foreach ($ch in $Keys.ToCharArray()) {
    $vk = $vks["$ch"]
    if ($null -eq $vk) { continue }
    $event = @{ virtual_key = $vk; character = "$ch"; modifiers = $mods }
    Send-Frame (@{ Key = @{ session = 7; event = $event } } | ConvertTo-Json -Compress -Depth 6)
    $r = Receive-Frame
    $frames += $r
    $short = if ($r.Length -gt 220) { $r.Substring(0, 220) + '...' } else { $r }
    "KEY $ch    : $short"
}

$joined = $frames -join "`n"
''
"frames       = $($frames.Count)"
"`"German`" in frames = $([regex]::Matches($joined, '\"German\"').Count)"
"`"English`" in frames = $([regex]::Matches($joined, '\"English\"').Count)"
"has 你好     = $($joined.Contains('你好'))"
"has Hallo    = $($joined.Contains('Hallo'))"
$m = [regex]::Match($joined, '.{0,60}你好.{0,320}')
if ($m.Success) { "context      = $($m.Value)" }
if ($Expect) {
    "expect       = $Expect -> $($joined.Contains($Expect))"
    $e = [regex]::Match($joined, ".{0,80}$([regex]::Escape($Expect)).{0,200}")
    if ($e.Success) { "expect ctx   = $($e.Value)" }
}

Send-Frame (@{ CloseSession = @{ session = 7 } } | ConvertTo-Json -Compress -Depth 4)
$pipe.Dispose()
