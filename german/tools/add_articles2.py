# -*- coding: utf-8 -*-
"""给德语释义表的名词补定冠词（第二版）。

和第一版 add_articles.py 的区别：
  1. 名词表读取带 genus 1..4 兜底（第一版只认 genus 列，约 1 万个词条被跳过 —— 心/Herz、
     公里/Kilometer、范围/Bereich 的性别只在 genus 1..4 里，所以当时全漏了）
  2. 只在「首义是单个词」时才加冠词（`älterer Bruder`、`einen Tag`、`in Richtung` 这类短语
     加了冠词会变成错的德语，一律跳过）
  3. 复合词按「性别随最后一段」补（Kraftfahrzeug → das Fahrzeug）
  4. 复数用名词表的复数栏 + 严格词尾判断补 die（Daten/Playoffs/Tirailleure），
     并跳过纯专名（Hessen/Abu 这类 Toponym/Nachname 不加冠词）
  5. 冠词加在释义最前面（`n. (Eisenbahn-) Zug` → `n. der (Eisenbahn-) Zug`）

用法：
  python add_articles2.py --dry-run         # 只统计，不写文件
  python add_articles2.py                   # 写 glossary-de-art2.tsv + articles2-report.txt
"""
import csv
import io
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
GENDER_CSV = os.path.join(HERE, "gender", "nouns.csv")
TSV_IN = os.path.join(HERE, "glossary-de-merged.tsv")
TSV_OUT = os.path.join(HERE, "glossary-de-art2.tsv")
REPORT = os.path.join(HERE, "articles2-report.txt")
ARTICLES = {"m": "der", "f": "die", "n": "das"}
NOUN_PREFIX = "n. "
HAS_ARTICLE = re.compile(r"^(der|die|das)\s", re.I)
PLURAL_SUFFIXES = ("se", "en", "er", "nen", "e", "n", "s")
PROPER_POS = ("toponym", "nachname", "vorname", "eigenname")
PLURAL_COLS = ("nominativ plural", "nominativ plural*", "nominativ plural 1", "nominativ plural 2",
               "nominativ plural 3", "nominativ plural 4", "nominativ plural stark",
               "nominativ plural schwach", "nominativ plural gemischt")


def load_genders(path):
    """返回 (lemma→冠词, 复数形→冠词, 纯专名集合, 统计)。"""
    table, plurals, proper_only, stats = {}, {}, set(), Counter()
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            lemma = (row.get("lemma") or "").strip()
            pos = (row.get("pos") or "").lower()
            if not lemma or lemma.startswith("-"):
                continue
            is_proper = any(k in pos for k in PROPER_POS)
            genus = (row.get("genus") or "").strip()
            if genus not in ARTICLES:
                for key in ("genus 1", "genus 2", "genus 3", "genus 4"):
                    g = (row.get(key) or "").strip()
                    if g in ARTICLES:
                        genus = g
                        stats["genus1-4 兜底"] += 1
                        break
                else:
                    genus = ""
                    stats["无性别"] += 1
            else:
                stats["genus 直接命中"] += 1
            if is_proper and not genus:
                proper_only.add(lemma)
                continue
            if not genus:
                for col in PLURAL_COLS:
                    form = (row.get(col) or "").strip()
                    if form:
                        plurals.setdefault(form, "die")
                        stats["只查到复数形"] += 1
                continue
            art = ARTICLES[genus]
            if lemma in table and table[lemma] != art:
                stats["性别冲突（保留先出现的）"] += 1
                continue
            table.setdefault(lemma, art)
            for col in PLURAL_COLS:
                form = (row.get(col) or "").strip()
                if form:
                    plurals.setdefault(form, "die")
    proper_only -= set(table)
    return table, plurals, proper_only, stats


def head_token(gloss):
    """首义里要加冠词的那个词（去掉括号说明后、第一个 , ; 之前的部分）。"""
    body = gloss[len(NOUN_PREFIX):]
    body = re.sub(r"\([^)]*\)", "", body)
    cut = len(body)
    for ch in ",;":
        i = body.find(ch)
        if i != -1:
            cut = min(cut, i)
    return body[:cut].strip()


def article_for(token, table, plurals, proper_only):
    if not token or HAS_ARTICLE.match(token):
        return None, "已有冠词"
    if " " in token or "\t" in token:
        return None, "短语（跳过）"
    if token in proper_only:
        return None, "纯专名（跳过）"
    if token in table:
        return table[token], "整词命中"
    low = token.lower()
    if low in table:
        return table[low], "小写命中"
    if "-" in token:
        last = token.split("-")[-1]
        for cand in (last, last.lower()):
            if cand in proper_only:
                return None, "复合词末段是专名（跳过）"
            if cand in table:
                return table[cand], "复合词末段"
        return None, "复合词末段查不到"
    if token in plurals:
        return "die", "复数栏命中"
    if token[:1].isupper():
        for suf in PLURAL_SUFFIXES:
            if token.endswith(suf):
                base = token[:-len(suf)]
                if base in table:
                    return "die", "复数→die(%s)" % suf
                if base in proper_only:
                    return None, "复数形是专名（跳过）"
    return None, "名词表查不到"


def main():
    write = "--dry-run" not in sys.argv
    table, plurals, proper_only, gstats = load_genders(GENDER_CSV)
    print("名词表 %d 条 / 复数形 %d 条 / 纯专名 %d 条  %s" % (len(table), len(plurals), len(proper_only), dict(gstats)))

    out, stats, samples = [], Counter(), []
    for raw in io.open(TSV_IN, "r", encoding="utf-8", newline=""):
        line = raw.rstrip("\r\n")
        if not line or line.startswith("#") or "\t" not in line:
            out.append(line)
            continue
        word, gloss = line.split("\t", 1)
        if gloss.startswith(NOUN_PREFIX):
            token = head_token(gloss)
            art, why = article_for(token, table, plurals, proper_only)
            if art:
                new_gloss = "%s%s %s" % (NOUN_PREFIX, art, gloss[len(NOUN_PREFIX):])
                out.append("%s\t%s" % (word, new_gloss))
                stats[why] += 1
                if len(samples) < 20:
                    samples.append("%s\t%s   →   %s" % (word, gloss, new_gloss))
                continue
            stats["未改：" + why] += 1
        else:
            stats["非名词行"] += 1
        out.append("%s\t%s" % (word, gloss))

    for k in sorted(stats, key=lambda k: -stats[k]):
        print("  %-26s %d" % (k, stats[k]))
    print("\n抽样：")
    for s in samples:
        print("    " + s)
    if write:
        with io.open(TSV_OUT, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(out) + "\n")
        with io.open(REPORT, "w", encoding="utf-8", newline="") as f:
            f.write("名词表 %d 条 / 复数形 %d 条 / 纯专名 %d 条\n%s\n" % (len(table), len(plurals), len(proper_only), dict(gstats)))
            for k in sorted(stats, key=lambda k: -stats[k]):
                f.write("%s\t%d\n" % (k, stats[k]))
        print("\n已写 %s （%d B）" % (TSV_OUT, os.path.getsize(TSV_OUT)))
    else:
        print("\n（--dry-run，没有写文件）")


if __name__ == "__main__":
    main()
