# 改动记录

## 2026-09-27 —— 第八轮：生僻词复核（verify）+ 个人表加词工具

**释义表仍是 205,333 条，其中约 3,300 条译文被复核修正**（`dist/glossary-de.qj` 15,510,104 B，sha256 `c869a59e…`）
**等级表 170,619 → 171,330 条；新增 `tools/add_word.py`（不用重打包就能加词/改词）**

- **起因**：第五轮的常用义修正按 `SENSE_MIN_FREQ = 100` 把词频 ≤100 的 **34,739 条**整批跳过，
  这些生僻词从没被任何模型看过；同时「表里没有这个词 / 这个词译得不好」一直只能靠重新打包解决。
- **新链路 `tools/llm_tools.py verify`**：候选 = 词频 < 100、有合法词性前缀、正文里有德语字母、
  且正文不是 `Eigenname` 标签；批 25、按词频降序。提示词要求**只在「德语释义与中文词明显不符」时出声**
  （不确定就不输出，宁漏勿错）→ `data/llm-verify.tsv`。
  送审 **34,739 条 / 1,390 批 / 0 失败**，回来 **16,135 行**（模型沉默即认为原文没问题），
  真改动 4,241 条；抽样 45 条：约 60% 明显更好（`路标 das → der Wegweiser`、`石磨 der → die Steinmühle`、
  `髑 Schädelknochen`）、约 35% 同义改写、约 5% 可疑。
- **`tools/apply_fixes.py` 新增两条复核守卫**：① 复核阶段不做纯删减（新义项是旧正文子串且长度 ≥3 → 拒绝 291 条）；
  ② 复核阶段不许 DROP（生僻词「删掉」远比「译得糙」糟）。另外质检阶段的「复述原文」不再短路复核阶段的发现。
- **修好三处长假守卫**（冠词证据链，此前「冠词表否决」长期 0 次触发）：① 查名词表前必须先剥掉中心词前的旧冠词
  （否则 `article_for("das Wegweiser")` 永远只回「已有冠词」）；② 新增 `compound_gender()` 复合词退化
  （`Steinmühle → Mühle` = die、`Hähnchenflügel → Flügel` = der）；③「只换冠词」规则只在正文完全相同时
  才拿名词表作证，换掉整个中心词的改动不再被旧冠词误杀（`一揽子 → das Gesamtpaket`、`上标 → das Superskript`）。
- **`data/fixes.tsv` 46 → 162 条**（人工核对，优先级最高）：谚文残留 4 条清理（`李俊基`、`李多海`、
  `釜山 → Busan (Stadt in Südkorea)`、`韩元 → Won (Währungssymbol ₩; …)`）、`本法 → n. dieses Gesetz`
  （原 `n. das Dieses Gesetz…` 语法错）、`司农 → der Landwirtschaftsminister`、`金藏 → der Goldschatz`、
  104 条 `X → n. Eigenname` 补性别、5 条冠词硬错（`冷血动物 der Kaltblüter`、`徭 der Frondienst`、
  `羊皮纸 das Pergament`、`鲋 die Karausche`、`腹足类 der Gastropode`，均经 `german-nouns` 证实）。
- **探针的教训**：`de-glossary/_probe8.py` 五条候选规则里四条被证伪——拿 `german-nouns` 给裸名词补冠词
  **区分不了音译专名与普通名词**（`凯特 → Kate`、`汤姆 → Tom`、`保时 → Porsche`、`鲍勃 → Bob`，
  197 条里真正该补的只有 `司农`、`金藏`）；「正文整段等于英语义项」0 条；「冠词与 `german-nouns` 冲突」
  1,009 条绝大多数是复合词/标题/复数/化学名假阳性 → 仍以 `audit_final.py` 的「可比 20,150、冲突 14」为准。
- **结果**：`glossary-de-final.tsv` 205,333 行 / 7,417,549 B，`apply-report.txt` 59,382 条
  （质检修正 6,948 含复核采纳 3,231、常用义修正 14,419、手工覆盖 151）；
  `levels-de.tsv` **171,330 键 / 4,608,660 B**（A1 28,309 / A2 16,276 / B1 29,479 / B2 38,117 /
  C1 22,433 / C2 36,716，盲兜底 0）；十项复检：覆盖率 100.00%、**CJK 归零**、中文全角标点 0、变音 0、
  格式 0、重复 0、冠词一致 20,136 / 20,150 = 99.93%、等级表 0 重复 / 0 非法 / 0 含 CJK。
- **新工具 `tools/add_word.py`**：`python tools/add_word.py 森饰 甜头 --write --reload` 直接写个人释义表
  `%APPDATA%\Qingjian\user-glossary-de.tsv`（优先于随包表），`--list` / `--no-llm` / `--personal` 可选，
  写前自动备份、`--reload` 重启 Server 重新 mmap，CEFR 用本地 Goethe 表 + `llm-cefr*.tsv` 现算。
  实测 `森饰 → n. der Waldschmuck; Mori Shiki`（C1）、`甜头 → n. die Süße; der Vorteil`（A2）。
- **部署验证**：`scripts/pack-glossary.ps1 -Deploy` → 15,510,104 B / sha256 `c869a59e…fa90`，
  `scripts/verify-de.ps1` 全绿（0 条提示）；CLI 实测 `lubiao → 路标 n. der Wegweiser`、
  `tiantou → 甜头 n. der Vorteil, der Nutzen`、`shangbiao → 上标 n. das Superskript`。
- **修掉自检里的一处偶发误报**：`verify-de.ps1` 第 2b 段原来用 PowerShell 的 `2>&1` 收 `qingjian-cli`
  的输出，native 程序写 stderr 会变成 ErrorRecord、落进管道的时机不受控，于是「引擎加载成功：
  glosses=205333」明明在输出里，脚本却偶发报「词表加载条数不对」——开机自检因此误判过一次。
  现在改成交给 `cmd /c … > 临时文件 2>&1` 再读文件，信息级日志与查询结果一定同时拿到。


## 2026-09-27 —— 第七轮：等级表去掉盲兜底（十项体检 / 每一条都有依据）

**释义表仍是 205,333 条，本轮只改 2 条排版**（`dist/glossary-de.qj` 15,490,632 B，sha256 `fa3e0555…`）
**等级表 170,620 → 170,619 条，盲兜底 11,647 → 0 条**

- **起因**：第六轮把定级覆盖率补到 100%，但那 11,647 条只是「没有依据就按 B2（无实词按 A1）兜底」——
  统计页不会漏项，等级却是默认值。这一轮把这些条目按依据补全。
- **两条新链路**（`tools/llm_tools.py`）：
  - `cefrword`：复现式（`gegessen`）、分词（`entschlossen`）、复合词退化后仍没等级的 **413 个中心词** →
    `data/llm-cefrword.tsv`（批次按内容记账，避免重跑时把新批当成已完成的旧批）。
  - `cefrgloss`：整条目都没有可定级实词的（`nach und nach`、`als ob`、`Eigenname`、`Typ 99`）→
    `data/llm-cefrgloss.tsv`（10,623 条；编号回填，模型不必照抄释义）。
  - `levels` 的定级链变成：中心词 → 复合词退化 → **条目定级** → 「有数字前缀就剥掉数字再试一次」
    （`100-Meter-Hürdenlauf`、`16-Bit-Architektur`，只在真能定级时采信）。
- **口径**：`cefrgloss` 的分只在「释义里确实有德语字母词」时采信；纯数字/型号/符号条目
  （`1 (Num)`、`1961`、`〡〢〣`）没有可学的德语词汇，一律 **A1**，不采信模型给整串编号打的 B2。
- **结果**：`data/levels-de.tsv` 170,619 键 / 4,577,561 B（A1 28,201 / A2 16,175 / B1 29,174 /
  B2 37,790 / C1 22,392 / C2 36,887），运行时查表 205,333 / 205,333 = 100%，**盲兜底 0 条**。
- **体检脚本升级为十项**（`tools/audit_final.py`）：新增全角标点（与正常的弯引号 `People’s` 分开统计）、
  变音字母被写成 `ae/oe/ue`、格式（首尾空白 / 连续空格 / 以逗号分号结尾）、重复行与同词多行、
  等级表自检（重复键 / 非法等级 / 含 CJK 的键）、借词大小写对照。
  - 复检结论：中文全角标点 0、变音字母 0、格式 0、重复 0、等级表 0 重复键 0 非法等级、
    冠词与 `german-nouns` 一致率 **20,103 / 20,117 = 99.93%**（14 条冲突逐条看都合理）。
  - **诚实说明**：德语本土名词的小写**无法自动判定**（形容词跟在冠词后本来就小写，`german-nouns`
    又把 `Klein`/`Für`/`Alt` 收成名词），这一项降级为「借词对照 + 人工抽查」，不再输出成百上千条假阳性。
- **数据修正 2 条**（写进 `data/fixes.tsv`，共 46 条）：`大千世界无奇不有` 的释义里有一个中文全角逗号
  （`Welt，was`）改成半角；`U盘 → der Memory stick` 改成 `der Memory Stick`。
- **文档**：README 的已知限制按新口径重写（不再有 B2 兜底，改为说明纯数字条目按 A1）；
  补词流水线补上第七轮的 23–29 步。

## 2026-09-27 —— 第六轮：自检修复（中文残留 / 冠词硬错 / 定级补到 100%）

**释义表仍是 205,333 条，其中 57 条被纠正**（`dist/glossary-de.qj` 15,490,832 → 15,490,632 B，sha256 `65e213f3…`）
**等级表 170,638 → 170,620 条可定级，运行时命中率补到 205,333 / 205,333 = 100.00%**

- **起因**：前五轮都是「让 LLM 改表」，没人系统性地查过表本身。这一轮先写体检脚本
  `tools/audit_final.py`（五项：定级覆盖率、中文残留、词性前缀 / 空正文、冠词与 `german-nouns` 冲突、词性分布），
  再按体检结论逐项修。
- **发现并修的硬错**：
  - **中文残留 2 条**：`凉凉送`、`凉送给` 的德语正文是 `v. (网络用语) 冷落、忽视`（整段中文）——
    已在 `apply_fixes.py` 加「中文残留守卫」（旧正文无 CJK、提案含 CJK → 拒绝，共拦下 13 条），
    这两条改用 `v. (Netzjargon) jdn. links liegen lassen, ignorieren`。
  - **冠词硬错 41 条**：`german-nouns` 与词表逐词比对后发现 `岁数/年龄/庚/龄/老伴儿` 是
    `der Alter`（错）而不是 `das Alter`、`馋猫` 是 `der Naschkatze`（错）而不是 `die Naschkatze`、
    `午餐肉 → das Frühstücksfleisch`、`蛀牙 → die Karies`、`垫脚石 → das Sprungbrett` 等。
  - **缺词性前缀 1 条**：`奈特·沙马兰 → M. Night Shyamalan`——`M.` 被青简当成量词（合法词性），
    已补成 `n. M. Night Shyamalan`。
  - **落地方式**：新增 `data/fixes.tsv`（44 条人工核对过的覆盖，优先级高于所有 LLM 提案），
    `apply_fixes.py` 多出第 5 段「手工覆盖」。
- **自检口径修正**：`audit_final.py` 最初把 `M.` 当非法词性、把复数名词（`die Möbel`、`die Stiefel`）报成
  冠词冲突，误报 117 条。对齐 Rust 的 `parse_sense`（`PartOfSpeech::from_str` 会 `to_ascii_lowercase()`）
  与 `german-nouns` 的 `nominativ plural` 列后：**冲突只剩 14 条，逐条看全部合理**
  （`die PIN` / `die ETA` / `der Hähnchenflügel` / `die Elbe` / `die Knickerbocker`）。
- **等级表**：键数 170,620（A1 28,602 / A2 15,930 / B1 28,970 / B2 38,104 / C1 22,324 / C2 36,690），
  11,647 条按 B2/A1 兜底；`audit_final.py` 复检 **205,333 / 205,333 = 100.00%**。
- **打包脚本**：`scripts/pack-glossary.ps1 -Deploy` 现在会一并部署 `assets/levels/levels-de.tsv`
  （旧表自动存成 `levels-de.tsv.bak-<日期>`），不必再手动拷等级表。

验证（本机实测）：`audit_final.py` 五项全绿（定级 100%、CJK 仅剩 4 条谚文注释、空正文 0、冠词冲突 14 条全都合理）；
`scripts/verify-de.ps1` → 「通过（0 条提示）」，`glosses=205333`、levels 170,620 条、探针 `学校 → die Schule`。

## 2026-09-27 —— 第五轮：常用义修正（拿英语释义表当第二意见）

**释义表仍是 205,333 条，其中 14,422 条的常用义被校正**（`dist/glossary-de.qj` 15,155,200 → 15,490,832 B，sha256 `e1908475…`）
**等级表 165,143 → 170,638 条可定级**（`data/levels-de.tsv` 4.15 MB → 4.58 MB）

- **问题**：HanDeDict 有些词只给了生僻义项——`权利` 是 `die Anwartschaft`（请求权）而不是 `das Recht`，
  `便宜` 是 `geeignet`（合适）而不是 `billig`。而青简自带**英语**释义表里 `便宜 = adj. cheap / adj. convenient`，
  等于现成的第二意见。
- **做法**（`tools/llm_tools.py sense`）：只对「德语 ∩ 英语 ∩ 词库」的 88,112 个词问 DeepSeek
  「常用义是不是明显不对」，英语表**全部义项**（同一行 TAB 分隔、带词性前缀）作为提示；
  2,938 批 / 0 失败，标出 36,418 条（41%）。
- **落地**（`tools/apply_fixes.py` 新增「常用义修正」段，仍是 `--apply`，默认干跑）：
  - **词频 <100 的一律不动**（跳过 16,224 条）：生僻词没有可靠第二意见，容易硬猜（`森饰 → Waldschmuck`）；
  - **只增不删**：新义项去掉旧的重复后插到最前，旧义项全部保留 → 最终采纳 **14,422 条**
    （`权利 → das Recht; der Anspruch; die Anwartschaft`、`军人 → der Soldat`、`规划 → der Plan; die Auslegung`）；
  - **词性变更要英语表佐证**：新词性在英语表该词的词性集合里、旧词性不在、且词频 ≥1000 才整体替换
    （716 条通过，如 `跟 n. die Ferse → prep. mit; und`；1,709 条无佐证被拒）；
  - **冠词表一票否决**：新义项的冠词与 `add_articles2` 的冠词表整词命中结果不一致的丢掉（225 条）。
- **等级表重建**（`tools/llm_tools.py levels`）：词典扩到 118,791 个词形，新增月份 / 星期 / 季节 / 度量衡
  的 A1–A2 兜底词表，复合词退化阈值 5 → 4 字符，键数 165,143 → **170,638**
  （A1 28,605 / A2 15,930 / B1 28,977 / B2 38,108 / C1 22,328 / C2 36,690）。
  运行时按释义整串小写查表，**205,333 行命中率 100%**；11,649 条没有可靠依据的走 B2 兜底。
- **修坑**：`scripts/verify-de.ps1` 的「引擎能加载这份词表」段偶发失败——`qingjian-cli` 的
  `glosses=…` 是 INFO 级日志，不设 `RUST_LOG=info` 就不打印，脚本现在临时打开并在结束时还原。

验证（本机实测）：`qingjian-cli.exe` 加载安装位词表 `glosses=205333`；`data/levels-de.tsv` 170,638 条已部署；
`scripts/verify-de.ps1` → 结论「通过（0 条提示）」；协议探针（protocol 7）`学校 → die Schule`；
CLI 抽查 `权利 → das Recht; der Anspruch; die Anwartschaft`、`跟 → prep. mit; und`。

## 2026-09-27 —— 第四轮：全表质检 + 缺口归零 + CEFR 全量分级

**释义表 205,226 → 205,333 条**（`dist/glossary-de.qj` 14,995,680 → 15,155,200 B，sha256 `c12f5693…`）
**等级表 36,560 → 165,143 条可定级**（`data/levels-de.tsv` 1.15 MB → 4.15 MB）

- **缺口归零**：`tools/llm_tools.py gap` 补完词库最后 147 个没德语的词
  （`爱奇艺 → iQIYI`、`戴高乐 → de Gaulle`、`雄安 → Xiong'an`、`阜新市 → die Stadt Fuxin`）。
  现在 `dict.tsv` **92,825 / 92,825 = 100.00%** 的词条都有德语译文（第四轮开始时缺 151 个）。
- **名词冠词补全**（`tools/llm_tools.py articles`，40,643 条 → 落地 34,703 条）：
  把 LLM 判定的 `der/die/das` 只插进首义，`none` 的 5,940 条跳过（日期、数字、复数形式）。
- **CEFR 全量分级**（`tools/llm_tools.py cefr`，Goethe 5,000 + LLM 107,687 个实词）：
  取每条释义**第一个有等级的实词**（冠词后的中心词），复合词再按 `-`/`‐`/`–` 从后往前退化命中，
  兜底 A1/B2 让键覆盖率到 100%。分布 A1 27,519 / A2 14,984 / B1 26,921 / B2 36,486 / C1 22,262 / C2 36,971。
- **全表质检 + 四条过滤器**（`tools/llm_tools.py audit` → `tools/apply_fixes.py`）：
  质检提出 14,646 条修改，其中 10,651 条是「复述原文」被忽略；真正落地 3,692 条。
  过滤器拦掉 76 条（只换冠词）、105 条（改词性）、122 条（单拉丁词相似度 < 0.6，防 `Elsa → Aisha` 这类臆改专名）、
  0 条（冠词表否决）。前三轮抽样里约 15% 的改动是损坏，本轮抽样降到 **约 5%**。
- **新增工具**：`tools/llm_tools.py`（gap / articles / cefr / audit / levels / report 六个子命令，
  8 并发、断点续跑）、`tools/apply_fixes.py`（四条过滤器 + `--apply`）、`tools/gaps_now.py`、
  `tools/junk_scan.py`；`tools/llm_tools.py levels` 取代旧的 `build_levels_de.py`。
- **修坑**：`gaps_now.py` 把 `dict.tsv` 开头的 `#` 注释行当词条（少数 3 条「缺口」是假象）；
  `pack-glossary.ps1` 的参数 `$Input` 撞 PowerShell 自动变量导致 `Test-Path` 报空串（改名 `$InputTsv`）。

验证（本机实测）：`qingjian-cli.exe` 加载安装位词表 `glosses=205333`、`glossary-de.qj` entries=205,333
（sha256 与产物一致）；`data/levels-de.tsv` 165,143 条已部署到 `<安装目录>\assets\levels\`；
`scripts/verify-de.ps1` → 结论「通过（0 条提示）」；协议探针（protocol 7）`学校 → die Schule`；
CLI 抽查 `艾莎 → n. Elsa`（臆改 Aisha 被过滤器挡住）。

## 2026-09-27 —— 词表质量二轮 + 仓库展示升级

**释义表 204,594 → 205,226 条**（`dist/glossary-de.qj` 14,939,408 → 14,995,680 B，sha256 `2744567d…`）

- **冠词二轮**（新增 `tools/add_articles2.py`）：性别列原先只读了 nouns.csv 的 `genus`
  单一列，`genus 1..4` 里藏着的 92,210 条（`心`/`Herz`、`公里`/`Kilometer`、`范围`/`Bereich`）
  全漏；再叠加复数形表（82,803 条）与复合词末段判定，修好 **4,876 行**
  （整词命中 1,621 / 复合词末段 1,780 / 复数栏 1,329 / 复数→die 146），纯专名 6,232 条跳过。
- **短语轮**（`tools/llm_fill.py --phrase` / `--no-hint`）：补上 `你家 → phr. dein Zuhause`、
  `五年 → phr. fünf Jahre`、`梦里 → phr. im Traum` 这类高频短语；`--no-hint` 再救回
  `生死 → Leben und Tod`、`攻防 → Angriff und Verteidigung`、`血泪 → Blut und Tränen` 等被
  「照抄英语」规则退回的词，共 **632 条**。
- **覆盖率**：词库 92,826 词里 92,044（99.2%）有德语；缺冠词的名词首义从 45,198 降到 40,611。
- **展示升级**：README 重写（效果截图、真实运行记录、数据表、补词流水线、已知限制、FAQ），
  新增 `docs/screenshots/`、本文件；`tools/` 增补 `add_articles2.py`、`audit.py`、`article_gap.py`。

验证（本机实测）：`qingjian-cli.exe` 加载安装位词表 `glosses=205226`；
`scripts/verify-de.ps1` → 结论「通过（0 条提示）」；假 DLL 协议探针（protocol 7）确认
`心 → das Herz`、`公里 → der Kilometer`、`数据 → die Daten`、`你家 → dein Zuhause`。

## 2026-09-26 —— 首次落地（提交 `0458e7e`、`973afc5`）

- `Language::German` + `PROTOCOL_VERSION` 7 → 8 + `downgrade_for_old_dll()`：
  装好的旧 TSF DLL 收到 `Language::German` 会整条帧反序列化失败、按键全部放行
  （日志：`unknown variant 'German'`），降级成英语标签后恢复正常。
- 释义表：HanDeDict 底表 157,162 条 + 冠词第一轮 + DeepSeek 补词 47,432 条 = 204,594 条。
- 德语词汇等级表 `data/levels-de.tsv`（Goethe 5,000，A1/A2/B1/B2+，36,560 条可定级）。
- 工具链：缺口统计、补词、加冠词、合并、等级表、体检；脚本：构建 / 部署 / 体检 / 协议探针 / OCR。
