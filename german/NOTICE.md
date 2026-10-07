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
| Goethe-Institut 5,000 词表（`voothi/20260716201616-german-5000` 整理） | `data/levels-de.tsv` 的 A1–C1 词形来源（11,106 个词形） | MIT |
| DeepSeek `deepseek-v4-flash` 生成（`tools/llm_tools.py` 的 gap / articles / cefr / audit / sense 五阶段） | `data/llm-cefr.tsv`（107,687 条分级）、`data/llm-sense.tsv`（36,418 条常用义建议）、`data/llm-*.tsv`、`data/fixes.tsv`（44 条人工核对过的覆盖） | 由本项目生成 |

合并与衍生的结果按 **CC-BY-SA-4.0** 发布（ShareAlike）。词表 META 里也写了同样的署名。

## 生产流程（可复现）

1. `tools/add_articles.py` —— 用 german-nouns 给 HanDeDict 的名词补定冠词
2. `tools/llm_fill.py` —— 用 DeepSeek 补词库缺口（严格轮；`--relaxed` 放宽轮收数量短语与专名）
3. `tools/postprocess.py` —— 合并两轮结果、去掉专名上多余的冠词
4. `tools/merge_glossary.py` —— HanDeDict 条目优先，合并 LLM 条目
5. `qingjian-dict-convert pack glossary --language de` —— 打包成 `glossary-de.qj`
6. `tools/llm_tools.py levels` —— 用 Goethe 词形 + LLM 分级结果生成 `levels-de.tsv`（旧 `tools/build_levels_de.py` 只覆盖 Goethe 5,000，已停用）
7. `tools/audit_final.py` —— 五项体检（运行时定级覆盖率 / CJK 残留 / 词性前缀 / 冠词冲突 / 词性分布）
8. `tools/apply_fixes.py` —— 落地 LLM 提案与 `data/fixes.tsv` 人工覆盖（四条过滤器 + 中文残留守卫）

## 复现所需原始数据（都在 `german/data/sources/`）

- `handedict.u8` 62,653,479 B（Datenstand 2026-09-25T02:30:02Z）
- `german-nouns.csv` 20,194,356 B（90,993 个词形）
- `goethe-german-5000.de.tsv` 311,584 B

⚠️ 词表文件必须是 **UTF-8 无 BOM + LF**：带 BOM 会让青简报 `load glossary: line 1: missing senses`
并导致整个词库装配失败。
## 关于仓库里的两份原始数据

`handedict.u8` 与 `german-nouns.csv` 在上游是 CRLF 行尾，本仓库里按 LF 存放（`german/.gitattributes` 声明）——
内容一致，只是行尾不同；解析脚本按行读，不受影响。`.qj` / `.u8` 已标记为二进制，不会被任何转换破坏。
