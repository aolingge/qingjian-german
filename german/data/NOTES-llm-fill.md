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
