# -*- coding: utf-8 -*-
"""名词冠词缺口分析：找出「n. 」开头但首义没有 der/die/das 的行，并按可修复程度分档。

分档：
  EXACT   首义整段就在名词表里（本来应该能补上）
  变体    首义去掉复数/格词尾、或大小写差异后命中
  LAST    复合词的最后一段命中（德语复合词性别随最后一段）
  NONE    名词表里查不到（专名、外来词、短语、动词化用法）
用法： python article_gap.py [glossary.tsv] [dict.tsv]
"""
import csv
import io
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
GLOSSARY = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "glossary-de-merged.tsv")
DICT_CANDIDATES = [
    sys.argv[2] if len(sys.argv) > 2 else "",
    r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926\assets\lexicon\dict.tsv",
    r"D:\application\Qingjian\assets\lexicon\dict.tsv",
]
GENDER_CSV = os.path.join(HERE, "gender", "nouns.csv")
ARTICLES = {"m": "der", "f": "die", "n": "das"}
NOUN_PREFIX = "n. "
HAS_ARTICLE = re.compile(r"^(der|die|das)\s", re.I)


def load_genders(path):
    table = {}
    stats = Counter()
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lemma = (row.get("lemma") or "").strip()
            genus = (row.get("genus") or "").strip()
            if not lemma or lemma.startswith("-"):
                continue
            if genus not in ARTICLES:
                stats["无 genus（只出现在 genus1..4）"] += 1
                for key in ("genus 1", "genus 2", "genus 3", "genus 4"):
                    g = (row.get(key) or "").strip()
                    if g in ARTICLES:
                        genus = g
                        break
                else:
                    continue
            stats["采用"] += 1
            table.setdefault(lemma, ARTICLES[genus])
    return table, stats


def first_sense(gloss):
    """首义：到第一个 , ; ( 为止。"""
    body = gloss[len(NOUN_PREFIX):]
    cut = len(body)
    for ch in ",;(":
        i = body.find(ch)
        if i != -1:
            cut = min(cut, i)
    return body[:cut].strip()


def classify(piece, table):
    if not piece or HAS_ARTICLE.match(piece):
        return "OK"
    if piece in table:
        return "EXACT"
    low = piece.lower()
    for cand in {low, low.rstrip("s"), low.rstrip("es"), low.rstrip("n"), low.rstrip("en"), piece.rstrip("s")}:
        if cand in table:
            return "变体"
    toks = re.split(r"[\s\-–'’]+", piece)
    for tok in reversed(toks):
        if tok[:1].isupper():
            if tok in table or tok.lower() in table:
                return "LAST"
            break
    return "NONE"


def main():
    table, stats = load_genders(GENDER_CSV)
    print("名词表 %d 条  %s" % (len(table), dict(stats)))

    freq = {}
    for path in DICT_CANDIDATES:
        if path and os.path.exists(path):
            with io.open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.rstrip("\r\n")
                    if not line or line.startswith("#"):
                        continue
                    cols = line.split("\t")
                    if len(cols) >= 3:
                        try:
                            freq[cols[0].strip()] = int(cols[2])
                        except ValueError:
                            pass
            print("词库 %s：%d 词" % (path, len(freq)))
            break
    else:
        print("未找到词库，按词表顺序统计")

    buckets = defaultdict(list)
    for raw in io.open(GLOSSARY, "r", encoding="utf-8"):
        line = raw.rstrip("\r\n")
        if not line or line.startswith("#") or "\t" not in line:
            continue
        word, gloss = line.split("\t", 1)
        if not gloss.startswith(NOUN_PREFIX):
            continue
        piece = first_sense(gloss)
        kind = classify(piece, table)
        if kind != "OK":
            buckets[kind].append((word.strip(), freq.get(word.strip(), 0), gloss.strip()))

    for kind in ("EXACT", "变体", "LAST", "NONE"):
        rows = buckets[kind]
        hi = [r for r in rows if r[1] >= 100]
        print("\n%s: %d 行（词频 >=100 的 %d 行）" % (kind, len(rows), len(hi)))
        sample = sorted(rows, key=lambda t: -t[1])[:15]
        for w, fr, g in sample:
            print("    %-14s freq=%-8d %s" % (w, fr, g[:70]))


if __name__ == "__main__":
    main()
