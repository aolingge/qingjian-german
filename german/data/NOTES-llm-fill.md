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

## 验证方式
- `qingjian-cli --language de --dict D:\application\Qingjian\data\generated\dict.qj --glossary <qj> --limit 5 -- <拼音…>`，启动日志有 `加载完成 … glosses=N`。
- 装好后 `verify-de.ps1`（探针 + SHA256 + 等级表 + config）。
