# -*- coding: utf-8 -*-
"""清点德语表的缺口：英语表有、德语表没有的中文词。"""
import collections
import os
import sys

SRC = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
EN = os.path.join(SRC, r"assets\glossary\glossary-en.tsv")
DE = r"E:\codemain\qingjian-de\de-glossary\glossary-de-art.tsv"


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows


en = load(EN)
de = load(DE)
print("英语表行数 %d，列数样例 %r" % (len(en), en[0]))
print("德语表行数 %d，列数样例 %r" % (len(de), de[0]))

# 英语表里词性前缀的样子
en_pos = collections.Counter()
for r in en[:200000]:
    g = r[1] if len(r) > 1 else ""
    en_pos[g.split(".")[0][:12] if "." in g else "(无)"] += 1
print("英语表释义前缀 top:", en_pos.most_common(12))

de_pos = collections.Counter()
for r in de:
    g = r[1] if len(r) > 1 else ""
    de_pos[g.split(".")[0] + "." if "." in g.split(" ")[0] else "(无.)"] += 1
print("德语表词性缩写 top:", de_pos.most_common(12))

en_words = {r[0] for r in en}
de_words = {r[0] for r in de}
missing = [r for r in en if r[0] not in de_words]
print("\n英语表词条 %d，德语表词条 %d，英语有而德语没有 %d" % (len(en_words), len(de_words), len(missing)))
print("德语有而英语没有 %d" % len(de_words - en_words))

# 缺口的长度分布 + 样例
bylen = collections.Counter(len(w) for w, _ in ((r[0], r) for r in missing))
print("缺口词长分布:", sorted(bylen.items()))
print("缺口样例（前 20）:")
for r in missing[:20]:
    print("   %s | %s" % (r[0], r[1][:60] if len(r) > 1 else ""))
print("缺口样例（多字词，前 15）:")
n = 0
for r in missing:
    if len(r[0]) >= 3:
        print("   %s | %s" % (r[0], r[1][:60] if len(r) > 1 else ""))
        n += 1
        if n >= 15:
            break

# 德语表里已有条目的释义风格样例
print("\n德语表样例 20 条:")
for r in de[:20]:
    print("   %s | %s" % (r[0], r[1][:70] if len(r) > 1 else ""))
