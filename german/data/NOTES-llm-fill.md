# 德语补词工作笔记（llm_fill）

## 现状
- 目标：给 `assets/lexicon/dict.tsv`（92,825 行，青简自家词库，列 `词\t音节\t词频`）里**没有德语释义**的 48,210 个词补上德语（其中 45,134 个有英语释义可作提示）。
- 现有德语表 157,162 行（HanDeDict + german-nouns 冠词），已有德语释义的 dict 词 43,709 个。
- 英语表 `assets/glossary/glossary-en.tsv` 232,213 行；英德两边词集差别很大（英有德无 180,258；德有英无 105,207），所以不能只按英语表补。
- 词频分布（缺德语的那 48,210 个词）：≥10000 的 756、≥1000 的 7,325、≥100 的 25,317、≥10 的 40,613、<10 的 7,597。
- 高频缺口全是 HanDeDict 不收录的虚词/短语：`了`(freq 5,314,932)、`吗`、`呢`、`嘛`、`都是`、`不会`、`你是`、`不知道`、`不能`、`狗`、`这是`。

## DeepSeek API
- key 在 `C:\Users\aolin\AppData\Roaming\Qingjian\.env`（`QINGJIAN_API_KEY=…`，53 B，无 BOM，icacls 只给当前用户）。
- 模型名 `deepseek-v4-flash`（`GET https://api.deepseek.com/models` 只列 `deepseek-flash`、`deepseek-v4-pro`，但配置里的名字也能调通）。
- **必须带 `"reasoning_effort": "none"`**：这是思维链模型，不关掉时 `completion_tokens_details.reasoning_tokens` 吃满 max_tokens、`message.content` 返回空串、`finish_reason: "length"`。青简 `[predict]` 配置里也是这个值。
- 关掉后：10 个词 ≈ 70 completion tokens、约 3 秒；48,210 词预计几十分钟、成本极低。

## 输出格式（必须与随包表一致）
`词\t词性. 释义`，词性缩写全集 12 个（来自 `crates/qingjian-core/src/candidate/part_of_speech.rs:8` 的 `PartOfSpeech`）：
`n.` `v.` `adj.` `adv.` `pron.` `prep.` `conj.` `num.` `m.` `part.` `int.` `phr.`
解析在 `crates/qingjian-translate/src/glossary/mod.rs:271-290 parse_sense()`：head 以 `.` 结尾且能 parse 才当词性，否则整段算译文（**坏行不会让整表加载失败，但会显示怪**）。
名词必须带 der/die/das（韩德词典那批已用 german-nouns 补过冠词）。

## 结果（2026-09-27 00:11 已部署）
- 严格轮：`llm-fill.tsv`，48,210 词里补上 43,922（91.1%），627 秒 + 108 秒重试，约 190 万 token。
- 放宽轮（`--relaxed --skip llm-fill.tsv` → `llm-fill2.tsv`）：又补 3,510 词，74 秒。
  放宽两条：① 数量短语收（`一年 → n. ein Jahr`、`两天 → n. zwei Tage`）② 专名收（`青岛 → n. Qingdao`）。
- 清洗 `postprocess.py`：两轮合并 → `llm-fill-all.tsv` 47,432 条，去掉专名上多余的冠词 3,762 条。
- 合并 `merge_glossary.py` → `glossary-de-merged.tsv` 204,594 行 → `qingjian-dict-convert pack glossary`
  → `glossary-de.qj` 14,939,408 B / 204,594 条 → 已装 `D:\application\Qingjian\data\generated\`。
- 覆盖：词库 92,826 词里**原本 43,709 个有德语，现在 92,044 个（99.2%）**，只剩 782 个（词库碎片、罕见专名）。
- 验证：`qingjian-cli` `glosses=204594`；`verify-de.ps1` 全 OK；探针 `一年 → ein Jahr`、`青岛 → Qingdao`。

## 第三轮：冠词二轮 + 短语轮（2026-09-27 01:21 已部署）
- **冠词二轮**（`add_articles2.py`，v2）：性别不只在 nouns.csv 的 `genus` 单列，`genus 1..4` 里还藏着 92,210 条
  （`心 → Herz`、`公里 → Kilometer`、`范围 → Bereich` 原先全漏；`Daten`/`Leute` 没有性别但有 `nominativ plural`）。
  规则：只给**首义里的单个词**加冠词、复合词按末段判定、复数形用复数栏、纯专名（6,232 条）跳过。
  结果：修 **4,876 行** —— 整词命中 1,621 / 复合词末段 1,780 / 复数栏 1,329 / 复数→die 146 →
  `glossary-de-art2.tsv`（204,594 行），缺冠词的名词首义 45,198 → 40,611。
- **短语轮**（`llm_fill.py --phrase`）：提示词按「短语/固定搭配」写 `phr.`、不硬套名词冠词 →
  `llm-fill3.tsv` 566 条（13 秒，33,222 prompt / 9,790 completion tokens）：`你家 → phr. dein Zuhause`、
  `该国 → phr. dieses Land`、`五年 → phr. fünf Jahre`、`梦里 → phr. im Traum`。
- **不给英语提示轮**（`--phrase --no-hint`）：严格轮的「照抄英语就退回」规则误伤了 `生死`(life and death)、
  `攻防`、`血泪`、`烟酒` 这类词 —— 去掉英语提示再跑 → `llm-fill4.tsv` 66 条：`生死 → Leben und Tod`、
  `军民 → Militär und Zivilbevölkerung`、`炒粉 → gebratene Reisnudeln`、`右下 → rechts unten`。
- 合并 `glossary-de-art2.tsv` + `llm-fill-phrase.tsv`(632) = `glossary-de-merged.tsv` **205,226 行**
  → `glossary-de.qj` 14,995,680 B / 205,226 条（sha256 `2744567d…`）→ 已装并验证。
- 剩余 146 词基本是词库碎片（`接科雷`、`仆寺少卿`）与罕见专名，不再补。

## 第四轮：质检 + 缺口归零 + CEFR 全量分级（2026-09-27）

工具：`tools/llm_tools.py`（子命令 `gap` / `articles` / `cefr` / `audit` / `levels` / `report`，8 并发、按 `# batch N` 断点续跑）
+ `tools/apply_fixes.py`（四条过滤器，默认干跑，`--apply` 才写）。四阶段全部 0 失败。

- **gap**（1 批）：词库缺德语的词 → `llm-gap.tsv` **147 条**；最后补的 `阜新市 → n. die Stadt Fuxin`
  让 `dict.tsv` 覆盖率到 **92,825 / 92,825 = 100.00%**。
- **articles**（817 批）：名词首义补冠词 → `llm-articles.tsv` 40,643 条
  （der 10,151 / die 16,887 / das 7,665 / none 5,940），落地 34,703 条，`none` 与已有冠词的跳过。
- **cefr**（1,796 批）：德语实词 → CEFR → `llm-cefr.tsv` 107,687 条
  （A1 461 / A2 2,055 / B1 3,502 / B2 6,367 / C1 4,064 / C2 2,991），与 Goethe 5,000 词形合成 118,791 词典供 `levels` 用。
- **audit**（1,603 批，`--only llm`）：只审前三轮 LLM 行（47,432 行）→ `llm-audit.tsv` **14,646 条**（约 30%）。
  首版提示词太宽（复述原文、同义改写都算），改窄成「只报意思明显不符 / 碎片 / 占位符」后才可用。
- **apply_fixes**：清垃圾 40 行（`*** löschen`、`n. ???`）、新增缺口词 147、补冠词 34,703（跳过 5,940）、
  质检修正 3,692 —— 忽略「复述原文」10,651 条，拒绝 303 条（只换冠词 76 / 改词性 105 / 臆改专名 122 / 冠词表否决 0）。
  产出 `glossary-de-final.tsv` **205,333 行** + `apply-report.txt` 38,885 条改动记录。
- **levels**（取代旧 `build_levels_de.py`）：词典 = Goethe 词形 11,106 + `llm-cefr.tsv` 107,687 = 118,791；
  取每条释义**第一个有等级的实词**（冠词后的中心词），复合词按 `-`/`‐`/`–` 从后往前退化，仍不中且长度 ≥8 时逐位取后缀；
  兜底：无实词按 A1、有实词但没等级按 B2。产出 `levels-de.tsv` **165,143 键 / 4,154,600 B**，
  分布 A1 27,519 / A2 14,984 / B1 26,921 / B2 36,486 / C1 22,262 / C2 36,971。
- **打包**：`pack-glossary.ps1`（参数 `$Input` 撞 PowerShell 自动变量 → 改名 `$InputTsv` + `[Alias('Input')]`）
  → `glossary-de.qj` 15,155,200 B / 205,333 条 / sha256 `C12F5693…54AF` → 部署 + `verify-de.ps1` 全绿。
- **教训**：LLM 质检的原始输出不能直接落地。前三轮抽样约 15% 的改动是损坏
  （`艾莎 Elsa → Aisha`、`福瑞 → Furry`、`鸭苗 das Entenküken → die Entenküken`、`田子 das Feld → der Sohn`）；
  四条过滤器后抽样损坏率约 5%，`田子` 这类残余仍需人工复核。

## 第五轮：常用义修正（sense）+ 等级表补兜底（2026-09-27）

起因：HanDeDict 有些词只留了生僻义项 —— `权利` 是 `die Anwartschaft`、`便宜` 是 `geeignet`。
青简自带**英语**表 `assets/glossary/glossary-en.tsv`（232,213 行，一个词可有多条义项、行内 TAB 分隔、带词性前缀）
正好是现成的第二意见。

- **sense**（`tools/llm_tools.py sense`，2,938 批 / 0 失败）：只对德语 ∩ 英语 ∩ 词库的 **88,112 个词**
  问「常用义是不是明显不对」，提示里给英语表全部义项；输出 `词\t词性. 建议义`（1–3 条用 `; ` 分隔，名词必须带冠词）
  → `llm-sense.tsv` **36,418 条**（41% 被标）。注意小样里大量标记其实是「顺序不同但已有该义」（`但`/`现在`/`今天`）
  或词性归属问题（`在`/`为`/`于`/`以`/`跟` 被 HanDeDict 记成 `v.`/`n.`），所以**不能直接整体替换**。
- **落地规则**（`apply_fixes.py` 新增第 4 段「常用义修正」，仍是默认干跑、`--apply` 才写）：
  1) 词频 <100 跳过（16,224 条）：生僻词没有第二意见、错了也没人用。代价是连明显合理的建议也一起放过
     （`憋闷 → bedrückt; beklommen; stickig`、`一股脑儿 → alles zusammen`）；
  2) 只增不删：新义项去掉旧表已有的重复后插到最前，旧义项保留 → 采纳 **14,422 条**
     （`权利 → das Recht; der Anspruch; die Anwartschaft`、`军人 → der Soldat`、`天气 → das Wetter; die Witterung`）；
  3) 词性变更需英语表佐证（新词性 ∈ 英语表该词词性集合、旧词性 ∉、词频 ≥1000）→ 通过 716 条
     （`跟 → prep. mit; und`）、拒绝 1,709 条；
  4) 冠词表（`add_articles2.load_genders`）整词命中结果与新义项冠词不一致 → 丢掉 225 条（`垂水` 等）。
  `apply-report.txt` 现在 **77,047 行**（第四轮 38,885 + 第五轮），四类标记：
  `[冠词]` 34,703、`[常用义]` 13,706、`[修正]` 3,692、`[新增]` 147、`[拒绝·…]` 2,012、`[清垃圾]` 40。
- **levels 重建**：新增月份 / 星期 / 季节 / 度量衡的 A1–A2 兜底词表（`Jahrhundert`、`Kilobyte`、`Lauf` 走 A2），
  复合词退化阈值 5 → 4 字符；键数 165,143 → **170,638 / 4,578,096 B**
  （A1 28,605 / A2 15,930 / B1 28,977 / B2 38,108 / C1 22,328 / C2 36,690）。
  运行时按释义整串小写精确匹配，**205,333 行命中 100%**（11,649 条无可靠依据走 B2/A1 兜底）。
- **打包部署**：`glossary-de.qj` 15,490,832 B / 205,333 条 / sha256 `E1908475…AC34E`；
  `levels-de.tsv` 4,578,096 B；两份产物都已装到本机，`verify-de.ps1` 全绿。
- **质量**：采纳的抽样看着合理（`腰斩 → halbieren; in zwei Hälften teilen`、`裤脚 → das Hosenbein; der Hosensaum`、
  `苗条 → schlank; schmal; zierlich`、`称道 → loben; anerkennen; rühmen`），但也有词频过线仍被硬猜的
  （`森饰 → der Waldschmuck; Mori Shiki` —— 这个词其实只是和制词/人名，`der Waldschmuck` 是字面直译）。
- **坑（新）**：`verify-de.ps1` 的 2b 段偶发失败 —— `qingjian-cli` 的 `glosses=…` 是 **INFO 级日志**，
  只有 `RUST_LOG=info` 才打印；脚本现在在调用前后临时设置 / 还原该变量。
- **坑（旧，重跑仍要注意）**：CLI 用**汉字**直接查（`-- xuexiao` 才是拼音路径），给汉字会走英语表（显示 `[en]`）。

## 验证方式
- `qingjian-cli --language de --dict D:\application\Qingjian\data\generated\dict.qj --glossary <qj> --limit 5 -- <拼音…>`，启动日志有 `加载完成 … glosses=N`。
  （`--dict` 必须显式给，否则按相对路径找 `data/generated/dict.qj` 报 os error 3。）
- 装好后 `verify-de.ps1`（探针 + SHA256 + 等级表 + config）。
- 覆盖统计：`audit.py`（行数/重复/空/缺冠词/BOM/CR）、`gap_in_dict.py`（词库覆盖率）。
- 坑：pwsh 里 `[IO.File]::WriteAllLines('相对路径', …)` 会写到**进程 CWD**（不是 PowerShell 的 `cd` 位置），
  一律用绝对路径。

## 第六轮：自检修复（中文残留 / 冠词硬错 / 定级补到 100%）

前五轮都在「让 LLM 改表」，没人系统性查过表本身。第六轮先写体检脚本 `tools/audit_final.py`（五项），再按结论修。

- **`audit_final.py` 五项**：① 运行时等级查表覆盖率（复刻 Rust `parse_sense`）② 德语正文里的 CJK 残留
  ③ 非法词性前缀 / 空正文 ④ 冠词与 `german-nouns` 冲突（整词同形、排除复数写法）⑤ 词性分布。
  跑法：`python tools\audit_final.py data\glossary-de-final.tsv data\levels-de.tsv data\gender\nouns.csv`。
- **口径坑（先踩后修）**：脚本一开始把 `M.` 当非法词性、把复数名词（`die Möbel`、`die Stiefel`）报成冠词冲突
  → 误报 117 条。Rust 侧 `PartOfSpeech::from_str` 会 `to_ascii_lowercase()`，`M.`（量词）是合法的；
  `german-nouns` 的复数在 `nominativ plural` 列（索引 16，表头 `lemma,pos,genus,…,nominativ plural`），
  `genus` 值是 `m/f/n` 而不是 `1/2/3`。对齐后**冲突只剩 14 条，逐条看全部合理**（`die PIN`、`die ETA`、
  `der Hähnchenflügel`、`die Gastropode`、`die Elbe`、`die Tao`、`der Weiße`、`das Frankolin`、`das Faszikel`、
  `der Gemeine`、`die Knickerbocker`、`das Berberin`、`das Hundert`、`der Pi`）。
- **修掉的硬错（共 57 条进入 `glossary-de-final.tsv`）**：
  - **中文残留 2 条**：`凉凉送`、`凉送给` 的正文是 `v. (网络用语) 冷落、忽视` → 改为
    `v. (Netzjargon) jdn. links liegen lassen, ignorieren`；`apply_fixes.py` 的质检段新增
    「中文残留守卫」（旧正文无 CJK、提案含 CJK → 拒绝，共拦下 13 条）。
  - **冠词硬错 41 条**（逐条人工核对）：`岁数/年龄/庚/龄/老伴儿 → das Alter`、`馋猫 → die Naschkatze`、
    `醋精 → die Essigessenz`、`午餐肉 → das Frühstücksfleisch`、`爵床 → der Akanthus`、
    `湖滨 → das Seeufer`、`独幕剧 → der Einakter`、`升麻 → das Wanzenkraut`、`垫脚石 → das Sprungbrett`、
    `天灵盖 → das Schädeldach`、`益母草 → das Mutterkraut`、`廊檐 → das Vordach`、`炮筒子 → das Kanonenrohr`、
    `复句 → das Satzgefüge`、`猯 → das Wildschwein`、`蛀牙 → die Karies`、`平房 → der Bungalow`、
    `话痨 → die Quasselstrippe`、`瞌睡虫 → die Schlafmütze`、`闲职 → die Sinekure`、`鳊鱼 → die Brasse`、
    `汆子 → die Schöpfkelle`、`蛴螬 → der Engerling`、`瀱 → das Quellwasser`、`马弁 → die Ordonnanz`、
    `卡普 → das Kap`、`广角 → das Weitwinkel`、`可丽饼/法式煎饼/薄饼卷 → der Crêpe` 等。
  - **缺词性前缀 1 条**：`奈特·沙马兰 → M. Night Shyamalan`（`M.` 会被当量词）→ 补成 `n. M. Night Shyamalan`。
  - **落地方式**：新增 `data/fixes.tsv`（44 条，制表符分隔「词<TAB>整条新释义」，优先级最高），
    `apply_fixes.py` 多出第 5 段「手工覆盖」（`import` 都不需要，读表覆盖即可）。
- **复检结果**：定级 **205,333 / 205,333 = 100.00%**；CJK 只剩 4 行且全是谚文注释
  （`李俊基 Lee, Jun-Gi (이준기 …)`、`李多海`、`釜山`、`韩元`）；空正文 0；
  无词性前缀 40,095 行（HanDeDict 原生，`10月11日 → 11. Oktober` 这类，预期且无害）；
  冠词冲突 14 条全部合理。词性分布：`n.` 111,664 / 无 40,095 / `v.` 26,986 / `adj.` 15,398 / `phr.` 7,457 /
  `adv.` 1,922 / `int.` 552 / `num.` 383 / `pron.` 333 / `conj.` 209 / `part.` 155 / `m.` 116 / `prep.` 63。
- **产物**：`glossary-de-final.tsv` 205,333 行 / 7,398,081 B（旧版备份 `glossary-de-final.tsv.bak6`）；
  `apply-report.txt` 55,286 条；`levels-de.tsv` 170,620 键 / 4,577,613 B
  （A1 28,602 / A2 15,930 / B1 28,970 / B2 38,104 / C1 22,324 / C2 36,690，11,647 条兜底）；
  `dist/glossary-de.qj` 15,490,632 B / sha256 `65E213F3…175ED`。
- **打包脚本改进**：`scripts/pack-glossary.ps1 -Deploy` 现在顺带部署 `assets/levels/levels-de.tsv`
  （旧表自动备份成 `levels-de.tsv.bak-yyyyMMdd-HHmmss`），部署从两条命令变一条。
- **坑（复述）**：`llm_tools.py` 的 `POS_PREFIX` 已扩到 Rust 的全别名集
  （`n|noun|v|verb|adj|adv|int|interj|pron|num|prep|conj|part|phr|phrase|mw|m`），别只写 `n|v|…` 那 12 个短写。

## 第七轮：等级表去掉盲兜底（2026-09-27 12:50）

- **动机**：第六轮定级覆盖率是 100%，但其中 11,647 条只是「没有依据就按 B2（无实词按 A1）兜底」。
  第七轮把「没有依据」这件事本身消掉，让每一条都能说出等级是从哪来的。
- **新增两条链路**（`tools/llm_tools.py`）：
  - `python tools/llm_tools.py cefrword --workers 8`：读 `levels/unknown-heads.tsv`（中心词定级失败的复现式
    `gegessen`、分词 `entschlossen`、复合词退化也没中的），批 50，输出 `data/llm-cefrword.tsv`
    —— **413 词 / 9 批 / 0 失败**。
  - `python tools/llm_tools.py cefrgloss --workers 8`：读 `levels/unknown-glosses.tsv`（整条释义都没有可定级实词），
    批 25，编号回填（模型只回 «序号 + 等级»，不必照抄释义），输出 `data/llm-cefrgloss.tsv`
    —— **10,623 条 / 425 批 / 0 失败**。
  - `run_batches(..., marker=...)` 改成**按内容记账**：重跑时新批的 0 不会被当成「旧批已完成」而跳过。
- **定级链**：中心词 → 复合词退化 → **条目定级**（`llm-cefrgloss.tsv`，键 = 释义小写）→ 兜底。
  条目定级只在 `has_letters(释义)` 为真时采信（释义里确实有德语字母词）；纯数字/型号/符号条目
  （`1 (Num)`、`1961`、`〡〢〣`）一律 **A1**，不采信模型给整串编号打的 B2。
- **产物**：`data/levels-de.tsv` **170,619 键 / 4,577,561 B**（A1 28,201 / A2 16,175 / B1 29,174 /
  B2 37,790 / C1 22,392 / C2 36,887）；定级来源：中心词 193,971、条目定级 930、复合词退化 374；
  未定级 10,058 条全是纯数字/符号 → A1。**盲兜底 0 条**。
- **体检脚本升级为十项**：`tools/audit_final.py` 加了全角标点（真中文标点与正常的弯引号 `People’s` 分开算）、
  变音字母写成 `ae/oe/ue`、格式（首尾空白/连续空格/以逗号结尾）、重复行、等级表自检（重复键/非法等级/CJK 键）、
  借词大小写对照。复检：中文全角标点 0、变音 0、格式 0、重复 0、等级表 0 重复 0 非法、
  冠词与 `german-nouns` 一致 **20,103 / 20,117 = 99.93%**。
- **教训（写进 README 已知限制）**：德语本土名词的小写**无法做自动判定** —— 形容词跟在冠词后本来就小写
  （`ein kleiner Teil`、`die drei Punkte`），而 `german-nouns` 把 `Klein`/`Für`/`Alt` 这类专名也收成名词；
  「小写词 ∈ nouns.csv」「表内别处写作大写」两版规则都产生成百上千条假阳性，最后只保留「冠词后的英语借词」这一条
  确定性对照（0 处命中），此前发现的 `U盘 → der Memory stick` 已改成 `der Memory Stick`。
- **数据修正 2 条**（`data/fixes.tsv` 44 → 46）：`大千世界无奇不有` 释义里的中文全角逗号改半角；
  `U盘 → n. der Memory Stick`。`python tools/apply_fixes.py --apply` → `glossary-de-final.tsv` 205,333 行 /
  7,398,080 B（旧版备份 `.bak7`），`apply-report.txt` 55,288 条。
  `scripts/pack-glossary.ps1 -Deploy` → `dist/glossary-de.qj` 15,490,632 B / sha256 `fa3e0555…41EC`，部署后
  `scripts/verify-de.ps1` 全绿（0 条提示）。

## 第八轮：生僻词复核（verify）+ 个人表加词工具（2026-09-27 13:08）

- **起因**：第五轮的 `sense` 只改词频 ≥100 的常用义，词频 ≤100 的 34,739 条从没被任何模型看过；
  同时想给「表里没有 / 译得不好」的单条词一个不重打包的入口。
- **新链路 `python tools/llm_tools.py verify --max-freq 100 --workers 8`**：候选 = `freq < 100`、
  有合法词性前缀、正文里有德语字母（`has_letters`）、且正文不是 `Eigenname` 标签（这些是专名，
  无义可校）；按词频降序，批 25，提示词要求**只在「德语释义与中文词明显不符」时才出声**
  （`VERIFY_SYSTEM`：不确定就不要输出，宁漏勿错）→ `data/llm-verify.tsv`。
  - 结果：送审 **34,739 条 / 1,390 批 / 0 失败**，回来 **16,135 行**（模型沉默 = 认为原文没问题）；
    其中原样复述 11,894 条、真改动 4,241 条。抽 45 条人工看：约 60% 明显更好
    （`路标 das → der Wegweiser`、`石磨 der → die Steinmühle`、`髑 Schädelknochen`、`上标 → das Superskript`）、
    约 35% 同义改写、约 5% 可疑，纯删减（`恪守`、`买卖人`）由守卫拦下。
- **`apply_fixes.py` 新增两条复核守卫**：① 复核阶段不做纯删减（新义项是旧正文子串且长度 ≥3 → 拒绝 291 条）；
  ② 复核阶段不许 DROP（生僻词「删掉」比「译得糙」糟）。质检阶段的「复述原文」不再短路复核阶段的发现
  （`石磨` 就是 audit 说没问题、verify 说冠词错）。
- **顺手修好了三处长假守卫**（冠词证据链）：① `add_articles2.head_token()` 拿到中心词后要先剥掉旧冠词再查表
  —— 否则 `article_for("das Wegweiser")` 永远返回「已有冠词」，导致 `冠词表否决` 规则长期 0 次触发；
  ② 新增 `compound_gender()` 复合词退化（`Steinmühle → Mühle` = die、`Hähnchenflügel → Flügel` = der）；
  ③「只换冠词」规则重写：只在正文完全相同时用名词表作证（`ref == 新冠词` 采纳、`ref == 旧冠词` 拒绝），
  换掉整个中心词的改动不再被旧冠词否决（`一揽子 der Geschäftsbereich → das Gesamtpaket`、
  `上标 der Exponent → das Superskript` 曾因此被误杀）。
- **`data/fixes.tsv` 46 → 162 条**（人工核对过的硬错，优先级最高）：谚文残留 4 条
  （`李俊基 → Lee, Jun-Gi (südkoreanischer Schauspieler)`、`李多海`、`釜山 → Busan (Stadt in Südkorea)`、
  `韩元 → Won (Währungssymbol ₩; die südkoreanische Währungseinheit)`）；`本法 → n. dieses Gesetz`
  （原为 `n. das Dieses Gesetz…`，语法错）；`司农 → n. der Landwirtschaftsminister`、
  `金藏 → n. der Goldschatz`；104 条 `X → n. Eigenname` 补上性别；5 条冠词硬错（经 `german-nouns` 证实）：
  `冷血动物 → der Kaltblüter, wechselwarmes Tier`、`徭 → der Frondienst, die Zwangsarbeit`、
  `羊皮纸 → das Pergament`、`鲋 → die Karausche`、`腹足类 → der Gastropode`。
- **探针的教训**（`_probe8.py` 五条规则里四条被证伪，只读探针不进套件）：拿 `german-nouns` 给裸名词补冠词
  区分不了音译专名与普通名词（`凯特 → n. Kate`、`汤姆 → Tom`、`保时 → Porsche`、`鲍勃 → Bob`，
  197 条里真正该补的只有 `司农`、`金藏`）；「正文整段等于该词英语义项」0 条（没有整条没译的情况）；
  「冠词与 `german-nouns` 冲突」1,009 条里绝大多数是复合词/标题/复数/化学名假阳性
  （`U盘 der Memory Stick` 而 nouns 说 das、`三文鱼 der Lachs` 而 nouns 里只有复数 `Lachstöne`）——
  之前 `audit_final.py` 那套「可比 20,150、冲突 14」才是可信口径。
- **产物**：`apply_fixes.py --apply` → `glossary-de-final.tsv` **205,333 行 / 7,417,549 B**（旧版备份 `.bak8`），
  `apply-report.txt` **59,382 条**；质检修正 6,948（其中生僻词复核采纳 3,231、删减拒绝 291、
  冠词表证实并采纳 41；复述原文忽略 18,542；非法 0、只换冠词拒绝 21、冠词表否决 50、改词性 480、
  臆改专名 180、混中文 18）、常用义修正 14,419、手工覆盖 151。
  `levels` 重建 → `data/levels-de.tsv` **171,330 键 / 4,608,660 B**（A1 28,309 / A2 16,276 / B1 29,479 /
  B2 38,117 / C1 22,433 / C2 36,716；定级来源 中心词 193,615、条目定级 928、复合词退化 602；
  未定级 10,188 全是纯数字/符号按 A1；盲兜底 0）。
- **十项复检**：覆盖率 205,333/205,333 = 100.00%、**CJK 0 行**、中文全角标点 0、冠词一致
  **20,136 / 20,150 = 99.93%（冲突回到 14 条，逐条可辩护）**、弯引号 60、无词性前缀 40,095、
  变音 0、格式 0、重复 0、等级表 171,330 键 0 重复 / 0 非法 / 0 含 CJK。
- `scripts/pack-glossary.ps1 -Deploy` → `dist/glossary-de.qj` **15,510,104 B / sha256
  `c869a59e7149ea91db6b5be188a3135e9f413d64e32ee3b567952a2468d6fa90`**，等级表备份
  `levels-de.tsv.bak-20260927-130840` 后部署；`scripts/verify-de.ps1` 全绿（0 条提示）。
  引擎实测（CLI 输入是拼音）：`lubiao → 路标 n. der Wegweiser`、`tiantou → 甜头 n. der Vorteil, der Nutzen`、
  `shangbiao → 上标 n. das Superskript`、`jichi → 鸡翅 n. der Hähnchenflügel`。
- **新工具 `tools/add_word.py`**（不重打包就能加词/改词）：`python tools/add_word.py 森饰 --write --reload`；
  `--list` 列个人表、`--no-llm` 纯离线查表（随包表 / 个人表 / 词频 / CEFR / 英语义项）、`--personal` 换路径；
  写完先备份 `.bak-时间戳` 再 upsert（保留注释头）；`--reload` 用 `taskkill /IM qingjian-server.exe /F`
  让宿主重新 mmap；CEFR 由本地 Goethe 表 + `llm-cefr*.tsv` 经 `resolve_level()` 算出。
  实测：`森饰 → n. der Waldschmuck; Mori Shiki`（C1）、`甜头 → n. die Süße; der Vorteil`（A2，
  比随包表的 `die Süße` 更全）、`猫猫头 → n. Katzenkopf`、`拜仁慕尼黑 → Bayern München`。
  个人表路径 `%APPDATA%\Qingjian\user-glossary-de.tsv`，由 `layered_translator.rs:40-44` 优先于随包表。
