# 把德语版青简的「重装套件」收到 E:\codemain\qingjian-de\dist\ —— 补丁二进制、德语释义表、配置快照、
# 源码补丁、HanDeDict 原始数据、全部脚本。目的：%TEMP% 被清掉或官方更新覆盖了二进制之后还能一条命令装回来。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File E:\codemain\qingjian-de\pack-de-kit.ps1
param(
    [string]$DistRoot = 'E:\codemain\qingjian-de\dist',
    [string]$Install   = 'D:\application\Qingjian',
    [string]$Source    = 'C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926',
    [string]$Handedict = 'C:\Users\aolin\AppData\Local\Temp\codex-handedict-source-20260926\handedict.u8'
)

$ErrorActionPreference = 'Stop'
$tools = 'E:\codemain\qingjian-de'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$kit = Join-Path $DistRoot "qingjian-de-kit"
New-Item -ItemType Directory -Force -Path $kit | Out-Null
foreach ($sub in 'bin','glossary','levels','config','sources','scripts','notes') {
    New-Item -ItemType Directory -Force -Path (Join-Path $kit $sub) | Out-Null
}

function Copy-One($from, $toDir, $name) {
    if (-not (Test-Path -LiteralPath $from)) { Write-Output "  跳过（不存在）: $from"; return }
    $to = Join-Path $toDir $name
    Copy-Item -LiteralPath $from -Destination $to -Force
    $item = Get-Item -LiteralPath $to
    Write-Output ("  {0,-28} {1,12:N0} B  {2}" -f $name, $item.Length, $item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
}

Write-Output '== 1. 打补丁后的二进制（Server / 设置 / 两个 TSF DLL）=='
Copy-One "$Install\qingjian-server.exe"   (Join-Path $kit 'bin') 'qingjian-server.exe'
Copy-One "$Install\qingjian-settings.exe" (Join-Path $kit 'bin') 'qingjian-settings.exe'
Copy-One "$Source\target\release\qingjian_tsf.dll"                (Join-Path $kit 'bin') 'qingjian_tsf-x64.dll'
Copy-One "$Source\target\i686-pc-windows-msvc\release\qingjian_tsf.dll" (Join-Path $kit 'bin') 'qingjian_tsf-x86.dll'
Copy-One "$Source\target\release\qingjian-cli.exe"               (Join-Path $kit 'bin') 'qingjian-cli.exe'
Copy-One "$Source\target\release\qingjian-dict-convert.exe"      (Join-Path $kit 'bin') 'qingjian-dict-convert.exe'

Write-Output '== 2. 德语释义表（安装目录的 .qj + 可编辑的 TSV 源）=='
Copy-One "$Install\data\generated\glossary-de.qj" (Join-Path $kit 'glossary') 'glossary-de.qj'
Copy-One "$env:APPDATA\Qingjian\custom\glossary-de-hd.tsv" (Join-Path $kit 'glossary') 'glossary-de-hd.tsv'
Copy-One (Join-Path $tools 'de-glossary\glossary-de-art.tsv') (Join-Path $kit 'glossary') 'glossary-de-art.tsv'
Copy-One "$env:APPDATA\Qingjian\user-glossary-de.tsv" (Join-Path $kit 'glossary') 'user-glossary-de.tsv'
Copy-One (Join-Path $tools 'de-glossary\gender\nouns.csv') (Join-Path $kit 'sources') 'german-nouns.csv'
Copy-One (Join-Path $tools 'de-glossary\glossary-de-merged.tsv') (Join-Path $kit 'sources') 'glossary-de-merged.tsv'
Copy-One (Join-Path $tools 'de-glossary\llm-fill.tsv') (Join-Path $kit 'sources') 'llm-fill.tsv'
Copy-One (Join-Path $tools 'de-glossary\llm-fill2.tsv') (Join-Path $kit 'sources') 'llm-fill2.tsv'
Copy-One (Join-Path $tools 'de-glossary\llm-fill-all.tsv') (Join-Path $kit 'sources') 'llm-fill-all.tsv'
Copy-One (Join-Path $tools 'de-glossary\glossary-de-art2.tsv') (Join-Path $kit 'sources') 'glossary-de-art2.tsv'
Copy-One (Join-Path $tools 'de-glossary\llm-fill-phrase.tsv') (Join-Path $kit 'sources') 'llm-fill-phrase.tsv'
Copy-One (Join-Path $tools 'de-glossary\NOTES-llm-fill.md') (Join-Path $kit 'sources') 'NOTES-llm-fill.md'

Write-Output '== 3. 德语词汇等级表（生词分级用，放 <安装目录>\assets\levels\）=='
Copy-One "$Install\assets\levels\levels-de.tsv" (Join-Path $kit 'levels') 'levels-de.tsv'
Copy-One (Join-Path $tools 'de-glossary\levels\build_levels_de.py') (Join-Path $kit 'levels') 'build_levels_de.py'
Copy-One (Join-Path $tools 'de-glossary\levels\coverage_compare.py') (Join-Path $kit 'levels') 'coverage_compare.py'
Copy-One (Join-Path $tools 'de-glossary\levels\20260716200932-goethe-german-5000.de.tsv') (Join-Path $kit 'sources') 'goethe-german-5000.de.tsv'

Write-Output '== 4. 配置快照（不改用户的 config.toml，只留一份可对照的副本）=='
Copy-One "$env:APPDATA\Qingjian\config.toml" (Join-Path $kit 'config') 'config.toml.snapshot'

Write-Output '== 5. 全部脚本与文档 =='
foreach ($name in 'build-de.cmd','build-x64.cmd','build-x86.cmd','cli-de.cmd','pack-de.cmd','linkwrap.cmd','test-de.cmd',
                  'deploy-de.ps1','pack-de-kit.ps1','verify-de.ps1','redeploy-de.ps1','probe-dll.ps1','ocr.ps1','ocr-de.ps1',
                  'README.md') {
    Copy-One (Join-Path $tools $name) (Join-Path $kit 'scripts') $name
}
if (Test-Path -LiteralPath (Join-Path $tools 'de-glossary')) {
    $dest = Join-Path $kit 'scripts\de-glossary'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    # 只带脚本与报告：gender\nouns.csv（20 MB）与 out\glossary-de.qj 已分别放在 sources\ 与 glossary\
    foreach ($f in Get-ChildItem -LiteralPath (Join-Path $tools 'de-glossary') -Recurse -File) {
        if ($f.Extension -eq '.py' -or $f.Extension -eq '.txt') {
            Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
            Write-Output ("  {0,-28} {1,12:N0} B  scripts\de-glossary" -f $f.Name, $f.Length)
        }
    }
}

Write-Output '== 6. HanDeDict 原始数据（%TEMP% 里的那份随时可能没了）=='
Copy-One $Handedict (Join-Path $kit 'sources') 'handedict.u8'

Write-Output '== 7. 源码补丁（相对上游 40e3e55；同样内容已提交到 german 分支）=='
if (Test-Path -LiteralPath $Source) {
    Push-Location $Source
    try {
        $diff = & git diff 40e3e55 -- . ':(exclude)german' 2>&1 | Out-String
        [IO.File]::WriteAllText((Join-Path $kit 'sources\qingjian-german.patch'), $diff, (New-Object Text.UTF8Encoding($false)))
        $st = & git status --porcelain 2>&1 | Out-String
        [IO.File]::WriteAllText((Join-Path $kit 'sources\git-status.txt'), $st, (New-Object Text.UTF8Encoding($false)))
        $head = & git log --oneline -1 2>&1 | Out-String
        $head += "`nbranch: " + (& git rev-parse --abbrev-ref HEAD 2>&1 | Out-String)
        $head += "`nbuild: cargo build --release --locked (见 scripts\build-de.cmd)"
        [IO.File]::WriteAllText((Join-Path $kit 'notes\source-revision.txt'), $head, (New-Object Text.UTF8Encoding($false)))
        Write-Output ("  qingjian-german.patch  {0,10:N0} B" -f (Get-Item (Join-Path $kit 'sources\qingjian-german.patch')).Length)
        Write-Output ("  git-status.txt         {0,10:N0} B" -f (Get-Item (Join-Path $kit 'sources\git-status.txt')).Length)
    } finally { Pop-Location }
} else {
    Write-Output "  跳过：源码目录不在了（$Source）"
}

Write-Output '== 8. 重建说明 =='
$readme = @'
# 青简德语版重装套件

生成时间：__STAMP__（脚本 pack-de-kit.ps1）

这套东西是「德语译文」补丁的完整副本。官方更新覆盖 qingjian-server.exe / qingjian-settings.exe，
或 %TEMP% 里的源码目录、HanDeDict 数据被清掉之后，按下面的顺序能装回来。

## 目录

- `bin\`：打补丁后的二进制。`qingjian-server.exe`、`qingjian-settings.exe` 覆盖安装目录同名文件；
  两个 `qingjian_tsf-*.dll` 只有在注册/重装 TSF 时才用得上（当前安装用的是 0.1.4 自带的 DLL，
  Server 侧已对老 DLL 做协议降级，不换 DLL 也能显示德语）。
  另外 `qingjian-cli.exe` 是命令行测试工具（`--language de --dict … --glossary … -- 拼音`，
  见 `scripts\README.md` 第四节），`qingjian-dict-convert.exe` 是把 TSV 打成 `.qj` 的官方打包器
  （`pack glossary --input … --language de --name …`）——这两个是从源码重建才有的，放这里免得 %TEMP% 被清。
- `glossary\glossary-de.qj`：**205,226 条**中文→德语释义（`n. die Schule` / `n. das Auto, der Wagen`），
  可直接放进 `<安装目录>\data\generated\`。四层来源：① HanDeDict（157,162 条，CC-BY-SA-3.0）② 用
  german-nouns（CC-BY-SA-4.0）给名词补的定冠词（第一轮 38,241 行 + 第二轮 `glossary-de-art2.tsv` 再修 4,876 行）
  ③ 词库里 HanDeDict 没收的 47,432 个词由 DeepSeek `deepseek-v4-flash` 生成（严格轮 `sources\llm-fill.tsv`
  + 放宽轮 `sources\llm-fill2.tsv` → 清洗合并成 `sources\llm-fill-all.tsv`）
  ④ 高频短语 632 条同样由 DeepSeek 补（`sources\llm-fill-phrase.tsv`，含 `--phrase` 短语轮与 `--no-hint` 轮）；
  脚本 `scripts\de-glossary\{llm_fill,postprocess,merge_glossary,add_articles2,audit}.py`。
  同目录另有来源文件：`glossary-de-hd.tsv`（无冠词原样转换）、`glossary-de-art.tsv`（第一轮加冠词）、
  `sources\glossary-de-art2.tsv`（第二轮加冠词）、`sources\glossary-de-merged.tsv`（合并 LLM 条目后、
  打包 .qj 的真正输入，205,226 行）；`glossary\user-glossary-de.tsv`
  是**个人释义表**（原样放到 `%APPDATA%\Qingjian\`，个人表优先于随包表，手改单条释义就改它）。
- `levels\levels-de.tsv`：德语词汇等级表（生词分级），放 `<安装目录>\assets\levels\`。
  36,560 / 157,163 条释义能定级（23.3%），来源 Goethe-Institut 5,000 词表（MIT，见 `sources\goethe-german-5000.de.tsv`）
  与 `levels\build_levels_de.py`（后者可重跑）。没有它 → 统计页德语不生词分级，其它一切照常。
- `config\config.toml.snapshot`：`learning_language = "de"` 的配置样子（不要整份覆盖，只对照第 5 行等）。
  其中 `[update] check = false` 是**按用户要求关掉的每日更新检查**（青简的更新器本来就只提示、不自动下载安装）。
- `sources\handedict.u8`：HanDeDict 原始数据（CC-BY-SA 3.0），重建词表用。
- `sources\qingjian-german.patch`：德语改动相对上游 `40e3e55` 的完整 diff（不含 `german\` 数据目录）。
  同样的内容已推送到 https://github.com/aolingge/qingjian-german 的 `german` 分支（提交 `977bf9f`），
  Release `v0.1.5-dev-german` 里挂着同一份 205,226 条的 `glossary-de.qj`。
- `scripts\`：构建 / 部署 / 验证 / OCR / 协议探针脚本。

## 重装步骤

1. 停掉 Server：`Get-Process qingjian-server | Stop-Process`
2. `copy bin\qingjian-server.exe "D:\application\Qingjian\"` 与 `...\qingjian-settings.exe`
3. `copy glossary\glossary-de.qj "D:\application\Qingjian\data\generated\"`
4. `copy levels\levels-de.tsv "D:\application\Qingjian\assets\levels\"`（可选，生词分级用）
5. 确认 `%APPDATA%\Qingjian\config.toml` 里 `learning_language = "de"`
6. 启动：`Start-Process -WorkingDirectory "D:\application\Qingjian" "D:\application\Qingjian\qingjian-server.exe"`
7. 验证：`powershell -File scripts\verify-de.ps1`（或 redeploy-de.ps1 一条命令做完 1-7）

## 从源码重建

`scripts\build-de.cmd` 需要：源码（git clone https://github.com/qingjian-team/qingjian.git，
checkout `notes\source-revision.txt` 里记的那个 revision）、
`cargo` + MSVC BuildTools，以及 `E:\codemain\qingjian-de\sdklib|sdkinc|qjbin` 里那份 NuGet 里的 Windows SDK
（本机没装 Windows SDK，见 README「三、构建」）。
'@
$readme = $readme.Replace('__STAMP__', $stamp)
[IO.File]::WriteAllText((Join-Path $kit 'notes\reinstall.txt'), $readme, (New-Object Text.UTF8Encoding($false)))
Write-Output '   notes\reinstall.txt 已写好'

Write-Output ''
Write-Output "== 套件大小 =="
$sum = (Get-ChildItem -LiteralPath $kit -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Output ("{0}  共 {1:N0} B ({2:N1} MB)" -f $kit, $sum, ($sum / 1MB))
