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
import llm_tools              # 复用它的英语表读取与词库词频（read_en / read_dict）

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "glossary-de-merged.tsv")
FINAL = os.path.join(HERE, "glossary-de-final.tsv")
REPORT = os.path.join(HERE, "apply-report.txt")
LEGAL_POS = ("n", "v", "adj", "adv", "int", "pron", "num", "prep", "conj", "part", "phr", "m")
SENSE_MIN_FREQ = 100          # 常用义修正只认词频 ≥100 的词：更生僻的词模型多半在猜（森饰→Waldschmuck）
POS_ANY = re.compile(r"^([A-Za-zÄÖÜäöüß]{1,10})\.\s")
ART_LINE = re.compile(r"^n\.\s+(.*)$")
# 真正的垃圾：占位符 / 只有符号（`*** löschen`、`n. ???`）。释义里出现 löschen、unbekannt 是正常译文
JUNK = re.compile(r"\*\*\*|\?{2,}|^\s*(n/?a|none|leer)\s*$", re.I)
ART_HEAD = re.compile(r"^(der|die|das)\s+(.*)$", re.I)
# 汉字/假名/谚文：德语列里只允许出现在「(scherzhaft für 朋友)」这类注释里，
# 但模型偶尔整条替换成中文（凉凉送 → v. (网络用语) 冷落、忽视）→ 旧文没有而新文有，一律拒绝
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]")


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


def compound_gender(token, table, plurals, proper_only):
    """连接式复合名词查性别：Steinmühle → 试后缀 Mühle；Nasenverstopfung → Verstopfung。

    只在整词查不到时才用；后缀必须大写开头（德语复合名词的最后一个成分总是名词）。
    """
    if not token or " " in token or "\t" in token:
        return None, ""
    for i in range(3, len(token) - 3):          # 从最长的后缀开始试（Stein|mühle → Mühle）
        cand = token[i:]
        if len(cand) < 4:
            break
        cap = cand[:1].upper() + cand[1:]       # 复合词内部的名词是小写的：mühle → Mühle
        ref, how = add_articles2.article_for(cap, table, plurals, proper_only)
        if ref:
            return ref, "复合词后缀 %s（%s）" % (cap, how)
    return None, ""


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
    n_artflip = n_artref = n_pos = n_spell = n_cjk = n_artok = 0
    n_verify = n_verify_trim = 0
    audit_fixes = read_kv(os.path.join(HERE, "llm-audit.tsv"))
    verify_fixes = read_kv(os.path.join(HERE, "llm-verify.tsv"))     # 生僻词复核（第八轮新增）
    for w in sorted(set(audit_fixes) | set(verify_fixes)):
        # 质检阶段（audit）优先，但它「原样复述」时不算结论——生僻词复核（verify）经常才是
        # 真发现问题的那一路，不能被复述短路掉（石磨：audit 说原文没错、verify 说冠词错了）。
        i = index.get(w)
        if i is None:
            n_bad += 1
            continue
        old = rows[i][1]
        from_verify = False
        fix = audit_fixes.get(w)
        if fix is None or fix.strip() == old:
            v = verify_fixes.get(w)
            if v is not None and v.strip() != old:
                fix = v
                from_verify = True
        if fix is None:
            fix = audit_fixes.get(w) or verify_fixes[w]   # 两路都等于原文：按「复述」统计
        if fix.strip().upper() == "DROP":
            if from_verify:                          # 复核阶段不许删条目（生僻词删了就是没译文）
                n_verify_trim += 1
                report.append(f"[复核·不动条目] {w}\t{old}")
                continue
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
        if CJK.search(nb) and not CJK.search(ob):
            n_cjk += 1
            report.append(f"[拒绝·新释义混中文] {w}\t{old} → {fix}")
            continue
        if (" " not in ob and " " not in nb and len(ob) >= 3 and len(nb) >= 3
                and difflib.SequenceMatcher(None, ob.lower(), nb.lower()).ratio() < 0.6):
            n_spell += 1
            report.append(f"[拒绝·像臆改专名] {w}\t{old} → {fix}")
            continue
        # 复核阶段只认「换了个说法」：新释义只是旧释义的删减（没有新信息）时不动——
        # HanDeDict 的原始条目是人工写的，模型多半只是嫌长（恪守 → 去掉一整个义项）。
        if from_verify and len(nb) >= 3 and nb.lower() in ob.lower():
            n_verify_trim += 1
            report.append(f"[复核·只做了删减] {w}\t{ob} → {nb}")
            continue
        mo = ART_HEAD.match(POS_ANY.sub("", old, count=1))
        mn = ART_HEAD.match(POS_ANY.sub("", fix, count=1))
        # 冠词检查只管「正文没换、只换了冠词」这一种：换掉整个中心词时（一揽子 der Geschäftsbereich
        # → das Gesamtpaket）旧的冠词不再是证据，硬拿它否决会把真改进挡掉。
        if (mo and mn and mo.group(1).lower() != mn.group(1).lower()
                and mo.group(2).strip().lower() == mn.group(2).strip().lower()):
            ref = how = None
            if old.startswith("n. "):
                head = add_articles2.head_token(old)
                hm = ART_HEAD.match(head)          # head_token 不去冠词，article_for 见到冠词会直接返回
                if hm:
                    head = hm.group(2).strip()
                ref, how = add_articles2.article_for(head, table, plurals, proper_only)
                if not ref:                       # 复合词：Steinmühle → 后缀 Mühle
                    ref, how = compound_gender(head, table, plurals, proper_only)
            if ref and ref == mn.group(1).lower():
                # 名词表证实「新的那个」才对（das Wegweiser → der Wegweiser）→ 采纳
                rows[i][1] = fix
                n_fix += 1
                if from_verify:
                    n_verify += 1
                n_artok += 1
                report.append(f"[{'复核' if from_verify else '修正'}·冠词表说是 {ref}（{how}）] "
                              f"{w}\t{old} → {fix}")
                continue
            if ref and ref == mo.group(1).lower():
                n_artref += 1
                report.append(f"[拒绝·冠词表说是 {ref}（{how}）] {w}\t{old} → {fix}")
                continue
            # 没有证据的冠词翻转一律不动（第六轮的结论：模型换冠词多半是把对的改错）
            n_artflip += 1
            report.append(f"[拒绝·只换冠词] {w}\t{old} → {fix}")
            continue
        rows[i][1] = fix
        n_fix += 1
        if from_verify:
            n_verify += 1
        report.append(f"[{'复核' if from_verify else '修正'}] {w}\n    旧: {old}\n    新: {fix}")

    rows = [r for r in rows if r[1]]

    # 4) 常用义修正（sense）
    #    模型拿英语表当第二意见，指出「这条词给的德语是生僻义」。落地规则：
    #    A 词性不变 → 把**旧表里没有的**新义项插到最前面，旧义项原样保留（纯增信息，最坏是多一个义项）
    #    B 词性变了 → 只有英语表也支持新词性、且不支持旧词性、且词频 ≥1000 时才整体替换（有独立佐证）
    en, freq = llm_tools.read_en(), dict(llm_tools.read_dict())
    n_sense = n_sense_noop = n_sense_pos = n_sense_bad = 0

    def toks(body):
        return [s.strip() for s in re.split(r"[;,，、]", body) if s.strip()]

    def tkey(s):
        return ART_HEAD.sub(r"\2", s).strip().lower()      # 比义项时忽略冠词，der Tag == Tag

    def dup(s, olds):
        # 完全相同，或只是带/不带括注、多一个词尾（der Sporn vs der Sporn (Reitsport)、autsch vs autsch !）
        k = tkey(s)
        return any(k == tkey(o) or (len(k) >= 3 and (tkey(o).startswith(k) or k.startswith(tkey(o))))
                   for o in olds)

    n_sense_rare = n_sense_art = 0
    for w, fix in sorted(read_kv(os.path.join(HERE, "llm-sense.tsv")).items()):
        i = index.get(w)
        if i is None:
            n_sense_bad += 1
            continue
        if freq.get(w, 0) < SENSE_MIN_FREQ:                # 生僻词模型多半在硬猜（森饰→Waldschmuck），不采纳
            n_sense_rare += 1
            continue
        old, fix = rows[i][1], fix.strip()
        pm_new, pm_old = POS_ANY.match(fix), POS_ANY.match(old)
        if not (pm_new and pm_new.group(1).lower() in LEGAL_POS):
            n_sense_bad += 1
            report.append(f"[拒绝·词性非法] {w}\t{fix[:60]}")
            continue
        pos_new = pm_new.group(1).lower()
        pos_old = pm_old.group(1).lower() if pm_old else ""
        new_s, old_s = toks(POS_ANY.sub("", fix, count=1)), toks(POS_ANY.sub("", old, count=1))
        missing = [s for s in new_s if not dup(s, old_s)]
        if not missing:
            n_sense_noop += 1                              # 常用义其实已经有了
            continue
        kept = []
        for s in missing:
            if not dup(s, kept):
                kept.append(s)
        missing = kept
        # 新义项里的名词冠词用冠词表核一遍：表里**整词命中**又和模型给的冠词不一致时，整条新义项丢掉。
        # （改写成表里的冠词反而更糟：der Vorgesetzte/Angestellte/Erwachsene 这类弱变化名词表里记的是阴性，
        #  289 条改写里大半会把对的改错；只丢不加，最坏是少一条义项。）
        fixed = []
        for s in missing:
            if CJK.search(s) and not CJK.search(old):
                n_cjk += 1
                report.append(f"[常用义·新义混中文，丢掉] {w}\t{s}")
                continue
            m = ART_HEAD.match(s)
            if m:
                ref, how = add_articles2.article_for(
                    add_articles2.head_token("n. " + m.group(2)), table, plurals, proper_only)
                if ref and how == "整词命中" and ref != m.group(1).lower():
                    n_sense_art += 1
                    report.append(f"[常用义·冠词表说 %s，丢掉] {w}\t{s}" % ref)
                    continue
            fixed.append(s)
        missing = fixed
        if not missing:
            n_sense_noop += 1
            continue
        if pos_new != pos_old:
            en_pos = {p.lower() for p in POS_ANY.findall(" ".join(en.get(w, "")))}
            if not (pos_new in en_pos and pos_old not in en_pos and freq.get(w, 0) >= 1000):
                n_sense_pos += 1
                report.append(f"[拒绝·改词性无佐证] {w}\t{old} → {fix}")
                continue
            rows[i][1] = f"{pos_new}. " + "; ".join(missing[:3])
            n_sense += 1
            report.append(f"[常用义·换词性] {w}\t旧: {old}\n    新: {rows[i][1]}")
            continue
        rows[i][1] = f"{pos_old}. " + "; ".join((missing + old_s)[:4])
        n_sense += 1
        report.append(f"[常用义] {w}\t旧: {old}\n    新: {rows[i][1]}")

    # 5) 手工覆盖（fixes.tsv）：自检发现的、模型四轮都没修对的硬错误（冠词与 german-nouns 相反、
    #    德语列写成中文、专名没有词性前缀导致定不了级）——人手核过，放在最后一步，优先级最高。
    n_manual = 0
    for w, g in sorted(read_kv(os.path.join(HERE, "fixes.tsv")).items()):
        i = index.get(w)
        if i is None:
            report.append(f"[手工覆盖·词表里没有] {w}\t{g}")
            continue
        if rows[i][1] == g:
            continue
        report.append(f"[手工覆盖] {w}\n    旧: {rows[i][1]}\n    新: {g}")
        rows[i][1] = g
        n_manual += 1

    print(f"新增缺口词 {n_gap:,}；补冠词 {n_art:,}（跳过 {n_art_skip:,}）；"
          f"质检修正 {n_fix:,}（复述原文忽略 {n_same:,}，非法拒绝 {n_bad:,}，"
          f"只换冠词拒绝 {n_artflip:,}，冠词表否决 {n_artref:,}，改词性拒绝 {n_pos:,}，"
          f"臆改专名拒绝 {n_spell:,}，混中文拒绝 {n_cjk:,}）；删除碎片 {n_drop:,}；"
          f"其中生僻词复核采纳 {n_verify:,}（删减拒绝 {n_verify_trim:,}，冠词表证实并采纳 {n_artok:,}）；"
          f"常用义修正 {n_sense:,}（已覆盖忽略 {n_sense_noop:,}，词频<{SENSE_MIN_FREQ} 跳过 {n_sense_rare:,}，"
          f"改词性无佐证拒绝 {n_sense_pos:,}，冠词表不一致丢掉 {n_sense_art:,}，非法/缺词 {n_sense_bad:,}）；"
          f"手工覆盖 {n_manual:,}")
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
