# 青简 German 学习语言 — build & deploy pipeline

本目录是给《青简》Windows 版加 **德语（de）** 学习语言的本地构建/部署工具链。
安装目录：`D:\application\Qingjian`（原版 0.1.4，官方没有德语，官方更新通道也没有新版本）。

## 一、源码补丁（相对上游）

上游 checkout：`C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926`
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
INFO 加载完成 … glossary=…\glossary-de.qj glosses=157162 …
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

### 7. 还摆着的（没做）
* `便宜 → adj. geeignet`（应为 billig）：HanDeDict 自己的第一义项就是 `geeignet (Adj)`，属上游数据问题，
  整表层面要修得换义项选择依据（按英文表对齐、或按词频挑义项）。**已在个人释义表里单点改成
  `adj. billig; preiswert; günstig` 并验证生效**（见第 5 节末），以后照这个办法加行即可。
* ~~没有 `levels-de.tsv`~~ —— 已做，见第 5 小节（覆盖 23.3%，因为键是整条释义文本）。
* ~~德语表词条缺口~~ —— 已用 DeepSeek 补到 204,594 条、覆盖词库缺口的 98.4%，见第 6 小节；
  剩 778 个词是词库里的碎片与罕见专名，想要可以再放宽规则重跑。
* `[predict]` 云联想仍是 `enabled = false`（key 已在 `%APPDATA%\Qingjian\.env` 里，随时可开）。
