"""对比 HanDeDict 原始义项与现有德语释义表，弄清上一次转换是怎么挑义项的。

用法：
    D:\\tools\\Miniconda\\python.exe E:\\codemain\\qingjian-de\\de-glossary\\analyze.py
输出：E:\\codemain\\qingjian-de\\de-glossary\\analyze-report.txt（UTF-8）
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

HANDEDICT = r"C:\Users\aolin\AppData\Local\Temp\codex-handedict-source-20260926\handedict.u8"
TSV = os.path.join(os.environ["APPDATA"], "Qingjian", "custom", "glossary-de-hd.tsv")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze-report.txt")

# 49 直前 直前 [zhi2 qian2] /geradeaus (Adv)/
ENTRY = re.compile(r"^(?P<trad>\S+) (?P<simp>\S+) \[(?P<pinyin>[^\]]*)\] /(?P<senses>.*)/\s*$")


def load_handedict(path: str) -> dict[str, list[str]]:
    """简化字 -> 义项列表（保留原始顺序，去重）"""
    table: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            match = ENTRY.match(line.rstrip("\n"))
            if not match:
                continue
            senses = [s for s in match.group("senses").split("/") if s.strip()]
            if not senses:
                continue
            key = match.group("simp")
            bucket = table.setdefault(key, [])
            for sense in senses:
                if sense not in bucket:
                    bucket.append(sense)
    return table


def load_tsv(path: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            rows.append((parts[0], parts[1]))
    return rows


def terms(gloss: str) -> list[str]:
    """把 `n. Schule; Hof` 拆成裸词（去词性、去括号、按 ; , 分）"""
    body = re.sub(r"^[a-z]+\.\s*", "", gloss)
    body = re.sub(r"\([^)]*\)", "", body)
    return [t.strip() for t in re.split(r"[;,]", body) if t.strip()]


def main() -> int:
    handheld = load_handedict(HANDEDICT)
    rows = load_tsv(TSV)
    lines: list[str] = []
    lines.append(f"HanDeDict 简化字词条：{len(handheld)}")
    lines.append(f"现有德语表行数：{len(rows)}")

    # 1) 现有表的词是否都在 HanDeDict 里
    missing = [w for w, _ in rows if w not in handheld]
    lines.append(f"现有表有、HanDeDict 没有的词：{len(missing)}  例：{missing[:10]}")

    # 2) 现有释义的第一个义项是否能在 HanDeDict 里找到，位于第几位
    positions = Counter()
    not_found: list[tuple[str, str]] = []
    for word, gloss in rows:
        senses = handheld.get(word, [])
        first = (terms(gloss) or [""])[0]
        if not first:
            positions["empty"] += 1
            continue
        hit = None
        for index, sense in enumerate(senses):
            if first and first.lower() in sense.lower():
                hit = index
                break
        if hit is None:
            positions["miss"] += 1
            if len(not_found) < 25:
                not_found.append((word, gloss, " | ".join(senses[:4])))
        else:
            positions[f"index{hit}"] += 1
    lines.append("")
    lines.append("现有表首个义项在 HanDeDict 中的位置：")
    for key in sorted(positions):
        lines.append(f"  {key}: {positions[key]}")
    lines.append("")
    lines.append("对不上（前 25 条）——词 / 现有表 / HanDeDict 前 4 个义项：")
    for word, gloss, senses in not_found:
        lines.append(f"  {word}\t{gloss}\t{senses}")

    # 3) 长度分布 + 括号
    lengths = [len(g) for _, g in rows]
    total = len(lengths) or 1
    hist = Counter()
    for value in lengths:
        hist[min(value // 8 * 8, 64)] += 1
    lines.append("")
    lines.append(f"释义长度：平均 {sum(lengths) / total:.1f}  最大 {max(lengths)}")
    for key in sorted(hist):
        lines.append(f"  {key:>3}-{key + 7}: {hist[key]}")
    paren = sum(1 for _, g in rows if "(" in g)
    semi = sum(1 for _, g in rows if ";" in g)
    comma = sum(1 for _, g in rows if "," in g)
    lines.append(f"含括号 {paren} / 含分号 {semi} / 含逗号 {comma}")

    # 4) 抽查词：HanDeDict 义项 vs 现有表
    lines.append("")
    lines.append("抽查：")
    for word in ("便宜", "中国", "电话", "谢谢", "东西", "打假", "大家", "汽车", "手机", "银行"):
        current = next((g for w, g in rows if w == word), "<无>")
        lines.append(f"  {word}")
        lines.append(f"    现有: {current}")
        lines.append(f"    原始: {' | '.join(handheld.get(word, [])[:6])}")

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({len(lines)} lines)")
    print("positions:", dict(positions))
    print(f"rows={len(rows)} missing={len(missing)} avg_len={sum(lengths)/total:.1f} max_len={max(lengths)} paren={paren}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
