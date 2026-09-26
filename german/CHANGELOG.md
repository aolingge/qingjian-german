# 改动记录

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
