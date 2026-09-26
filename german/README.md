# 青简德语支持（Qingjian German）

给中文拼音输入法 **青简**（[qingjian-team/qingjian](https://github.com/qingjian-team/qingjian)，GPL-3.0）加上「学习语言 = 德语」的一整套成果：源码改动、204,594 条汉德释义表、德语词汇等级表、生成工具，以及构建 / 部署 / 验证脚本。

## 现在能做什么

- 设置页「学习语言」多出 **德语** 选项，候选词旁显示德语译文（含 ä/ö/ü/ß 等变音符号）
- 词库 92,826 个词里 **92,044 个（99.2%）** 有德语译文（补词前只有 43,709 个）
- 统计页有 A1 / A2 / B1 / B2+ 生词分级（36,560 条释义能定级）
- **不用换 DLL**：安装自带的旧版 TSF DLL 不认识 `German` 枚举，Server 侧按协议版本自动降级（协议 7→8）

## 目录

```
german/
  docs/build-and-deploy.md      完整构建 / 部署 / 踩坑记录（要从零重建就看这篇）
  tools/                        生成工具（Python）：补词、加冠词、合并、打包、等级表
  scripts/                      构建、部署、体检、协议探针、OCR 脚本
  data/glossary-de-merged.tsv   最终释义表（204,594 行，UTF-8 无 BOM + LF）
  data/levels-de.tsv            德语词汇等级表（36,560 条）
  data/llm-fill*.tsv            DeepSeek 补词结果：严格轮 / 放宽轮 / 合并清洗后
  data/sources/                 HanDeDict、german-nouns、Goethe 5,000 的原始数据
  dist/glossary-de.qj           打包好的释义表，直接拷进 <安装目录>\data\generated\
  patch/qingjian-german.patch   相对上游 40e3e55 的完整改动
```

## 最小使用（不编译）

1. `copy dist\glossary-de.qj "D:\application\Qingjian\data\generated\"`（Server 重启后生效）
2. `%APPDATA%\Qingjian\config.toml` 里 `learning_language = "de"`
3. 设置页「学习语言」选 **德语**（二进制需含德语支持，见下）

可选：
- `data\levels-de.tsv` → `<安装目录>\assets\levels\`（生词分级）
- `data\user-glossary-de.tsv` → `%APPDATA%\Qingjian\`（个人释义表，优先于随包表，改单条释义就改它）

二进制（`qingjian-server.exe` / `qingjian-settings.exe` / 两个 TSF DLL）不在仓库里，按 `docs/build-and-deploy.md` 自己编，
或用 Release 里的成品。

## 源码改动（german 分支）

15 个文件、+156 / −19 行，都在上游 `40e3e55` 之上：

- `crates/qingjian-core/src/candidate/language.rs`：`Language::German`（`de` / `de-DE` / `german` / `deutsch`）
- `crates/qingjian-platform/src/protocol/mod.rs`：`PROTOCOL_VERSION` 7 → 8
- `apps/windows/server/src/dispatch/composed/mod.rs`：`downgrade_for_old_dll` 把德语记号降级成英语，保住旧 DLL
- `apps/windows/{server,settings}/build.rs`：图标路径按 `CARGO_MANIFEST_DIR` 解析
- `apps/cli`、`apps/macos`、`apps/linux`：语言列表与文案补德语
- `crates/qingjian-predict/src/gloss/prompt.rs`：德语释义提示词（云联想用）
- `.cargo/config.toml`、`scripts/`：本机没有 Windows SDK 时的链接配置与构建包装

完整 diff 见 `patch/qingjian-german.patch`。

## 许可与署名

- 本仓库是 **qingjian** 的 fork，源码部分沿用上游 **GPL-3.0**（见根目录 `LICENSE`）
- 释义表由 [HanDeDict](https://github.com/gugray/HanDeDict)（CC-BY-SA 3.0）与
  [german-nouns](https://github.com/gambolputty/german-nouns)（CC-BY-SA 4.0）衍生，
  另有 47,432 条由 DeepSeek 生成 → `german/data/glossary-de*.tsv` 与 `german/dist/glossary-de.qj`
  **按 CC-BY-SA-4.0 发布**，署名细节见 `german/NOTICE.md` 与词表 META
- Goethe-Institut 5,000 词表：MIT

## 本机专用说明

`scripts/cargo-config.this-machine.toml` 与 `.cargo/config.toml` 里的绝对路径（`E:\codemain\…`、
MSVC 版本号、`linkwrap.cmd`）只对制作这台机器有效，是为了在**没装 Windows SDK** 的情况下把
x64 三件套和 x86 TSF DLL 都链出来。换机器要先看 `docs/build-and-deploy.md` 第二、三节。
