# 青简德语支持（Qingjian German）

[![license: GPL-3.0](https://img.shields.io/badge/code-GPL--3.0--only-blue)](../LICENSE)
[![data: CC-BY-SA-4.0](https://img.shields.io/badge/data-CC--BY--SA--4.0-lightgrey)](NOTICE.md)

给中文拼音输入法 **青简**（[qingjian-team/qingjian](https://github.com/qingjian-team/qingjian)，GPL-3.0）加上
「学习语言 = 德语」的一整套成果：源码改动、**205,333 条**汉德释义表（词库覆盖率 100%、常用义已按英语义项校正）、
德语词汇等级表（**170,638 条释义可分级**）、生成工具，以及构建 / 部署 / 验证脚本。

装完就是这样（真机候选窗口，在 Edge 里输入 `da'jia'hao`）：

![青简德语候选窗口](docs/screenshots/qingjian-german-candidates.png)

| 输入 | 候选 | 候选旁的德语译文 |
| --- | --- | --- |
| `nihao` | 你好 | `int. Hallo!` |
| `dajiahao` | 大家 | `jeder, jedermann, alle` |
| `dajia` | 打架 | `kämpfen, sich streiten` |
| `dajia` | 打假 | `gegen Markenpiraterie vorgehen` |
| `daji` | 打击 | `schlagen; angreifen, bekämpfen, brechen` |
| `xuexiao` | 学校 | `n. die Schule` |
| `qiche` | 汽车 | `n. das Auto, Wagen, der Kraftwagen, das Automobil, das Kraftfahrzeug` |
| `xin` | 心 | `n. das Herz` |
| `gongli` | 公里 | `n. der Kilometer(km, eine Längeneinheit)` |
| `shuju` | 数据 | `n. die Daten` |
| `jiaotong` | 交通 | `n. der Verkehr, Straßenverkehr` |
| `kaifa` | 开发 | `v. erschließen, abbauen, entwickeln` |
| `nijia` | 你家 | `phr. dein Zuhause` |
| `shengsi` | 生死 | `phr. Leben und Tod` |

## 现在能做什么

- 设置页「学习语言」多出 **德语** 选项，候选词旁显示德语译文（含 ä/ö/ü/ß 等变音符号）
- 词库 92,825 个词 **100% 有德语译文**（补词前只有 43,709 个）
- 名词带定冠词（`der Kilometer` / `das Herz` / `die Daten`），短语标 `phr.`，词性沿用青简的 12 种
- 统计页有 A1 / A2 / B1 / B2 / C1 / C2 生词分级（**170,638 条释义**能定级，A1 28,605 / A2 15,930 / B1 28,977 / B2 38,108 / C1 22,328 / C2 36,690）
- 常用义排在前面：`权利` 是 `das Recht; der Anspruch; die Anwartschaft`（原来只有生僻的 `die Anwartschaft`），
  `便宜` 是 `billig; preiswert; günstig`（原来只有 `geeignet`）——第五轮用英语释义表当第二意见校正了 14,422 条
- **不用换 DLL**：安装自带的旧 TSF DLL 不认识 `German` 枚举，Server 侧按协议版本自动降级（协议 7→8），
  旧 DLL 收到的是「英语」标签 + 德语正文，因此不会丢键、不会打不出汉字
- 全离线：释义表是 mmap 的 `.qj` 容器，启动近零耗时；个人释义表 `user-glossary-de.tsv` 可覆盖任意单条

## 快速开始

### A. 已经装好青简（只换词表，最快）

```powershell
copy dist\glossary-de.qj "D:\application\Qingjian\data\generated\"   # 换成你的安装目录
# %APPDATA%\Qingjian\config.toml 里改成：learning_language = "de"
Get-Process qingjian-server | Stop-Process   # 输入法宿主会自动把它拉起来
```

可选：`data\levels-de.tsv` → `<安装目录>\assets\levels\`（生词分级）；
`data\user-glossary-de.tsv` → `%APPDATA%\Qingjian\`（个人释义表，优先于随包表，改单条释义就改它）。

> 注意：设置页能出现「德语」，前提是 `qingjian-settings.exe` / `qingjian-server.exe` 是**带德语支持**的构建
> （上游正式版没有）。二进制不在仓库里 —— 用 Release 里的成品，或按 `docs/build-and-deploy.md` 自己编。

### B. 从源码构建

```powershell
git clone --branch german https://github.com/aolingge/qingjian-german.git
cd qingjian-german
cargo build --release -p qingjian-windows-server -p qingjian-windows-settings
```

本机没有 Windows SDK 时的链接配置、x86 TSF DLL 的交叉链接、`mt.exe` 与图标等坑，全部记在
[`docs/build-and-deploy.md`](docs/build-and-deploy.md)（第二、三节）；`scripts/` 下是可直接复用的包装脚本。

### C. 验证装好了没

```powershell
scripts\verify-de.ps1                     # 一键体检：二进制、词表、配置、Server、候选帧
```

```
$ qingjian-cli.exe --dict dict.qj --glossary glossary-de.qj --language de --limit 3 -- nihao
加载完成 dict=...\dict.qj entries=92825 glossary=...\glossary-de.qj glosses=205226 english=0 learned=0
   1. 你好    int. Hallo!
   2. 你好好  phr. du gut
   3. 你好像  phr. du scheinst
parse 71µs · lookup 52µs · rank 6.30ms · translate 24µs (43/44 hit) · total 6.45ms
```

`scripts\probe-dll.ps1 -Keys xin -Expect Herz -Protocol 7` 用假 DLL 走一遍协议，确认**装好的旧 DLL**
也能拿到 `"language":"English", "text":"das Herz"` 这种降级帧。

## 数据从哪来

| 文件 | 数据行 | 说明 | 许可 |
| --- | --- | --- | --- |
| `data/glossary-de-final.tsv` | 205,333 | **最终释义表**（UTF-8 无 BOM + LF），`dist/glossary-de.qj` 就是它打的包 | CC-BY-SA-4.0 |
| `data/glossary-de-merged.tsv` | 205,226 | 合并底表（第四轮质检前的状态，供复现） | CC-BY-SA-4.0 |
| `data/glossary-de-art2.tsv` | 204,594 | 加完定冠词的表（底表 157,162 + LLM 补词） | CC-BY-SA-4.0 |
| `data/glossary-de-art.tsv` | 157,162 | HanDeDict 底表 + 冠词第一轮 | CC-BY-SA 3.0 衍生 |
| `data/llm-fill.tsv` | 43,921 | DeepSeek 严格轮（带英语提示） | 生成内容 |
| `data/llm-fill2.tsv` | 3,510 | 放宽轮（数量短语 / 专名 / 无词性兜底） | 生成内容 |
| `data/llm-fill-all.tsv` | 47,432 | 上两轮合并清洗（去掉专名多余冠词 3,762 条） | 生成内容 |
| `data/llm-fill3.tsv` / `llm-fill4.tsv` | 566 / 66 | 短语轮（`phr.`）/ 不给英语提示轮 | 生成内容 |
| `data/llm-fill-phrase.tsv` | 632 | 上两轮合并 | 生成内容 |
| `data/llm-gap.tsv` | 147 | 第四轮：词库里**还没有**德语的词（最后一轮补完，缺口归零） | 生成内容 |
| `data/llm-articles.tsv` | 40,643 | 第四轮：名词首义补 der/die/das | 生成内容 |
| `data/llm-cefr.tsv` | 107,687 | 第四轮：德语实词 → CEFR 等级（Goethe 口径） | 生成内容 |
| `data/llm-audit.tsv` | 14,646 | 第四轮：全表质检提出的修改（合并时只采纳 3,692 条） | 生成内容 |
| `data/apply-report.txt` | 55,241 | 合并落地的每一条改动（含被过滤器拒绝的理由；第四轮 + 第五轮） | 生成内容 |
| `data/llm-sense.tsv` | 36,418 | 第五轮：常用义可疑的词 + 建议释义（只采纳词频 ≥100 的 14,422 条） | 生成内容 |
| `data/levels-de.tsv` | 170,638 | A1–C2 等级表（键 = 整条释义小写）；Goethe 5,000 + LLM 分级 + 月份/度量兜底 | MIT + 生成内容 |
| `data/user-glossary-de.tsv` | 10 | 个人释义表样例 | 自制 |
| `dist/glossary-de.qj` | 205,333 | 打包产物，15,490,832 B，sha256 `e1908475…` | CC-BY-SA-4.0 |
| `data/sources/` | — | HanDeDict、german-nouns、Goethe 5,000 原始数据 | 各自见 `NOTICE.md` |

### 补词流水线

```powershell
python tools\gap_in_dict.py       # 1. 算缺口：词库 dict.tsv 减德语表 → 48,210 个词没译文
python tools\llm_fill.py          # 2. 严格轮：英语释义当提示，名词强制 der/die/das → 43,921 条
python tools\llm_fill.py --relaxed --skip data\llm-fill.tsv --out data\llm-fill2.tsv        # 3. 放宽轮
python tools\postprocess.py       # 4. 清理 + 合并 → llm-fill-all.tsv
python tools\add_articles2.py     # 5. 冠词二轮：genus 1..4 兜底 + 复数栏 → 修 4,876 行
python tools\llm_fill.py --phrase --skip data\llm-fill3.tsv --out data\llm-fill3.tsv        # 6a. 短语轮
python tools\llm_fill.py --phrase --no-hint --skip data\llm-fill3.tsv --out data\llm-fill4.tsv   # 6b. 照抄英语重试
python tools\merge_glossary.py data\glossary-de-art2.tsv data\llm-fill-phrase.tsv data\glossary-de-merged.tsv
python tools\audit.py             # 7. 体检：重复 / 空释义 / 缺冠词 / BOM / CR
# —— 第四轮（质检 + 等级表）：一个脚本四个阶段，都支持断点续跑 ——
python tools\llm_tools.py gap      --workers 8   # 8. 词库里还没德语的词（本轮补 147 个，缺口归零）
python tools\llm_tools.py articles --workers 8   # 9. 名词首义补冠词 → 40,643 条
python tools\llm_tools.py cefr     --workers 8   # 10. 德语实词 → CEFR → 107,687 条
python tools\llm_tools.py audit --only llm       # 11. 全表质检：只挑「意思明显不符」的 → 14,646 条
python tools\apply_fixes.py --apply              # 12. 四条过滤器合并落地 → glossary-de-final.tsv 205,333 行
python tools\llm_tools.py levels                 # 13. 重建 levels-de.tsv（165,143 键）
python tools\gaps_now.py data\glossary-de-final.tsv <源码>\assets\lexicon\dict.tsv data\levels-de.tsv   # 14. 体检
# —— 第五轮（常用义修正）：拿英语释义表当第二意见 ——
python tools\llm_tools.py sense  --workers 8     # 15. 只挑「常用义明显不对」的行 → 36,418 条（88,112 词里 41%）
python tools\apply_fixes.py --apply              # 16. 只采纳词频 ≥100 的 14,422 条 → 205,333 行
python tools\llm_tools.py levels                 # 17. 重建 levels-de.tsv（170,638 键，含月份/度量兜底）
qingjian-dict-convert.exe --out-dir out pack glossary --input data\glossary-de-final.tsv --language de ...
```

`apply_fixes.py` 的过滤器是关键——LLM 质检会顺手动很多**本来正确**的词条
（第四轮抽样里约 15% 的改动是损坏：`艾莎 Elsa → Aisha`、`福瑞 → Furry`）。
现在只有同时满足下面条件才落地，否则在 `apply-report.txt` 里记明拒绝理由：

1. 只把 `der/die/das` 换掉、正文没变的 → 拒绝（冠词表 `add_articles2` 认旧冠词正确时尤其）；
2. 词性（`n.`/`v.`/…）被改的 → 拒绝；
3. 旧、新都是单个拉丁词、且 `difflib` 相似度 < 0.6 的 → 视为臆改专名，拒绝；
4. 与原文一字不差的「复述」→ 直接忽略（第四轮 10,651 条）。

第五轮的「常用义」段另有三条（`apply-report.txt` 里逐条可查）：

5. **词频 < 100 的一律不动**（跳过 16,224 条）：生僻词没有可靠第二意见、错了也没人用
   （代价是连 `憋闷 → bedrückt; beklommen; stickig` 这种合理建议也一起放过）；
6. **只增不删**：新义项里去掉旧表已有的，插到最前，旧义项全部保留——`权利 das Recht` 就是这么补进
   `die Anwartschaft` 前面的；
7. **词性变更必须拿到英语表佐证**：新词性要出现在英语表该词的词性集合里、旧词性不在其中、且词频 ≥1000
   （1,709 条没佐证 → 拒绝；`跟 n. die Ferse → prep. mit; und` 有佐证 → 通过）；
   另外新义项的冠词与冠词表整词命中结果不一致的（`垂水`、共 225 条）一律丢掉。

两个踩过的坑，重跑务必注意：

* **`deepseek-v4-flash` 默认开思维链**：不加 `"reasoning_effort": "none"` 时 token 全烧在 `reasoning_content` 上，
  `message.content` 返回空串、`finish_reason: "length"`。脚本已固定带上这个参数。
* **服务器 mmap 着 `.qj`**：直接覆盖会报 `ERROR_USER_MAPPED_FILE`，要先 `Stop-Process qingjian-server`
  再复制（宿主约 150 ms 后自动重启 Server 并重新 mmap）。

## 目录

```
german/
  README.md                     本文
  CHANGELOG.md                  改动记录
  NOTICE.md                     数据署名与许可细节
  docs/build-and-deploy.md      完整构建 / 部署 / 踩坑记录（要从零重建就看这篇）
  docs/screenshots/             候选窗口截图
  tools/                        生成工具（Python）：缺口统计、补词、加冠词、合并、等级表、体检
  scripts/                      构建、部署、体检、协议探针、OCR 脚本
  data/                         释义表 / 等级表 / 补词中间产物 / 上游原始数据
  dist/glossary-de.qj           打包好的释义表，直接拷进 <安装目录>\data\generated\
  patch/qingjian-german.patch   相对上游 40e3e55 的完整改动
```

## 源码改动（`german` 分支）

15 个文件、+156 / −19 行，全部在上游 `40e3e55` 之上：

- `crates/qingjian-core/src/candidate/language.rs`：`Language::German`（`de` / `de-DE` / `german` / `deutsch`）
- `crates/qingjian-platform/src/protocol/mod.rs`：`PROTOCOL_VERSION` 7 → 8
- `apps/windows/server/src/dispatch/composed/mod.rs`：`downgrade_for_old_dll` 把德语记号降级成英语，保住旧 DLL
- `apps/windows/{server,settings}/build.rs`：图标路径按 `CARGO_MANIFEST_DIR` 解析
- `apps/cli`、`apps/macos`、`apps/linux`：语言列表与文案补德语
- `crates/qingjian-predict/src/gloss/prompt.rs`：德语释义提示词（云联想用）
- `.cargo/config.toml`、`scripts/`：本机没有 Windows SDK 时的链接配置与构建包装

完整 diff 见 `patch/qingjian-german.patch`。

## 已知限制

- **协议版本变了**：德语记号让 `PROTOCOL_VERSION` 从 7 升到 8。老 DLL 靠 Server 侧降级仍可用，
  但如果你自己改了协议，请同步重编并注册 TSF DLL（`docs/build-and-deploy.md` 第五节）。
- **CEFR 分级：每条释义都能定级**。等级表的键是整条释义的小写文本（精确匹配），表里 170,638 条，
  运行时查表命中 100%；其中 11,649 条（日期、单位、化学名——`400米跨栏`、`2‐酮古洛糖酸`）没有可靠依据，
  按 B2 兜底（没有实词的短语按 A1），所以统计页不会漏项，但这些词的等级只是默认值。
- **名词首义里还有 15,883 条没有定冠词**：剩下的是日期（`12月25日 → 1. Weihnachtsfeiertag`）、
  数量（`5分钟`）、技术复合词（`8通道双向数据耦合器`）——这些本来就不该加 `der/die/das`。
- **词库覆盖率已经是 100%**：`dict.tsv` 92,825 个词条全部有德语译文（第四轮补完 147 个缺口词，
  最后一个 `阜新市 → die Stadt Fuxin` 也在里面）。
- 语料是词典式的，**不是逐句翻译**；生成词条（`llm-fill*.tsv`、`llm-*.tsv`）没有人工逐条校对。
  第五轮已经用英语表校正了 14,422 条常用义，但**词频 <100 的生僻词仍可能有取错义项的老毛病**
  （例如 `都会` 被当成「大都市」而不是「都 + 会」）。

## 许可与署名

- 本仓库是 **qingjian** 的 fork，源码部分沿用上游 **GPL-3.0**（见根目录 `LICENSE`）
- 释义表由 [HanDeDict](https://github.com/gugray/HanDeDict)（CC-BY-SA 3.0）与
  [german-nouns](https://github.com/gambolputty/german-nouns)（CC-BY-SA 4.0）衍生，
  另有 48,064 条由 DeepSeek 生成 → `german/data/glossary-de*.tsv` 与 `german/dist/glossary-de.qj`
  **按 CC-BY-SA-4.0 发布**，署名细节见 `german/NOTICE.md` 与词表 META
- Goethe-Institut 5,000 词表：MIT

## 本机专用说明

`scripts/cargo-config.this-machine.toml` 与 `.cargo/config.toml` 里的绝对路径（`E:\codemain\…`、
MSVC 版本号、`linkwrap.cmd`）只对制作这台机器有效，是为了在**没装 Windows SDK** 的情况下把
x64 三件套和 x86 TSF DLL 都链出来。换机器要先看 `docs/build-and-deploy.md` 第二、三节。
