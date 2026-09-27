# 德语支持（2026-09-27）

## 起因

青简的「学习语言」原来只有英语 / 日语 / 西班牙语三套释义表，其中西语表是 Azure 机器翻译的直接产物。
德语是第二套**独立做到底**的学习语言：词表不从英语表机翻，而是拿中德词典（HanDeDict）打底，
缺的词用 LLM 按中英词典的口径补，再逐轮质检。成品、工具与踩坑记录都在仓库根的 [`german/`](../../german/README.md)。

## 现在能做什么

- 设置页「学习语言」多出**德语**，候选旁显示德语译词（`xuexiao → n. die Schule`），带 ä/ö/ü/ß。
- 一份 205,333 条的汉德释义表（`german/data/glossary-de-final.tsv`），词库 `dict.tsv` 的 92,825 个词
  **100% 有德语**；名词带定冠词、短语标 `phr.`，词性沿用青简的 12 种。
- 一份 CEFR 等级表（`german/data/levels-de.tsv`，170,620 键），「统计」页按 A1–C2 列生词进度。
- 云联想补词走德语提示词（`GERMAN_SYSTEM_PROMPT`），一条译词最多 40 字符（`MAX_GERMAN_CHARS`），
  保留变音字母，不把 ä/ö/ü/ß 改写成 ae/oe/ue/ss。

## 数据源与许可

| 数据 | 来源 | 许可 |
|---|---|---|
| 中德底表 | [HanDeDict](https://github.com/gugray/HanDeDict) | CC BY-SA 3.0 |
| 名词性别与复数 | [german-nouns](https://github.com/gambolputty/german-nouns) | CC BY-SA 4.0 |
| 补词 / 冠词 / 常用义 / 质检 | DeepSeek（`german/tools/llm_*.py`） | 生成内容 |
| CEFR 等级 | Goethe-Institut 5,000 词表 + DeepSeek 按 Goethe 口径标注 | MIT + 生成内容 |

衍生的 `german/data/glossary-de*.tsv` 与 `german/dist/glossary-de.qj` 整体按 **CC BY-SA 4.0** 发布，
署名细节见 `german/NOTICE.md`。上游数据源登记在 [landscape.md](../design/landscape.md) 的「数据源」表。

## 生成流水线

`german/tools/` 下的 Python 脚本按轮次跑，每轮都支持断点续跑，中间产物一律落 `german/data/*.tsv`：

```powershell
python tools\gap_in_dict.py                  # 词库减德语表算缺口（第一轮 48,210 个词）
python tools\llm_fill.py                     # 补词：英语释义当提示，名词强制 der/die/das
python tools\llm_fill.py --relaxed --skip …  # 放宽轮：数量短语、专名也收
python tools\add_articles2.py                # 冠词：german-nouns 的 genus 1..4 兜底 + 复数栏
python tools\merge_glossary.py …             # 合并成待质检的表
python tools\audit.py                        # 体检：重复 / 空释义 / 缺冠词 / BOM / CR
python tools\llm_tools.py gap|articles|cefr|audit|sense|levels   # 第四、五轮的六个阶段
python tools\apply_fixes.py --apply          # 过滤器 + data\fixes.tsv 手工覆盖，落地成最终表
python tools\gaps_now.py …                   # 定级与覆盖率的收尾体检
python tools\junk_scan.py                    # 扫占位符、`*** löschen` 一类垃圾行
```

`apply_fixes.py` 是质量的关键：LLM 质检会顺手动**本来正确**的词（第四轮抽样约 15% 的改动是损坏，
`艾莎 Elsa → Aisha`），所以默认干跑，`--apply` 才写，只采纳同时满足「没只换冠词 / 没改词性 /
不是臆改专名 / 不是复述原文」的提案，`apply-report.txt` 逐条记下拒绝理由。第五轮「常用义」段另有三条：
词频 <100 一律不动、新义项只增不删、改词性必须拿到英语表的词性佐证。第六轮又加了「中文残留守卫」
（旧正文没中文、提案里有 CJK 就拒）与 `data/fixes.tsv` 人工覆盖（优先级最高）。

## 打包与部署

```powershell
powershell -File scripts\pack-glossary.ps1 -Deploy   # 打包 glossary-de.qj 并部署
scripts\verify-de.ps1                                 # 体检：二进制、词表、配置、Server、候选帧
```

`pack-glossary.ps1` 调 `qingjian-dict-convert pack glossary`（`--language de` 决定输出名
`glossary-<语言>.qj`），产物 15,490,632 B、sha256 `65e213f3…175ed`；`-Deploy` 顺便把 `levels-de.tsv`
拷进安装目录的 `assets/levels/`（旧表自动备份）。两种部署位置：

- 词表：`<安装目录>\data\generated\glossary-de.qj`，`config.toml` 里 `learning_language = "de"`；
- 等级表：`<安装目录>\assets\levels\levels-de.tsv`（文件名按 `Language::code()` 拼，Server 启动时加载）；
- 个人释义表：`%APPDATA%\Qingjian\user-glossary-de.tsv`，优先于随包表，覆盖单条用。

`selfcheck.ps1` 把同一套体检包成可重复跑的自检，`register-selfcheck.ps1` 注册成计划任务。

## 等级表格式

`levels-de.tsv` 是「键 → 等级」两列 TSV，前五行是 `#` 注释，第五行是列名：

```
# levels	A1	A2	B1	B2	C1	C2
"100 jahre harmonisches zusammenleben" (glückwunsch zur hochzeit)	A1
(abwehrend) mit der hand winken	A1
```

键是**整条释义的小写文本**：`LevelTable::rank` 按小写精确匹配（`crates/qingjian-translate/src/level_table.rs`），
而词汇记录里存的正是去掉词性前缀的 `sense.text`，所以「`n. die Schule`」查的是 `die schule`。
等级取释义里**第一个有等级的实词**（即冠词后的中心词），复合词从后往前退，
都没有就兜底：没有实词的短语按 A1、有实词但没等级的按 B2。

当前 170,620 键，分布 A1 28,602 / A2 15,930 / B1 28,970 / B2 38,104 / C1 22,324 / C2 36,690；
205,333 行释义运行时**一行不落地全部命中**，其中 11,647 条是上述兜底值。

## 老客户端降级（协议 v8）

`Language::German` 让协议版本从 7 升到 8。老的 TSF DLL 枚举里只有中英日西，收到 `"German"`
会报 `` unknown variant `German` ``，整条帧失败、按键被放行——所以 Server 侧
`downgrade_for_old_dll` 在按协议版本回退时把译文语言记号改写成英语，**文本照旧是德语**。
旧 DLL 只是渲染用的壳，候选窗口由 Server 画，因此不换 DLL 也能正常显示德语译词、不会丢键。

`scripts\probe-dll.ps1 -Keys xin -Expect Herz -Protocol 7` 用假 DLL 走一遍这条路径，确认降级帧里
`"English"` 记号与德语正文（`Herz`）同时在。

## 验证

```powershell
qingjian-cli --dict dict.qj --glossary glossary-de.qj --language de --limit 3 -- nihao
```

启动日志出现 `entries=92825 glossary=…glosses=205333`，候选旁是 `int. Hallo!`；`verify-de.ps1`
把二进制、词表哈希、等级表与配置一次跑完。两个坑：`glosses=` 是 INFO 级日志，要 `RUST_LOG=info`；
CLI 直接给**汉字**会走英语表（拼音路径才查学习语言表）；CLI 的 `--dict` 必须显式给，否则按相对路径找不到。

## 已知限制

- **40,095 行没有词性前缀**（`10月11日 → 11. Oktober`）：HanDeDict 原生写法，青简按「整段就是释义」处理，
  不影响显示与定级，硬加反而写错。
- **11,647 条等级是兜底值**（日期、单位、化学名），统计页不会漏项，但那些词的等级只是默认值。
- 名词首义里还有 15,610 条没有定冠词——日期、数量、技术复合词，本来就不该加 `der/die/das`。
- 词频 <100 的生僻词仍可能取错义项（`都会` 被当成「大都市」而不是「都 + 会」）：第五轮刻意跳过它们，
  没有可靠第二意见、错了也没人用。
- 4 行的德语释义里带谚文注释，是原表（HanDeDict）就有的，不是残留（中文残留会被守卫拦下）。
- 生成词条没有人工逐条校对，语料是词典式的，**不是逐句翻译**。

## 相关

- 成品、完整数据表与踩坑记录：[`german/README.md`](../../german/README.md)
- 构建与部署：[`german/docs/build-and-deploy.md`](../../german/docs/build-and-deploy.md)
- 打包好的词表：<https://github.com/aolingge/qingjian-german/releases/latest/download/glossary-de.qj>
