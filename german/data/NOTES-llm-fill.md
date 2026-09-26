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

## 验证方式
- `qingjian-cli --language de --dict D:\application\Qingjian\data\generated\dict.qj --glossary <qj> --limit 5 -- <拼音…>`，启动日志有 `加载完成 … glosses=N`。
  （`--dict` 必须显式给，否则按相对路径找 `data/generated/dict.qj` 报 os error 3。）
- 装好后 `verify-de.ps1`（探针 + SHA256 + 等级表 + config）。
- 覆盖统计：`audit.py`（行数/重复/空/缺冠词/BOM/CR）、`gap_in_dict.py`（词库覆盖率）。
- 坑：pwsh 里 `[IO.File]::WriteAllLines('相对路径', …)` 会写到**进程 CWD**（不是 PowerShell 的 `cd` 位置），
  一律用绝对路径。
