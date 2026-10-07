# -*- coding: utf-8 -*-
import io, sys, collections
sys.path.insert(0, r"E:\codemain\qingjian-de\de-glossary")
import llm_fill as L
items = L.load_worklist()
done = set()
with io.open(r"E:\codemain\qingjian-de\de-glossary\llm-fill.tsv", encoding="utf-8") as f:
    for ln in f:
        if "\t" in ln and not ln.startswith("#"):
            done.add(ln.split("\t")[0])
rest = [it for it in items if it[0] not in done]
print("总缺口 %d，已补 %d，剩 %d" % (len(items), len(done), len(rest)))
buckets = collections.Counter()
for w, syl, en in rest:
    f = int(syl) if False else None
print("前 30 个（按词频）:", "、".join(w for w, _, _ in rest[:30]))
print("有英语提示的:", sum(1 for _, _, en in rest if en))
# 词频分布
import re
freq = {}
with io.open(L.DICT, encoding="utf-8") as f:
    for ln in f:
        p = ln.rstrip("\n").split("\t")
        if len(p) >= 3:
            try: freq[p[0]] = int(p[2])
            except ValueError: pass
for lo, hi in ((10000, 10**9), (1000, 10000), (100, 1000), (10, 100), (0, 10)):
    print("  词频 %6d~%9d : %d" % (lo, hi, sum(1 for w, _, _ in rest if lo <= freq.get(w, 0) < hi)))
with io.open(r"E:\codemain\qingjian-de\de-glossary\rest-words.txt", "w", encoding="utf-8", newline="\n") as f:
    for w, syl, en in rest:
        f.write("%s\t%s\t%s\n" % (w, freq.get(w, 0), en))
print("清单已写 rest-words.txt")
