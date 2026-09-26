# -*- coding: utf-8 -*-
"""按「输入法真的能打出来的词」重新算德语缺口：dict.tsv ∩ 英语表 − 德语表。"""
import collections
import os

SRC = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
EN = os.path.join(SRC, r"assets\glossary\glossary-en.tsv")
DICT = os.path.join(SRC, r"assets\lexicon\dict.tsv")
DE = r"E:\codemain\qingjian-de\de-glossary\glossary-de-art.tsv"

print("dict.tsv 存在:", os.path.isfile(DICT))
if os.path.isfile(DICT):
    with open(DICT, encoding="utf-8", errors="replace") as f:
        head = [next(f) for _ in range(5)]
    print("dict.tsv 前 5 行:", [h.rstrip() for h in head])
print("lexicon 目录:", os.listdir(os.path.join(SRC, r"assets\lexicon")))


def load(path, skip_hash=True):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n")
            if not s or (skip_hash and s.startswith("#")):
                continue
            out.append(s)
    return out


de_words = {ln.split("\t")[0] for ln in load(DE)}
en_map = {}
for ln in load(EN):
    p = ln.split("\t")
    en_map.setdefault(p[0], p[1] if len(p) > 1 else "")

if os.path.isfile(DICT):
    dict_lines = load(DICT)
    # 找词条列：多数行第一列是词
    dict_words = []
    for ln in dict_lines:
        p = ln.split("\t")
        if p[0]:
            dict_words.append(p[0])
    dict_set = set(dict_words)
    print("\ndict.tsv 词条 %d（去重 %d）" % (len(dict_words), len(dict_set)))
    print("在 dict.tsv 里、德语表没有的词 %d" % len(dict_set - de_words))
    print("在 dict.tsv 里、德语表也有的词 %d" % len(dict_set & de_words))
    gap = [w for w in dict_words if w not in de_words]
    seen = set()
    uniq = []
    for w in gap:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    print("缺口去重后 %d；其中英语表里有释义的 %d" % (len(uniq), sum(1 for w in uniq if w in en_map)))
    print("\n缺口样例（前 40，带英语释义）:")
    for w in uniq[:40]:
        print("   %-8s | %s" % (w, en_map.get(w, "(英语表也没有)")[:50]))
    print("\n缺口样例（无英语释义，前 15）:")
    n = 0
    for w in uniq:
        if w not in en_map:
            print("   %s" % w)
            n += 1
            if n >= 15:
                break
    # 词长分布
    c = collections.Counter(len(w) for w in uniq)
    print("\n缺口词长分布:", sorted(c.items()))
