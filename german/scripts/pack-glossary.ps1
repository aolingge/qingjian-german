# 把合并后的 TSV 打成 glossary-de.qj（官方 qingjian-dict-convert），并打印体积/条目数/SHA256。
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File E:\codemain\qingjian-de\pack-glossary.ps1
#   ... -File pack-glossary.ps1 -Input E:\codemain\qingjian-de\de-glossary\glossary-de-final.tsv
#   ... -File pack-glossary.ps1 -Deploy          # 打完顺带拷进安装目录（杀-复制重试）
#
# 元数据（name/license/attribution/source/data-version）写进 .qj 的 META 段，
# verify-de.ps1 会检查 META 里有没有 german-nouns 字样。
param(
    # 注意：参数不能叫 $Input —— 那是 PowerShell 的自动变量（管道输入枚举器），
    # 在 pwsh 7 里会被自动覆盖成空串，导致 Test-Path 报「空字符串」。
    [Alias('Input')]
    [string]$InputTsv = 'E:\codemain\qingjian-de\de-glossary\glossary-de-final.tsv',
    [string]$OutDir  = 'E:\codemain\qingjian-de\de-glossary\out',
    [string]$Levels  = 'E:\codemain\qingjian-de\de-glossary\levels\levels-de.tsv',
    [string]$Convert = 'C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926\target\release\qingjian-dict-convert.exe',
    [string]$DataVersion = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$Install = 'D:\application\Qingjian',
    [switch]$Deploy
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $InputTsv)) { throw "找不到输入表：$InputTsv" }
if (-not (Test-Path -LiteralPath $Convert)) { throw "找不到打包器：$Convert（先跑 pack-de.cmd）" }
$null = New-Item -ItemType Directory -Force -Path $OutDir

$name = '青简德语释义（HanDeDict + german-nouns + DeepSeek 补词/补冠词）'
$attr = 'HanDeDict (CC BY-SA 3.0, https://github.com/gugray/HanDeDict); german-nouns (CC BY-SA 4.0, https://github.com/gambolputty/german-nouns); Goethe-Institut A1-B2 词汇表 (MIT); 缺失词条/冠词/等级由 DeepSeek 补写'
$lines = (Get-Content -LiteralPath $InputTsv | Where-Object { $_ -and -not $_.StartsWith('#') }).Count
Write-Output "输入 $InputTsv`n  $lines 行"

& $Convert --out-dir $OutDir pack glossary `
    --input $InputTsv --language de `
    --name $name --license 'CC-BY-SA-4.0' --attribution $attr `
    --source 'https://github.com/aolingge/qingjian-german' --data-version $DataVersion
if ($LASTEXITCODE -ne 0) { throw "打包失败（exit $LASTEXITCODE）" }

$qj = Join-Path $OutDir 'glossary-de.qj'
$h = (Get-FileHash -LiteralPath $qj -Algorithm SHA256).Hash
Write-Output ("产物 {0}`n  {1:N0} B  sha256 {2}" -f $qj, (Get-Item -LiteralPath $qj).Length, $h)
[IO.File]::WriteAllText((Join-Path $OutDir 'glossary-de.qj.sha256'), "$h  glossary-de.qj`n", (New-Object Text.UTF8Encoding($false)))

if ($Deploy) {
    $dst = Join-Path $Install 'data\generated\glossary-de.qj'
    for ($i = 1; $i -le 12; $i++) {
        @(Get-Process qingjian-server -ErrorAction SilentlyContinue) | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 150
        try { Copy-Item -LiteralPath $qj -Destination $dst -Force -ErrorAction Stop
              Write-Output "已部署到 $dst（第 $i 次尝试）"; break }
        catch { if ($i -eq 12) { throw }; Start-Sleep -Milliseconds 600 }
    }
    # 顺带部署等级表（assets\levels\levels-de.tsv），旧表留一份带日期的备份
    $lvl = $Levels
    if ($lvl -and (Test-Path -LiteralPath $lvl)) {
        $ldst = Join-Path $Install 'assets\levels\levels-de.tsv'
        if (Test-Path -LiteralPath $ldst) {
            $bak = "$ldst.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Copy-Item -LiteralPath $ldst -Destination $bak -Force
            Write-Output "旧等级表已备份到 $bak"
        }
        Copy-Item -LiteralPath $lvl -Destination $ldst -Force
        Write-Output ("已部署到 {0}（{1:N0} B）" -f $ldst, (Get-Item -LiteralPath $ldst).Length)
    } else {
        Write-Output "跳过等级表部署（找不到 $lvl）"
    }
}

