# 署名与数据来源（NOTICE）

## 源码
- 上游：`qingjian-team/qingjian` @ `40e3e550425466e6ba9c0a14de3a77ed04862799`，GPL-3.0。
- 本仓库是它的 fork；德语改动在同一许可（GPL-3.0）下发布。完整 diff 见 `german/patch/qingjian-german.patch`。

## 释义表数据（`german/data/glossary-de-*.tsv`、`german/dist/glossary-de.qj`）

| 来源 | 贡献 | 许可 |
| --- | --- | --- |
| HanDeDict（Gábor L. Ugray 及贡献者）commit `39e9cca1d692940fa43035be4e325ca8227f4384` | 157,162 条中文→德语释义与词性 | CC-BY-SA-3.0 |
| german-nouns（gambolputty，数据取自德语维基词典） | 38,241 行名词补 der/die/das | CC-BY-SA-4.0 |
| DeepSeek `deepseek-v4-flash` 生成（脚本 `tools/llm_fill.py`） | 47,432 条 HanDeDict 未收录的高频词 | 由本项目生成 |
| Goethe-Institut 5,000 词表（`voothi/20260716201616-german-5000` 整理） | `data/levels-de.tsv`，36,560 条定级 | MIT |

合并与衍生的结果按 **CC-BY-SA-4.0** 发布（ShareAlike）。词表 META 里也写了同样的署名。

## 生产流程（可复现）

1. `tools/add_articles.py` —— 用 german-nouns 给 HanDeDict 的名词补定冠词
2. `tools/llm_fill.py` —— 用 DeepSeek 补词库缺口（严格轮；`--relaxed` 放宽轮收数量短语与专名）
3. `tools/postprocess.py` —— 合并两轮结果、去掉专名上多余的冠词
4. `tools/merge_glossary.py` —— HanDeDict 条目优先，合并 LLM 条目
5. `qingjian-dict-convert pack glossary --language de` —— 打包成 `glossary-de.qj`
6. `tools/build_levels_de.py` —— 用 Goethe 词表生成 `levels-de.tsv`

## 复现所需原始数据（都在 `german/data/sources/`）

- `handedict.u8` 62,653,479 B（Datenstand 2026-09-25T02:30:02Z）
- `german-nouns.csv` 20,194,356 B（90,993 个词形）
- `goethe-german-5000.de.tsv` 311,584 B

⚠️ 词表文件必须是 **UTF-8 无 BOM + LF**：带 BOM 会让青简报 `load glossary: line 1: missing senses`
并导致整个词库装配失败。