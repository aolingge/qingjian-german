# -*- coding: utf-8 -*-
"""apply_fixes.py —— 把 llm_tools.py 四个阶段的产物合并成最终词表。

    python apply_fixes.py --dry-run        # 只看会改什么，不写文件（默认）
    python apply_fixes.py --apply          # 写出 glossary-de-final.tsv + apply-report.txt

合并顺序（后一步基于前一步的结果）：
  1. llm-gap.tsv       新增词库里还没有译文的词
  2. llm-articles.tsv  给名词首义补 der/die/das
  3. llm-audit.tsv     改掉意思错的条目 / 删除碎片（DROP）
输出：glossary-de-final.tsv（词\t词性. 释义，LF、无 BOM）
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import add_articles2          # 复用它的冠词表（gender/nouns.csv + 复数栏 + 专名表）

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "glossary-de-merged.tsv")
FINAL = os.path.join(HERE, "glossary-de-final.tsv")
REPORT = os.path.join(HERE, "apply-report.txt")
LEGAL_POS = ("n", "v", "adj", "adv", "int", "pron", "num", "prep", "conj", "part", "phr", "m")
POS_ANY = re.compile(r"^([A-Za-zÄÖÜäöüß]{1,10})\.\s")
ART_LINE = re.compile(r"^n\.\s+(.*)$")
# 真正的垃圾：占位符 / 只有符号（`*** löschen`、`n. ???`）。释义里出现 löschen、unbekannt 是正常译文
JUNK = re.compile(r"\*\*\*|\?{2,}|^\s*(n/?a|none|leer)\s*$", re.I)
ART_HEAD = re.compile(r"^(der|die|das)\s+(.*)$", re.I)


def read_kv(path):
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            w, _, g = line.partition("\t")
            if w and g:
                out[w] = g
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的写文件（默认只预览）")
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--out", default=FINAL)
    args = ap.parse_args()

    rows = []
    with open(args.base, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            w, _, g = line.partition("\t")
            if w and g:
                rows.append([w, g])
    index = {w: i for i, (w, _) in enumerate(rows)}
    print(f"底表 {len(rows):,} 行：{args.base}")

    n_gap = n_art = n_art_skip = n_fix = n_same = n_drop = n_bad = n_junk = 0
    report = []

    # 0) 先清掉占位符垃圾行（`*** löschen`、`n. ???` 这类，HanDeDict 的残缺条目）
    keep = []
    for w, g in rows:
        body = re.sub(r"^[A-Za-zÄÖÜäöüß]{1,10}\.\s+", "", g)
        if JUNK.search(body) or not re.search(r"[0-9A-Za-zÄÖÜäöüß]", body):
            n_junk += 1
            report.append(f"[清垃圾] {w}\t{g}")
            continue
        keep.append([w, g])
    rows = keep
    index = {w: i for i, (w, _) in enumerate(rows)}
    if n_junk:
        print(f"清掉占位符/空释义 {n_junk} 行")

    # 1) 新增缺口词
    for w, g in sorted(read_kv(os.path.join(HERE, "llm-gap.tsv")).items()):
        if w in index:
            continue
        index[w] = len(rows)
        rows.append([w, g])
        n_gap += 1
        report.append(f"[新增] {w}\t{g}")

    # 2) 名词补冠词
    art = read_kv(os.path.join(HERE, "llm-articles.tsv"))
    for w, gender in art.items():
        gender = gender.strip().lower()
        i = index.get(w)
        if i is None or gender not in ("der", "die", "das"):
            n_art_skip += 1
            continue
        g = rows[i][1]
        m = ART_LINE.match(g)
        if not m:
            n_art_skip += 1
            continue
        body = m.group(1)
        head, sep, tail = body.partition(";")          # 只动首个义项
        head = head.strip()
        if re.match(r"^(der|die|das)\s", head, re.I):
            n_art_skip += 1
            continue
        new_head = f"{gender} {head}"
        rows[i][1] = "n. " + new_head + (sep + tail if sep else "")
        n_art += 1
        report.append(f"[冠词] {w}\tn. {head} → n. {new_head}")

    # 3) 质检修正 / 删除
    #   模型很爱把名词冠词换个说法（鸭苗 das Entenküken → die Entenküken），这类「只动冠词」的改动
    #   没有依据、经常把对的改错，一律拒绝；冠词被 gender/nouns.csv 证实是对的，也拒绝。
    table, plurals, proper_only, _st = add_articles2.load_genders(add_articles2.GENDER_CSV)
    n_artflip = n_artref = n_pos = n_spell = 0
    for w, fix in sorted(read_kv(os.path.join(HERE, "llm-audit.tsv")).items()):
        i = index.get(w)
        if i is None:
            n_bad += 1
            continue
        old = rows[i][1]
        if fix.strip().upper() == "DROP":
            rows[i][1] = None
            n_drop += 1
            report.append(f"[删除] {w}\t{old}")
            continue
        fix = fix.strip()
        pm = POS_ANY.match(fix)
        if not (pm and pm.group(1).lower() in LEGAL_POS) and not re.match(r"^\d", fix):
            n_bad += 1
            report.append(f"[拒绝·词性非法] {w}\t{fix[:60]}")
            continue
        if fix == old:
            n_same += 1                                # 模型复述了原文 = 本来没问题
            continue
        # 词性不该被质检改动：原始词性来自 HanDeDict，模型改词性多半是改错（把成语/动词改成 n.）
        pm_old = POS_ANY.match(old)
        if pm_old and pm.group(1).lower() != pm_old.group(1).lower():
            n_pos += 1
            report.append(f"[拒绝·改词性] {w}\t{old} → {fix}")
            continue
        # 专名拼写：旧新都是单个拉丁词、又几乎不像同一个词（Elsa→Aisha 这类臆改）→ 拒绝
        ob, nb = POS_ANY.sub("", old, count=1).strip(), POS_ANY.sub("", fix, count=1).strip()
        if (" " not in ob and " " not in nb and len(ob) >= 3 and len(nb) >= 3
                and difflib.SequenceMatcher(None, ob.lower(), nb.lower()).ratio() < 0.6):
            n_spell += 1
            report.append(f"[拒绝·像臆改专名] {w}\t{old} → {fix}")
            continue
        mo = ART_HEAD.match(POS_ANY.sub("", old, count=1))
        mn = ART_HEAD.match(POS_ANY.sub("", fix, count=1))
        if mo and mn and mo.group(1).lower() != mn.group(1).lower():
            if mo.group(2).strip().lower() == mn.group(2).strip().lower():
                n_artflip += 1
                report.append(f"[拒绝·只换冠词] {w}\t{old} → {fix}")
                continue
            if old.startswith("n. "):
                ref, how = add_articles2.article_for(
                    add_articles2.head_token(old), table, plurals, proper_only)
                if ref and ref == mo.group(1).lower():
                    n_artref += 1
                    report.append(f"[拒绝·冠词表说是 {ref}（{how}）] {w}\t{old} → {fix}")
                    continue
        rows[i][1] = fix
        n_fix += 1
        report.append(f"[修正] {w}\n    旧: {old}\n    新: {fix}")

    rows = [r for r in rows if r[1]]
    print(f"新增缺口词 {n_gap:,}；补冠词 {n_art:,}（跳过 {n_art_skip:,}）；"
          f"质检修正 {n_fix:,}（复述原文忽略 {n_same:,}，非法拒绝 {n_bad:,}，"
          f"只换冠词拒绝 {n_artflip:,}，冠词表否决 {n_artref:,}，改词性拒绝 {n_pos:,}，"
          f"臆改专名拒绝 {n_spell:,}）；删除碎片 {n_drop:,}")
    print(f"结果 {len(rows):,} 行 → {args.out}")
    if args.apply:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            for w, g in rows:
                f.write(f"{w}\t{g}\n")
        with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(report) + "\n")
        print(f"写出 {args.out}（{os.path.getsize(args.out):,} B）与 {REPORT}（{len(report)} 条改动）")
    else:
        print("（预览模式，没写文件；加 --apply 才落地）")
        for line in report[:15]:
            print("   " + line.replace("\n", "\n   "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
