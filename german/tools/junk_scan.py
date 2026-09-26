# -*- coding: utf-8 -*-
"""junk_scan.py —— 词表体检（规则判定，不用 LLM）：占位符 / 空释义 / 重复 / 覆盖。

注意：释义里出现 löschen、unbekannt 是**正常译文**（删除、不知名），不要当垃圾；
同样的道理，「德语跟英语一模一样」也不是问题（Middleware、Vancomycin、illegal 本来就是外来词）。

用法：
    python junk_scan.py                  # 统计 + 每类样例
    python junk_scan.py --out junk.tsv   # 导出「词<TAB>类别<TAB>释义」
"""
from __future__ import annotations

import argparse
import collections
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
GLOSS = os.path.join(HERE, "glossary-de-merged.tsv")
DICT = os.path.join(SRC, r"assets\lexicon\dict.tsv")
POS = re.compile(r"^(n|v|adj|adv|int|pron|num|prep|conj|part|phr|m)\.\s+")
PLACEHOLDER = re.compile(r"\*\*\*|\?{2,}|^\s*(n/?a|none|leer)\s*$", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gloss", default=GLOSS)
    ap.add_argument("--out")
    args = ap.parse_args()

    freq = {}
    with io.open(DICT, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0]:
                try:
                    freq[p[0]] = int(p[2])
                except (IndexError, ValueError):
                    freq[p[0]] = 0

    rows = []
    for line in io.open(args.gloss, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        w, _, g = line.partition("\t")
        if w and g:
            rows.append((w, g))

    cats = collections.OrderedDict((k, []) for k in ("A 占位符", "B 无字母无数字", "C 完全重复行", "D 同词多义"))
    for w, g in rows:
        body = POS.sub("", g).strip()
        if PLACEHOLDER.search(body):
            cats["A 占位符"].append((w, g))
        if not re.search(r"[0-9A-Za-zÄÖÜäöüß]", body):
            cats["B 无字母无数字"].append((w, g))

    seen = collections.Counter(rows)
    for (w, g), n in seen.items():
        if n > 1:
            cats["C 完全重复行"].append((w, g))
    byword = collections.defaultdict(set)
    for w, g in rows:
        byword[w].add(POS.sub("", g).strip().lower())
    for w, gs in byword.items():
        if len(gs) > 1 and w in freq:
            cats["D 同词多义"].append((w, " | ".join(sorted(gs))[:80]))

    in_dict = sum(1 for w, _ in rows if w in freq)
    print(f"词表 {len(rows):,} 行；其中能打出来的（在词库 dict.tsv 里）{in_dict:,} 行"
          f"（{in_dict * 100.0 / max(1, len(rows)):.1f}%），其余 {len(rows) - in_dict:,} 行是词典收录、"
          f"输入法打不出来的长词/日期/地名（无害，不进候选窗）")
    for k, v in cats.items():
        print(f"  {k:<12} {len(v):>7,}")
        for w, g in v[:8]:
            print(f"        {w}  →  {g[:70]}")
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            for k, v in cats.items():
                for w, g in v:
                    f.write(f"{w}\t{k}\t{g}\n")
        print(f"写出 {args.out}（{os.path.getsize(args.out):,} B）")


if __name__ == "__main__":
    main()
