# 青简 German 学习语言 — build & deploy pipeline

> 已发布到 GitHub：**https://github.com/aolingge/qingjian-german**（上游的 fork，默认分支 `german`）。
> 仓库里是同一份成果（`german/` 目录）；打包好的释义表在
> [Release v0.1.10-dev-german](https://github.com/aolingge/qingjian-german/releases/tag/v0.1.10-dev-german)
> （仅包含 `glossary-de.qj`、`glossary-de.qj.sha256`、`levels-de.tsv`，不含 Server、设置程序或安装包）。

本目录是给《青简》Windows 版加 **德语（de）** 学习语言的本地构建/部署工具链。
首次从源码构建，请先看 [README 的通用 Windows x64 构建步骤](../README.md#b-从源码构建)。
下文保留原构建机器的工程记录：安装路径、SDK 版本和包装脚本参数都是该机器的示例，
不代表读者机器的配置或当前上游版本。部署脚本可能覆盖安装文件、重启 Server 或调整更新任务，运行前应逐项检查。
记录中的安装目录为 `D:\application\Qingjian`，当时安装的是上游 0.1.4。

## 一、源码补丁（相对上游）

上游 checkout：`<上游源码目录>`
（`https://github.com/qingjian-team/qingjian.git`，HEAD `40e3e550425466e6ba9c0a14de3a77ed04862799`）

| 文件 | 改动 |
| --- | --- |
| `crates\qingjian-core\src\candidate\language.rs` | `Language` 加 `German` 变体；`code()` → `"de"`；`FromStr` 接受 `de / de-de / german / deutsch`；测试同步 |
| `apps\windows\settings\src\panel\pages\general.rs` | 学习语言下拉加 `("德语","de")` |
| `apps\windows\settings\src\panel\pages\usage.rs` | `language_name` 加 `Language::German => "德语"` |
| `apps\windows\server\src\assembly\mod.rs` | `load_vocabulary` 循环加 `Language::German`（缺 `levels-de.tsv` 会被跳过） |
| `crates\qingjian-predict\src\gloss\prompt.rs` | 德语云联想提示词 `GERMAN_SYSTEM_PROMPT` + `is_german_char`（保留 ä ö ü ß）+ 测试 |
| `apps\windows\{server,settings}\build.rs` | 图标路径用 `CARGO_MANIFEST_DIR` 拼绝对路径（否则 build script 的 CWD 不是 crate 根，报 os error 3） |

释义表本身与语言无关（`.qj` 容器不存语言，语言由调用方传入），所以德语表可以直接复用。

## 二、这台机器上的构建前提

本机**没装 Windows SDK**，MSVC BuildTools 只有编译器。手工补齐（都放在本目录）：

| 目录 | 内容 | 来源 |
| --- | --- | --- |
| `sdklib\x64` / `sdklib\x86` | 460 / 458 个 SDK 导入库 + UCRT（含 `kernel32.lib`、`uuid.lib`、`libucrt.lib`） | NuGet `Microsoft.Windows.SDK.CPP.{x64,x86}` `10.0.29648.1000-preview` |
| `sdkinc\` | SDK 头文件（ucrt/shared/um/winrt/cppwinrt，4776 个） | NuGet `Microsoft.Windows.SDK.CPP` 同版本 |
| `sdkbin\x64` / `sdkbin\x86` | `mt.exe`、`rc.exe` 等 SDK 工具 | NuGet `Microsoft.Windows.SDK.BuildTools` 同版本 |
| `nuget\*.nupkg` | 上面三个包的原始 nupkg（重装用） | `api.nuget.org` |
| `qjbin\{x64,x86}` | 只放 `mt.exe`/`rc.exe` 及依赖 DLL | 从 `sdkbin` 精简而来 |
| `linkwrap.cmd` | x64 链接器 shim，写进 workspace `.cargo\config.toml` 的 `linker =` | 本项目 |

工程里 `.cargo\config.toml`（在源码 checkout 内）被改成：

```toml
[target.x86_64-pc-windows-msvc]
rustflags = ["-C", "target-feature=+crt-static"]
linker = "E:\\codemain\\qingjian-de\\linkwrap.cmd"

# i686：LIB 放 x64 库（cargo 给宿主编 build script 要用），目标自己的 x86 库走 /LIBPATH
[target.i686-pc-windows-msvc]
rustflags = [
    "-C", "target-feature=+crt-static",
    "-C", "link-arg=/LIBPATH:E:\\codemain\\qingjian-de\\sdklib\\x86",
    "-C", "link-arg=/LIBPATH:C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Tools\\MSVC\\14.44.35207\\lib\\x86",
]
```

另外需要 `rustup target add i686-pc-windows-msvc --toolchain 1.96.0-x86_64-pc-windows-msvc`（已装）。

## 三、脚本

| 脚本 | 作用 |
| --- | --- |
| `build-de.cmd release` | 先 x64（server+tsf+settings），成功后再 x86 TSF DLL |
| `build-de.cmd check` | 只做 `cargo check`（x64） |
| `build-x64.cmd` / `build-x86.cmd` | 两个阶段各自独立，避免 32/64 位 LIB 互相污染 |
| `cli-de.cmd` | 编译 `qingjian-cli.exe`（命令行验证工具） |
| `test-de.cmd` | `cargo test -p qingjian-core -p qingjian-predict` |
| `deploy-de.ps1` | 备份 + 停旧 server + 装新二进制 + 装德语释义表 + 改 config + 重启（`-DryRun` 只预览，`-RegisterTsf` 才动 TSF 注册） |
| `pack-de.cmd` | 编译 `qingjian-dict-convert.exe`（官方 TSV→`.qj` 打包器） |
| `verify-de.ps1` | 体检：二进制是不是补丁版、释义表在不在（含冠词版特征）、等级表、config、Server、协议探针（`-Quick` 跳过探针） |
| `redeploy-de.ps1` | 一条命令装回来：装二进制 + 换释义表 + 装等级表 + 改 config + 起 Server + 体检（处理后述 mmap/自动重启坑） |
| `pack-de-kit.ps1` | 把二进制/释义表/配置快照/源码补丁/脚本打成本地套件 `dist\qingjian-de-kit\` |
| `pack-glossary.ps1` | 一条命令：TSV → `out\glossary-de.qj`（调官方打包器）+ 打印 sha256；带 `-Deploy` 顺带装进安装目录（先停 Server） |
| `selfcheck.ps1` | 开机自检：延迟 20 秒跑 `verify-de.ps1`，写 `logs\selfcheck-<date>.log` 与 `selfcheck-last.txt`，失败弹窗提醒 |
| `register-selfcheck.ps1` | 注册/查看/移除计划任务 `QingjianGermanSelfCheck`（登录后 30 秒触发；`-RunNow`、`-Status`、`-Remove`、`-At`） |
| `probe-dll.ps1` | 假 DLL 走命名管道协议，检查下发帧（`-Protocol`、`-Keys`、`-Expect`） |
| `ocr.ps1` / `ocr-de.ps1` | Windows OCR 读截图（必须 `powershell.exe` 5.1 跑，WinRT 反射在 pwsh 7 里报 `Operation is not supported`） |

`.cmd` 必须是 **CRLF** 换行，否则 cmd.exe 会把注释里的中文/路径当命令执行。

## 四、验证德语（不碰输入法）

```powershell
$cli = 'E:\codemain\qingjian-de\dist\qingjian-de-kit\bin\qingjian-cli.exe'   # 套件里的副本（源码树 target\release 下也有一份）
$d   = 'D:\application\Qingjian\data\generated'
& $cli --language de --dict "$d\dict.qj" --glossary "$d\glossary-de.qj" `
       --limit 5 -- xuexiao qiche jiaotong
```

（`--dict` 必须给，否则报 `failed to read dictionary: 系统找不到指定的路径。 (os error 3)`；
位置参数是「一个个拼音串」，多个就是多轮查询。）

期望看到：

```
INFO 加载完成 … glossary=…\glossary-de.qj glosses=205333 …
> xuexiao
   1. 学校    n. die Schule
> qiche
   1. 汽车  n. das Auto, Wagen, der Kraftwagen, das Automobil, das Kraftfahrzeug
```

server 日志应打印（`%LOCALAPPDATA%\Qingjian\logs\server.<日期>.log`）：

```
青简 Windows Server 就绪 … glossary="…\glossary-de.qj" language="de" …
```

## 五、现状与风险

* 已部署：新 `qingjian-server.exe` + `qingjian-settings.exe`；新 TSF DLL 放进安装目录
  （`qingjian_tsf-0.1.5.dll` / `-x86.dll`）但**未注册** —— TSF 与语言无关，注册表 CLSID
  仍指向 0.1.4 DLL，工作正常；要换 TSF 需管理员权限（本机当前非管理员）。
* 德语释义表：`data\generated\glossary-de.qj`（12,240,936 B，157,162 条，**名词带定冠词**，见第七节），
  源数据 HanDeDict（CC BY-SA 3.0）+ german-nouns（CC BY-SA 4.0）；可编辑中间产物在
  `E:\codemain\qingjian-de\de-glossary\`，`%APPDATA%\Qingjian\custom\glossary-de-hd.tsv` 只是转换脚本的输入副本。
  **输入法真正会读的个人释义表是 `%APPDATA%\Qingjian\user-glossary-de.tsv`**（`assembly\mod.rs:144-166`），
  `custom\` 目录下的文件不参与装配，改它没用。
* 原版 0.1.4 二进制备份：`backup-0.1.4-20260926-220630\`；本轮改动前的释义表/配置备份：`backups\`。
* **官方更新器本来只提示、不自动下载安装**（`crates\qingjian-update\src\lib.rs`：把版本索引写进
  `%APPDATA%\Qingjian\update.json`，菜单/设置「关于」页读它），而且目前更新通道无新版本；
  按用户要求，每日检查也已关掉（`config.toml` 的 `[update] check = false`，设置页「立即检查」仍可手动用）。
  万一日后手工更新覆盖了 server/settings，`pwsh -File E:\codemain\qingjian-de\redeploy-de.ps1` 一条命令装回来（装完自动体检）。
* 个人释义表 `%APPDATA%\Qingjian\user-glossary-de.tsv` 已建好并**验证生效**（`layered_translator.rs:40-44`：
  个人表优先，查不到才查随包表；`assembly\mod.rs:144-166` 按 `user-glossary-<语言>.tsv` 打开）。
  现在就一条 `便宜	adj. billig; preiswert; günstig`，覆盖了随包表里 HanDeDict 的第一义项 `geeignet`。
  **以后看到哪条德语不对，往这个文件加一行 `词<TAB>[词性. ]译词` 再重启 Server 就行**；
  格式与随包表相同（写出格式见 `personal_glossary.rs:98-115`），坏行只警告跳过，不影响其它词。

## 六、重大修复：老 TSF DLL 不认识 `German`（2026-09-26 23:21）

**症状**：换上带德语的 server 后，用户报「好多字打了不显示，打不出来汉字，前面英文后面中文」。

**根因**（证据在 DLL 侧日志 `%LOCALAPPDATA%\Qingjian\logs\tsf.<日期>.log`）：

```
2026-09-26 23:18:48.538 [pid 6044] 转发按键失败，放行并断开，下一键重连:
  codec: json: unknown variant `German`, expected one of `Chinese`, `English`, `Japanese`, `Spanish` at line 1 column 270
```

Server 下发的帧里 `Candidate.translation.language` 序列化成 `"German"`，而**安装的 0.1.4 TSF DLL** 的
`Language` 枚举只有中英日西 → 整条 JSON 反序列化失败 → DLL 放行按键并断开重连 → 「打不出汉字、只出英文、丢键」。
`crates\qingjian-platform\src\protocol\mod.rs` 的注释早就警告过这一类坑（加枚举变体必须 +1 版本并重装 DLL）。

**修复**（两处，已构建部署）：

1. `crates\qingjian-platform\src\protocol\mod.rs`：`PROTOCOL_VERSION` 7 → **8**。
2. `apps\windows\server\src\dispatch\composed\mod.rs` 的 `downgrade_for_old_dll()`：对协议 < 8 的 DLL，
   除 `PreeditKind::AuxCode`→`Typed` 外，再把 `frame.candidates.items[*].translation.language`
   从 `German` 改写成 `English`（**只是记号**；译文文本照旧德语，DLL 是纯渲染端不读该字段，
   候选窗由 Server 自绘，自绘路径 `self_drawn_frame()` 不降级，显示不受影响）。
   这样**不重装 DLL 也能打字**，德语译文照常显示。

**无 GUI 验证** `probe-dll.ps1`（假 DLL，命名管道 4 字节长度前缀 + JSON）：

```powershell
pwsh -File E:\codemain\qingjian-de\probe-dll.ps1 -Protocol 7 -Keys nihao   # 老 DLL：帧里 "German"=0，"English"=23，译文文本仍是 "Hallo!"
pwsh -File E:\codemain\qingjian-de\probe-dll.ps1 -Protocol 8 -Keys nihao   # 新 DLL：帧里 "German"=17（降级只对老 DLL 生效）
```

server 日志同时出现预期警告：`DLL 与 Server 的协议版本不同（应用还没重启、用着旧 DLL？），照常服务 … dll=7 server=8`。

**中间版本备份**：`qingjian-server-v7-protocol.exe.bak`（含德语但协议 7，会触发本 bug，别回滚到它）。

## 七、本轮改进（2026-09-26 23:31）

### 1. 名词加定冠词（德语表可用性）
HanDeDict 只给词义、不给性，`n. Schule` 这种写法对学德语的人没用。做法：
`de-glossary\add_articles.py` 用 `gambolputty/german-nouns`（取自德语维基词典，CC-BY-SA-4.0，
`de-glossary\gender\nouns.csv` 20 MB）给 `n. ` 行里的**裸名词片段**加 der/die/das：只改释义文本、
不动词条与顺序；括号里的补充说明、多词短语、全大写缩略语（源表把 `CT` 记成阴性）一律不加 —— 宁可不加，不加错。
结果：157,162 行改动 38,241 行。样例：

```
学校        n. die Schule
汽车        n. das Auto, Wagen, der Kraftwagen, das Automobil, das Kraftfahrzeug
X射线断层扫描仪  n. der Computertomograf, CT
七情        n. die sieben menschlichen Gemütsregungen (Freude, Zorn, …)   ← 括号里不动
```

用**官方打包器** `qingjian-dict-convert pack glossary`（`tools\dict-convert`，`pack-de.cmd` 构建）打成
`glossary-de.qj`（12,240,936 B，`entries=157162`），元数据写进容器 META：
`name = "青简德语释义（HanDeDict + german-nouns）"`、`license = "CC-BY-SA-4.0"`、两份来源署名 +
`generator = "qingjian-dict-convert 0.1.1"`。

### 2. `chinese_first = true`
用户最初的抱怨「前面显示的是英文，后面显示的是中文」对应 `chinese_first` 缺省关
（`crates\qingjian-platform\src\config\general.rs:57-59`：拼音不像话的输入英文词排第一）。
已在 `%APPDATA%\Qingjian\config.toml:29` 打开（备份 `backups\*.bak`），改回 `false` 即恢复原行为。

### 3. 一条命令体检 / 重装
* `verify-de.ps1`：二进制 SHA256 与套件对比（兜底看补丁特征字符串）、释义表在不在且是带冠词版、
  `learning_language = "de"`、Server 进程、以及用假 DLL 走协议确认候选帧里有 `die Schule`。
* `redeploy-de.ps1`：官方更新覆盖之后一条命令装回来（含后述 mmap 循环 + 自动体检）。
* `dist\qingjian-de-kit\`（147.9 MB）已刷新：新释义表 + 加冠词 TSV + german-nouns.csv + `levels\levels-de.tsv`
  + Goethe 词表 + 全部脚本 + 源码 diff。

### 4. 踩到的坑：`.qj` 是 mmap 打开的，而且 Server 会被自动拉起来
直接覆盖 `glossary-de.qj` 会失败：`请求的操作无法在使用用户映射区域打开的文件上执行。`
（ERROR_USER_MAPPED_FILE）。Server 用 mmap 读 `.qj`；更麻烦的是**输入法宿主进程会在 Server 被杀后
立刻再拉起一个**（tsf 日志里的 pid，如 6044 → 新 server 25248），新进程马上又把文件 map 住。
所以换表/换 exe 必须是「杀 → 立刻复制 → 失败就重试」的循环（`redeploy-de.ps1` 的 `Copy-Live`，最多 12 次）。

### 5. 德语词汇等级表 `levels-de.tsv`（生词分级，2026-09-26 23:44）
**先搞清楚语义**：青简是按**整条释义文本**记学习记录的 ——
`crates\qingjian-core\src\engine\learning\mod.rs:52-67` 用 `(translation.language, sense.text)` 当 key
（`die Schule` 整串），统计页 `crates\qingjian-learning\src\vocabulary_book.rs:150` 拿同一个串查
`LevelTable::rank`（`crates\qingjian-translate\src\level_table.rs:73-84` 只做小写化 + 日文词尾回退）。
所以等级表的键必须是**整条德语释义**（小写），不是汉语词 —— 上游英文表因此只在单词典释上命中
（实测 232,213 行整串命中 23,124 ≈ 10%），而 `der Straßenverkehr` 这种多词释义上游根本没法覆盖。

做法（`de-glossary\levels\`）：
* 数据源：Goethe-Institut 5,000 词表 `20260716200932-goethe-german-5000.de.tsv`（MIT，5,010 行，A1/A2/B1/B2+，
  列含 `Word / Sense / Part of Speech / Level`），已存进套件 `sources\`。
* `build_levels_de.py`：词形表 11,105 条（原形 + 变位 + 带/去冠词，同形取最易级），对每条德语释义按
  ①整串 → ②第一个片段（去括号、去冠词变体）→ ③`(` 之前**第一个**命中的实词（跳过 der/die/das/ein…）
  匹配；多给的 TSV 参数会并入（已把 `user-glossary-de.tsv` 也算上）。
* 结果：**36,560 / 157,163 条（23.3%）能定级**（整串 9,614 / 第一片段 5,667 / 兜底 28,947；未命中 112,935），
  A1 14,197、A2 4,874、B1 11,309、B2+ 6,180。抽样：`你好/学校/汽车/电脑/银行/商店/老师/睡觉` A1、
  `医院/高兴/中国/东西` A2、`漂亮` B1。未命中多是专名与日期（`007岛`、`100米赛跑`、`10月31日`）以及
  多词释义（`交通 → der Straßenverkehr`）。对照脚本 `coverage_compare.py`：英文表若按「任意词」匹配能到 69.4%。
* 已装 `D:\application\Qingjian\assets\levels\levels-de.tsv`（1,147,033 B，36,560 行，UTF-8 无 BOM + LF），
  重启 Server（PID 53588）后日志无 `词汇等级表读不了` → 解析通过。**没有这张表也能正常显示德语译文**，
  它只决定统计页的 A1/B1… 标记与「生词」筛选。

### 6. 用 DeepSeek 补词库缺口（2026-09-27 00:06）
**缺口口径**：不是跟英文表比，而是跟**输入法自己的词库**比 —— `assets\lexicon\dict.tsv` 有 92,825 个词，
德语表只有其中 43,709 个 → **48,210 个词打出来没有德语译文**（45,134 个有英文释义可当提示）。
按词频降序：≥10000 的 756 个、≥1000 的 7,325、≥100 的 25,317、≥10 的 40,613、更低的 7,597；
最高频的全是 HanDeDict 不收的虚词/短语（`了` 词频 5,314,932、`吗`、`呢`、`嘛`、`都是`、`不会`、`你是`…）。

工具 `de-glossary\llm_fill.py`（清单=词库减德语表、按词频降序；英文释义当提示；输出 `词\t词性. 释义`）：
* **关键坑**：`deepseek-v4-flash` 默认开思维链 —— 不关掉时 `reasoning_tokens` 吃满 `max_tokens`、
  `message.content` 返回**空串**（`finish_reason: "length"`）。必须带 `"reasoning_effort": "none"`。
* 词性只用青简代码里的 12 个（`crates\qingjian-core\src\candidate\part_of_speech.rs:8`），
  名词强制 der/die/das；模型漏冠词时用 `gender\nouns.csv` 兜底补（`with_articles()`），补不上才丢弃；
  疑似照抄英语提示的条目会退回严格重试。
* 结果（两轮）：48,210 词里 **第一轮 43,922 词（91.1%）**；剩下的 4,288 个用放宽规则再跑一轮
  （`--relaxed --skip llm-fill.tsv`）又补回 **3,510 词**，合计 **47,432 / 48,210 = 98.4%**。
  **词库整体覆盖率：92,826 个词里 92,044 个（99.2%）有了德语译文**（补前只有 43,709 个），剩 782 个。
  放宽的两条是：① 数量短语收（`一年 → n. ein Jahr`、`两天 → n. zwei Tage`，原来被「名词必须有
  der/die/das」的规则误杀）② 专名收（`青岛 → n. Qingdao`、`长沙 → n. Changsha`），专名上多余的冠词
  由 `postprocess.py` 去掉（3,762 条 `n. der Nick` → `n. Nick`）。剩 778 个词是词库里的碎片与
  罕见专名（如 `尔茨州`、`月至`），宁缺勿错。
* 合并 `merge_glossary.py`（HanDeDict 条目优先）→ `glossary-de-merged.tsv` 204,594 行，
  用官方 `qingjian-dict-convert pack glossary` 打包 → `glossary-de.qj` **14,939,408 B / 204,594 条**
  （最初 12,240,936 B / 157,162 条），已装进安装目录（Server PID 27644）。
  验证：`qingjian-cli` 加载 `glosses=204594`；`了 → part. Aspektpartikel`、`一年 → n. ein Jahr`、
  `青岛 → n. Qingdao`、`交通 → n. der Straßenverkehr`；协议探针（老 DLL）全部命中（第 5 节探针全 OK）。
* 质量抽样（用户可见）：好的如 `画作 → n. das Gemälde`、`装嫩 → v. sich jünger geben`、
  `英雄联盟 → n. das League of Legends`、`一年 → n. ein Jahr`、`青岛 → n. Qingdao`；词库里本身是词片段的
  会得到机械译文（`都会 → n. die Metropole` 走的是「都会 dūhuì」这个义项，而词库里它是「都+会」；
  `茵兰 → n. Finnland` 是 `莱茵兰` 的碎片），这类片段本来就只占低频尾部。

### 7. 第三轮：冠词二轮修 4,876 行 + 短语轮补 632 条（2026-09-27 01:21）
**冠词二轮**（新增 `de-glossary\add_articles2.py`）：第一轮只读了 `gender\nouns.csv` 的 `genus` 单列，
而性别还藏在 `genus 1..4` 四列里 —— `心/Herz`、`公里/Kilometer`、`范围/Bereich` 这些全漏；
`Daten`/`Leute` 这类没有性别但有 `nominativ plural`。规则：只给首义里的**单个词**加冠词、
复合词按**末段**判定、复数形走**复数栏**、整词是纯专名（6,232 条）跳过。
结果 **修好 4,876 行**（整词命中 1,621 / 复合词末段 1,780 / 复数栏 1,329 / 复数→die 146）→
`glossary-de-art2.tsv` 204,594 行；缺冠词的名词首义 45,198 → 40,611。
抽查：`心 → n. das Herz`、`公里 → n. der Kilometer(km, eine Längeneinheit)`、`数据 → n. die Daten`、
`列车 → n. der (Eisenbahn-) Zug`；`尔茨州 → n. Hessen`、`阿布 → n. Abu`、`辛醇 → n. Octanol` 正确地不加冠词。

**短语轮**（`llm_fill.py --phrase`）：剩下 778 个缺口词里高频的几乎全是短语
（`你家` 36,494、`多人` 26,823、`该国` 24,156、`五年`、`我朋友`、`梦里`），
提示词改成「按短语/固定搭配写 `phr.`、不硬套名词冠词」→ **566 条**（13 秒，33,222 prompt / 9,790 completion tokens）：
`你家 → phr. dein Zuhause`、`该国 → phr. dieses Land`、`五年 → phr. fünf Jahre`、`梦里 → phr. im Traum`。
再补 `--no-hint`（去掉英语提示，专治「照抄英语就退回」）：严格轮把 `生死 → life and death` 判为照抄英语丢弃，
去掉提示后模型自己写德语 → **66 条**：`生死 → phr. Leben und Tod`、`军民 → phr. Militär und Zivilbevölkerung`、
`炒粉 → phr. gebratene Reisnudeln`、`右下 → phr. rechts unten`。

**合并部署**：`glossary-de-art2.tsv` + `llm-fill-phrase.tsv`(632) = `glossary-de-merged.tsv` **205,226 行**
→ 官方打包器 → `glossary-de.qj` **14,995,680 B / 205,226 条**（sha256 `2744567d…`）
→ 装进 `D:\application\Qingjian\data\generated\`（Server PID 46600）。
验证：CLI `glosses=205226`、`你好 → int. Hallo!`（`translate 24µs (43/44 hit)`）；
协议探针（`-Protocol 7` 老 DLL）`心 → das Herz`、`数据 → die Daten`、`你家 → dein Zuhause`；
`verify-de.ps1` 结论「通过（0 条提示）」。剩 146 词是词库碎片（`接科雷`、`仆寺少卿`）与罕见专名，不再补。
体检工具 `audit.py`：205,226 行、重复 0、空释义 0、`BOM=False`、`CR=0`。

**仓库展示升级**（`github.com/aolingge/qingjian-german`，分支 `german`，提交 `977bf9f`）：
README 重写（真机截图 `docs/screenshots/qingjian-german-candidates.png`、真实运行记录、数据表、
补词流水线、已知限制）、新增 `CHANGELOG.md`、补齐 `add_articles2.py`/`audit.py`/`article_gap.py`、
刷新 `data/` 与 `dist/glossary-de.qj`；Release `v0.1.5-dev-german` 资产换成 205,226 条版。

### 8. 第四轮：全表质检 + 缺口归零 + CEFR 全量分级（2026-09-27 02:05）

新增 `de-glossary\llm_tools.py`（六个子命令 `gap` / `articles` / `cefr` / `audit` / `levels` / `report`，
8 并发、按 `# batch N` 断点续跑，日志 `_run-*.log`）与 `de-glossary\apply_fixes.py`（四条过滤器 + `--apply`）。

**四阶段结果**（全部 0 失败）：
* `gap`：词库缺德语的词 → `llm-gap.tsv` **147 条**（`爱奇艺 → iQIYI`、`戴高乐 → de Gaulle`、`雄安 → Xiong'an`）；
  最后补的 `阜新市 → n. die Stadt Fuxin` 让 `dict.tsv` 覆盖率到 **92,825 / 92,825 = 100.00%**。
* `articles`（817 批）：名词首义补冠词 → 40,643 条（der 10,151 / die 16,887 / das 7,665 / none 5,940）。
* `cefr`（1,796 批）：德语实词 → CEFR → 107,687 条（A1 461 … C2 2,991）。
* `audit --only llm`（1,603 批）：审前三轮 LLM 行（47,432 行）→ 14,646 条（约 30%）。
  首版提示词太宽（复述原文都报），改窄成「只报意思明显不符 / 碎片 / 占位符」才可用。

**合并落地**（`apply_fixes.py --apply`）：清垃圾 40 行（`*** löschen`、`n. ???`）、新增缺口词 147、
补冠词 34,703（跳过 5,940）、质检修正 3,692 —— 忽略「复述原文」10,651 条，拒绝 303 条
（只换冠词 76 / 改词性 105 / 臆改专名 122 / 冠词表否决 0）→ `glossary-de-final.tsv` **205,333 行**，
`apply-report.txt` 38,885 条改动记录。四条过滤器针对的是「LLM 质检顺手改坏本来正确的词条」：
`艾莎 Elsa → Aisha`、`福瑞 → Furry`、`鸭苗 das Entenküken → die Entenküken`、`田子 das Feld → der Sohn`。
前三轮抽样损坏率约 15%，加过滤器后约 5%（`田子` 这类残余仍需人工复核）。

**等级表重建**（`llm_tools.py levels` 取代旧 `build_levels_de.py`，Goethe-only 36,560 键）：
词典 = Goethe 词形 11,106 + `llm-cefr.tsv` 107,687 = 118,791；每条释义取**第一个有等级的实词**
（冠词后的中心词），复合词按 `-`/`‐`/`–` 从后往前退化命中，仍不中且长度 ≥8 时逐位取后缀；
兜底：无实词按 A1、有实词但没等级按 B2 → `levels-de.tsv` **165,143 键 / 4,154,600 B**
（A1 27,519 / A2 14,984 / B1 26,921 / B2 36,486 / C1 22,262 / C2 36,971）。

**打包部署验证**：新增 `pack-glossary.ps1`（参数 `$Input` 撞 PowerShell 自动变量导致
`Test-Path` 报 “Cannot bind argument to parameter 'LiteralPath' because it is an empty string.”
→ 改名 `$InputTsv` + `[Alias('Input')]`，一条命令打包 + 部署 + 打印 sha256）
→ `glossary-de.qj` **15,155,200 B / 205,333 条**（sha256 `C12F5693…54AF`）装进
`D:\application\Qingjian\data\generated\`；`levels-de.tsv` 装进 `assets\levels\`（旧表备份 `.bak-20260927`）。
`verify-de.ps1` 结论「通过（0 条提示）」：引擎 `glosses=205333`、协议探针 `学校 → die Schule`。

**开机自检**：`selfcheck.ps1`（延迟 20 秒跑 `verify-de.ps1`，写 `logs\selfcheck-<date>.log` 与
`selfcheck-last.txt`，失败弹 WScript.Shell 弹窗 180 秒）+ `register-selfcheck.ps1`
（计划任务 `QingjianGermanSelfCheck`，登录后 30 秒触发，`-RunNow` / `-Status` / `-Remove`）。
已注册并试跑成功（LastTaskResult 0）。`verify-de.ps1` 也新增「2b. 引擎能加载这份词表」
（用套件 `bin\qingjian-cli.exe` 直接查 `xuexiao` 必须是 `die Schule`）。

### 9. 第五轮：常用义修正 14,422 条 + CEFR 170,638 条（2026-09-27 12:10）

起因：HanDeDict 有些词只留了生僻义项 —— `权利` 是 `die Anwartschaft`（请求权）、`便宜` 是 `geeignet`（合适）。
青简自带**英语**表 `assets\glossary\glossary-en.tsv`（232,213 行，一个词可有多条义项、行内 TAB 分隔、带词性前缀）
是现成的第二意见。

**sense 阶段**（`llm_tools.py` 新增 `sense` 子命令，2,938 批 / 0 失败）：只对德语 ∩ 英语 ∩ 词库的
**88,112 个词**提问，提示里给英语表全部义项，只让它报「常用义明显不对」的行 → `llm-sense.tsv` **36,418 条**（41%）。
小样显示大量标记其实是「顺序不同但已有该义」（`但`/`现在`/`今天`）或词性归属问题（`在`/`为`/`于`/`以`/`跟`
被 HanDeDict 记成 `v.`/`n.`），所以不能整体替换。

**落地规则**（`apply_fixes.py` 新增第 4 段「常用义修正」，仍默认干跑、`--apply` 才写）：
1. **词频 <100 一律不动**（跳过 16,224 条）：生僻词没有第二意见、错了也没人用
   （代价是连 `憋闷 → bedrückt; beklommen; stickig` 这种合理建议也放过）；
2. **只增不删**：新义项去掉旧表已有的重复后**插到最前**，旧义项全部保留 → 采纳 **14,422 条**
   （`权利 → das Recht; der Anspruch; die Anwartschaft`、`军人 → der Soldat; der Angehöriger des Militärs`、
   `便宜 → billig; preiswert; günstig; geeignet`）；
3. **词性变更要英语表佐证**（新词性 ∈ 英语表该词词性集合、旧词性 ∉、词频 ≥1000）→ 通过 716 条
   （`跟 n. die Ferse → prep. mit; und`）、拒绝 1,709 条；
4. **冠词表一票否决**：新义项冠词与 `add_articles2` 冠词表整词命中结果不一致 → 丢掉 225 条（`垂水` 等）。
`apply-report.txt` 现在 **77,047 行**（`[冠词]` 34,703 / `[常用义]` 13,706 / `[修正]` 3,692 / `[新增]` 147 /
`[拒绝·…]` 2,012 / `[清垃圾]` 40）。抽样：采纳的多数合理（`腰斩 → halbieren`、`裤脚 → das Hosenbein; der Hosensaum`、
`苗条 → schlank; schmal; zierlich`），仍有词频过线被硬猜的（`森饰 → der Waldschmuck; Mori Shiki`）。

**等级表重建**：新增月份 / 星期 / 季节 / 度量衡的 A1–A2 兜底词表，复合词退化阈值 5 → 4 字符 →
`levels-de.tsv` **170,638 键 / 4,578,096 B**（A1 28,605 / A2 15,930 / B1 28,977 / B2 38,108 / C1 22,328 / C2 36,690）。
运行时按释义整串小写精确查表，**205,333 行命中 100%**；11,649 条没有可靠依据（日期 / 单位 / 化学名）走 B2 兜底。

**打包部署验证**：`glossary-de.qj` **15,490,832 B / 205,333 条**（sha256 `E1908475…AC34E`）与 `levels-de.tsv`
都已装到安装目录（`D:\application\Qingjian\data\generated\` 与 `assets\levels\`）；`verify-de.ps1`
结论「通过（0 条提示）」——引擎 `glosses=205333`、协议探针 `学校 → die Schule`；
CLI 抽查 `权利 → das Recht; der Anspruch; die Anwartschaft`、`跟 → prep. mit; und`。

**修了一个坑**：`verify-de.ps1` 的 2b 段偶发报「词表加载条数不对」—— `qingjian-cli` 的 `glosses=…`
是 **INFO 级日志**，只有 `RUST_LOG=info` 才打印；脚本现在在调用前后临时设置 / 还原该变量。

**仓库同步**：`german` 分支提交 `f094e27`（已推 fork），Release **`v0.1.7-dev-german`** 挂
`glossary-de.qj`（15,490,832 B）+ `.sha256` + `levels-de.tsv`；套件 `dist\qingjian-de-kit` 重建
（199,585,750 B / 190.3 MB，`notes\reinstall.txt` 数字已更新，密钥扫描 0 命中，`sources\NOTES-llm-fill.md`
补齐第四、五轮）；
`german\README.md` / `CHANGELOG.md` / `data\NOTES-llm-fill.md` 都补了第五轮（含已知限制里等级表口径改写）。

### 10. 第六轮：自检修复 —— 中文残留 / 冠词硬错 / 定级补到 100%（2026-09-27 12:30）

前五轮都是「让 LLM 改表」，从没人系统性查过表本身。这一轮先写体检脚本，再按结论修。

**体检脚本** `de-glossary\audit_final.py`，五项：
① 运行时等级查表覆盖率（复刻 Rust 的 `parse_sense`）② 德语正文里的 CJK 残留 ③ 非法词性前缀 / 空正文
④ 冠词与 `german-nouns` 冲突（整词同形、排除复数写法）⑤ 词性分布。
跑法 `python audit_final.py glossary-de-final.tsv levels\levels-de.tsv gender\nouns.csv`。

**先修的是脚本自己**：一开始把 `M.` 当非法词性、把复数名词（`die Möbel`、`die Stiefel`）报成冠词冲突 →
误报 117 条。原因是 Rust 的 `PartOfSpeech::from_str`（`crates\qingjian-core\src\candidate\part_of_speech.rs:75-95`）
会 `to_ascii_lowercase()` 并接受别名 `noun/verb/interj/phrase/mw`，`M.`（量词）其实合法；
`german-nouns` 的复数在 `nominativ plural` 列（表头 `lemma,pos,genus,…,nominativ plural`），`genus` 值是 `m/f/n`。
对齐后**冲突只剩 14 条，逐条看全部合理**（`die PIN`、`die ETA`、`der Hähnchenflügel`、`die Elbe`、`der Pi`…）。

**修掉的硬错（共 57 条）**：
* 中文残留 2 条：`凉凉送`、`凉送给` 的正文是 `v. (网络用语) 冷落、忽视` → `v. (Netzjargon) jdn. links liegen lassen, ignorieren`。
  `apply_fixes.py` 质检段新增「中文残留守卫」（旧正文无 CJK、提案含 CJK → 拒绝，共拦下 13 条）。
* 冠词硬错 41 条（人工核对后写进 `de-glossary\fixes.tsv`）：`岁数/年龄/庚/龄/老伴儿 → das Alter`、
  `馋猫 → die Naschkatze`、`午餐肉 → das Frühstücksfleisch`、`蛀牙 → die Karies`、`垫脚石 → das Sprungbrett`、
  `平房 → der Bungalow`、`可丽饼 → der Crêpe` 等。
* 缺词性前缀 1 条：`奈特·沙马兰 → M. Night Shyamalan`（`M.` 会被当量词）→ `n. M. Night Shyamalan`。
* `apply_fixes.py` 新增第 5 段「手工覆盖」（读 `fixes.tsv`，44 条，优先级高于所有 LLM 提案）。

**复检全绿**：定级 **205,333 / 205,333 = 100.00%**；CJK 只剩 4 行且全是谚文注释（`李俊基`、`李多海`、`釜山`、`韩元`）；
空正文 0；无词性前缀 40,095 行（HanDeDict 原生，`10月11日 → 11. Oktober` 这类，无害）；
冠词冲突 14 条全部合理。

**产物与部署**：`glossary-de-final.tsv` 205,333 行 / 7,398,081 B（旧版留 `glossary-de-final.tsv.bak6`）、
`apply-report.txt` 55,286 条、`levels-de.tsv` **170,620 键 / 4,577,613 B**
（A1 28,602 / A2 15,930 / B1 28,970 / B2 38,104 / C1 22,324 / C2 36,690，11,647 条兜底）、
`glossary-de.qj` **15,490,632 B / sha256 `65E213F3…175ED`**；两份产物都已部署。
`pack-glossary.ps1 -Deploy` 顺带部署等级表（旧表自动备份成 `levels-de.tsv.bak-yyyyMMdd-HHmmss`），一条命令搞定。
`verify-de.ps1` → 结论「通过（0 条提示）」，`glosses=205333`、`learning_language=de`、探针 `学校 → die Schule`。

### 11. 还摆着的（没做）
* `便宜 → adj. geeignet`（应为 billig）：HanDeDict 自己的第一义项就是 `geeignet (Adj)`，属上游数据问题，
  整表层面要修得换义项选择依据（按英文表对齐、或按词频挑义项）。**已在个人释义表里单点改成
  `adj. billig; preiswert; günstig` 并验证生效**（见第 5 节末），以后照这个办法加行即可。
* ~~没有 `levels-de.tsv`~~ —— 已做，见第 5、8 小节；第六轮复检后 **205,333 / 205,333 = 100.00%** 的释义都能定级
  （表里 170,620 条，11,647 条按 B2/A1 兜底，数字/日期/化学名这类本来就没有可靠依据）。
* ~~德语表词条缺口~~ —— **已归零**：第四个轮把词库缺口补到 **100.00%**（92,825 / 92,825），
  最后一个词是 `阜新市 → n. die Stadt Fuxin`，见第 6、7、8 小节。
* 多义词义项选择：`都会 → n. die Metropole`（词库里它是「都+会」）、`便宜 → adj. geeignet`（HanDeDict 第一义项）
  都属于「词典式义项挑选」问题，整表层面要修得换依据（按英文表对齐或按词频挑义项）。
* `[predict]` 云联想仍是 `enabled = false`（key 已在 `%APPDATA%\Qingjian\.env` 里，随时可开）。
