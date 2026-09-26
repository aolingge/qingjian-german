# -*- coding: utf-8 -*-
"""德语释义表体检：重复、缺冠词、空释义、超长释义、词库覆盖缺口分档。

用法：
  python audit.py                       # 默认检查本目录的 glossary-de-merged.tsv
  python audit.py <glossary.tsv> <dict.tsv>
"""
import io
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEF_GLOSSARY = os.path.join(HERE, "glossary-de-merged.tsv")
DEF_DICT = r"D:\application\Qingjian\data\lexicon\dict.tsv"
ARTICLES = ("der ", "die ", "das ")
SKIP_ARTICLE = {"ein", "eine", "einer", "einem", "einen", "kein", "keine"}


def read_rows(path):
    rows = []
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        for raw in f:
            if raw.endswith("\r\n"):
                raw = raw[:-2]
            elif raw.endswith("\n"):
                raw = raw[:-1]
            if not raw or raw.startswith("#"):
                continue
            if "\t" not in raw:
                rows.append((raw, ""))
                continue
            w, s = raw.split("\t", 1)
            rows.append((w.strip(), s.strip()))
    return rows


def main():
    gp = sys.argv[1] if len(sys.argv) > 1 else DEF_GLOSSARY
    dp = sys.argv[2] if len(sys.argv) > 2 else DEF_DICT
    rows = read_rows(gp)
    print("释义表: %s" % gp)
    print("  数据行 = %d" % len(rows))

    dup = [w for w, c in Counter(w for w, _ in rows).items() if c > 1]
    print("  重复词条 = %d  例: %s" % (len(dup), ", ".join(sorted(dup)[:8])))

    empty = [w for w, s in rows if not s]
    print("  空释义 = %d  例: %s" % (len(empty), ", ".join(empty[:8])))

    noart, noart_multi = [], []
    for w, s in rows:
        if not s.startswith("n. "):
            continue
        gloss = s[3:]
        head = gloss.split("(")[0]
        parts = [p.strip() for p in head.replace(";", ",").split(",") if p.strip()]
        if not parts:
            continue
        first = parts[0]
        low = first.lower()
        if any(low.startswith(a) for a in ARTICLES):
            continue
        if any(low.startswith(a + " ") for a in SKIP_ARTICLE):
            continue
        if first[:1].isupper() and not first.isupper():
            noart.append(w)
        elif any(p[:1].isupper() and not p.isupper() for p in parts):
            noart_multi.append(w)
    print("  名词首义缺冠词 = %d  例: %s" % (len(noart), ", ".join(noart[:8])))
    print("  首义无冠词但后续义项像名词 = %d  例: %s" % (len(noart_multi), ", ".join(noart_multi[:8])))

    longg = [(w, len(s)) for w, s in rows if len(s) > 80]
    print("  超过 80 字符的释义 = %d  例: %s" % (len(longg), "; ".join("%s(%d)" % t for t in sorted(longg, key=lambda t: -t[1])[:5])))

    print("  首字节 = %d (应为 35 '#')" % (open(gp, "rb").read(1)[0]))
    with open(gp, "rb") as f:
        data = f.read()
    print("  BOM = %s, CR = %d" % (data[:3] == b"\xef\xbb\xbf", data.count(b"\r")))

    if not os.path.exists(dp):
        print("词库不存在，跳过覆盖率: %s" % dp)
        return
    have = set(w for w, _ in rows)
    bands = defaultdict(lambda: [0, 0])
    missing = []
    total = 0
    with io.open(dp, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            word, freq = cols[0].strip(), cols[2].strip()
            try:
                fr = int(freq)
            except ValueError:
                fr = 0
            total += 1
            if word in have:
                continue
            missing.append((word, fr))
            for lo in (1, 10, 100, 1000, 10000):
                if fr >= lo:
                    bands[lo][0] += 1
                    bands[lo][1] += 1
    print("词库: %d 词，有德语 %d (%.1f%%)，缺 %d" % (total, total - len(missing), 100.0 * (total - len(missing)) / total, len(missing)))
    for lo in sorted(bands):
        print("  缺失且词频 >= %-6d : %d" % (lo, bands[lo][0]))
    print("  缺失中词频最高的 30 个:")
    for w, fr in sorted(missing, key=lambda t: -t[1])[:30]:
        print("    %-12s %d" % (w, fr))


if __name__ == "__main__":
    main()
