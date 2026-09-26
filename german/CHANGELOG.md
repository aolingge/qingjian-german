# 改动记录

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
