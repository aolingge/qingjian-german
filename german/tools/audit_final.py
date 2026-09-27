# -*- coding: utf-8 -*-
"""最终词表自检（第七轮扩展版，随工具一起进套件）。

十项检查，全部只看最终产物，不联网：
   1. 运行时等级查表覆盖率（严格按 Rust level_table::rank 的口径：释义去掉词性前缀后 to_lowercase 精确匹配）
   2. 德语正文里混进 CJK / 全角标点（中文残留信号）
   3. 词性前缀是否合法、是否有空正文、词性与正文是否矛盾（`v.`/`adj.` 却以冠词开头…）
   4. 名词首义的冠词与 german-nouns（nouns.csv）冲突的行 + 一致率
   5. 词性分布
   6. 德语名词大小写：小写名词（german-nouns 里查得到）出现在正文里
   7. 变音字母被改写成 ae/oe/ue（改写成变音写法后能在 german-nouns 里查到，说明原文是错的）
   8. 格式：连续空格 / 行尾空格 / 正文以逗号分号结尾 / 正文首尾多余空白
   9. 重复：完全相同的行、同一个中文词出现多行
  10. 等级表自检：重复键、非法等级值、键形态

用法：python audit_final.py [词表] [等级表] [nouns.csv]
"""
import io
import os
import re
import sys
import collections

GLOSS = sys.argv[1] if len(sys.argv) > 1 else 'glossary-de-final.tsv'
LEVELS = sys.argv[2] if len(sys.argv) > 2 else r'levels\levels-de.tsv'
NOUNS = sys.argv[3] if len(sys.argv) > 3 else r'gender\nouns.csv'
EN_GLOSSARY = (sys.argv[4] if len(sys.argv) > 4 else
               r'C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926\assets\glossary\glossary-en.tsv')

POS = {'n.', 'v.', 'adj.', 'adv.', 'pron.', 'prep.', 'conj.', 'num.', 'm.', 'part.', 'int.', 'phr.'}
# Rust 侧 PartOfSpeech::from_str 会 to_ascii_lowercase()，所以 `M.` 也算词性（= 量词）；
# 另有几个别名同样合法：noun/verb/interj/phrase/mw。
POS_ALIAS = {'noun.', 'verb.', 'interj.', 'phrase.', 'mw.'}
POS_RE = re.compile(r'^(\S+)\s+(.*)$')
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]')
FULLWIDTH = re.compile(u'[\uff0c\u3001\uff1b\uff1a\uff08\uff09\u3010\u3011\uff01\uff1f]')
# 弯引号（’‘“”）是正常的英文/德文排版写法（People’s、King’s、Cramer’sche），不算中文残留，单独统计
TYPOQUOTE = re.compile(u'[\u2018\u2019\u201c\u201d]')
ART = re.compile(r'^(der|die|das)\s+(.*)$')
LEVELS_OK = {'A1', 'A2', 'B1', 'B2', 'C1', 'C2'}
WORD_RE = re.compile(r"[A-Za-z\u00c0-\u024f\u00df][A-Za-z\u00c0-\u024f\u00df'\u2019-]*")
# 冠词后紧跟的词：这个位置上的德语名词必须大写
ART_NEXT = re.compile(r"\b(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer)\s+([A-Za-z\u00c0-\u024f\u00df][\w\u00c0-\u024f-]*)")
NOUN_STOP = set('''die der das von am des dem den und in im an auf mit zu zur zum aus bei nach seit ueber unter vor fuer
ist sind war wird werden ein eine einen einem einer nicht nur auch aber oder als wie wenn dass man sich es sie er wir
ihr ich du x y z a b c d e f g h i j k l m n o p q r s t u v w'''.split())


def parse_sense(text):
    """复刻 crates/qingjian-translate/src/glossary/mod.rs parse_sense()（词性缩写大小写不敏感）。"""
    m = POS_RE.match(text)
    if m and (m.group(1).lower() in POS or m.group(1).lower() in POS_ALIAS):
        return m.group(1).lower(), m.group(2)
    return '', text


def load_gloss(path):
    rows = []
    with io.open(path, encoding='utf-8') as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip('\n')
            if not line:
                continue
            w, _, g = line.partition('\t')
            rows.append((w, g, n))
    return rows


def load_nouns(path):
    """-> (lemma->冠词, 复数写法集合, 全部 lemma 小写集合, 大写写法集合)"""
    gn, plurals, lemmas, caps = {}, set(), set(), set()
    with io.open(path, encoding='utf-8', errors='replace') as fh:
        cols = [c.strip().lower() for c in fh.readline().rstrip('\n').split(',')]
        try:
            i_lemma, i_gen = cols.index('lemma'), cols.index('genus')
            i_pl = cols.index('nominativ plural')
        except ValueError:
            i_lemma, i_gen, i_pl = 0, 2, 16
        for line in fh:
            p = line.rstrip('\n').split(',')
            if len(p) <= max(i_lemma, i_gen, i_pl):
                continue
            lemma = p[i_lemma].strip()
            if not lemma:
                continue
            low = lemma.lower()
            lemmas.add(low)
            caps.add(lemma[:1].upper() + lemma[1:])
            art = {'m': 'der', 'f': 'die', 'n': 'das'}.get(p[i_gen].strip())
            if art and low not in gn:
                gn[low] = art
            pl = p[i_pl].strip().lower()
            if pl:
                plurals.add(pl)
    return gn, plurals, lemmas, caps


def umlaut_variants(tok):
    """把 ae/oe/ue 换回变音写法，返回候选（不处理 ss→ß，那需要词表对照）。"""
    out = set()
    for a, b in (('ae', u'\u00e4'), ('oe', u'\u00f6'), ('ue', u'\u00fc')):
        if a in tok:
            out.add(tok.replace(a, b))
    return out


def main():
    rows = load_gloss(GLOSS)

    # ---- 1. 等级表覆盖 ----
    keys, lv_bad, lv_dup = {}, [], []
    with io.open(LEVELS, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            p = line.split('\t')
            if len(p) < 2:
                lv_bad.append((line, ''))
                continue
            if p[1] not in LEVELS_OK:
                lv_bad.append((p[0], p[1]))
            if p[0] in keys:
                lv_dup.append(p[0])
            keys[p[0]] = p[1]

    hit, miss = 0, []
    cjk, fullw = [], []
    no_pos, empty, clash = [], [], []
    noun_art = {}
    lower_noun, umlaut = [], []
    fmt = []
    for w, g, n in rows:
        pos, body = parse_sense(g)
        if not pos:
            no_pos.append((w, g))
        if not body.strip():
            empty.append((w, g))
        if CJK.search(body):
            cjk.append((w, g))
        if FULLWIDTH.search(body):
            fullw.append((w, g))
        if body != body.strip() or '  ' in body:
            fmt.append((w, g))
        if body.rstrip().endswith((',', ';', '、')):
            fmt.append((w, g))
        if body.lower() in keys:
            hit += 1
        else:
            miss.append((w, g))
        if pos in ('v.', 'adj.') and ART.match(body):
            clash.append((w, g))
        if pos == 'n.':
            m = ART.match(body)
            if m:
                noun_art.setdefault(m.group(2).split(',')[0].strip().lower(), (w, m.group(1)))

    print('== 1. 运行时等级查表覆盖率（Rust 口径）==')
    print('   词表 %d 行，命中 %d（%.2f%%），未命中 %d' % (len(rows), hit, 100.0 * hit / max(1, len(rows)), len(miss)))
    for w, g in miss[:12]:
        print('   未命中: %s\t%s' % (w, g))

    print('== 2. 德语正文里混进 CJK / 全角标点 ==')
    nq = sum(1 for _, g, _ in rows if TYPOQUOTE.search(parse_sense(g)[1]))
    print('   CJK %d 行，中文全角标点 %d 行，弯引号（正常排版）%d 行' % (len(cjk), len(fullw), nq))
    for w, g in cjk[:12]:
        print('   CJK: %s\t%s' % (w, g))
    for w, g in fullw[:8]:
        print('   全角: %s\t%s' % (w, g))

    print('== 3. 词性前缀 / 空正文 ==')
    print('   无词性 %d 行（HanDeDict 原表写法，预期），空正文 %d 行' % (len(no_pos), len(empty)))
    print('   说明：`v.`|`adj.` 释义以冠词开头 %d 行属合法德语（`adj. der letzte`、`v. das letzte Wort haben`），仅作统计。'
          % len(clash))

    # ---- 4. 冠词与 german-nouns ----
    gn, plurals, lemmas, caps = load_nouns(NOUNS)
    comparable, agree, conf = 0, 0, []
    for lemma, (w, art) in noun_art.items():
        g2 = gn.get(lemma)
        if not g2:
            continue
        comparable += 1
        if g2 == art:
            agree += 1
        elif art == 'die' and lemma in plurals:
            agree += 1
        else:
            conf.append((w, lemma, art, g2))
    print('== 4. 冠词与 german-nouns ==')
    print('   可比对 %d 个，一致 %d（%.2f%%），冲突 %d 个'
          % (comparable, agree, 100.0 * agree / max(1, comparable), len(conf)))
    for w, lemma, art, g2 in conf:
        print('   冲突: %s\t表里 %s %s，nouns.csv 说 %s' % (w, art, lemma, g2))

    print('== 5. 词性分布 ==')
    c = collections.Counter(parse_sense(g)[0] or '(无)' for _, g, _ in rows)
    print('   ' + '，'.join('%s %d' % (k, v) for k, v in c.most_common()))

    # ---- 6/7. 大小写与变音字母 ----
    # 大小写：只查「冠词后的小写外来词（英语词条）」。德语本土名词的小写没法自动判定：
    # 冠词后面跟形容词本来就小写（ein kleiner Teil），而 german-nouns 又把 Klein/Für/Alt
    # 这类专名收成名词，任何「小写词 ∈ nouns.csv」的判定都会得出成百上千条假阳性。
    en_words = set()
    if os.path.isfile(EN_GLOSSARY):
        with io.open(EN_GLOSSARY, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if line.startswith('#'):
                    continue
                en_words.add(line.split('\t')[0].strip().lower())
    for w, g, n in rows:
        pos, body = parse_sense(g)
        if en_words:
            for tok in ART_NEXT.findall(body):
                if tok[:1].islower() and len(tok) > 2 and tok.lower() in en_words:
                    lower_noun.append((w, g, tok))
        for tok in WORD_RE.findall(body):
            if tok[:1].isupper():
                continue
            for var in umlaut_variants(tok.lower()):
                if var in lemmas:
                    umlaut.append((w, g, tok, var))
    print('== 6. 德语名词大小写（只能对照检查）==')
    print('   冠词后小写、且该小写词是英语词条（借词漏大写）的候选：%d 处' % len(lower_noun))
    for w, g, tok in lower_noun[:20]:
        print('   %s\t%s   (应为 %s)' % (w, g, tok[:1].upper() + tok[1:]))
    print('   说明：德语本土名词小写无法自动判定——德语形容词跟在冠词后本来就小写（ein kleiner Teil、'
          'die drei Punkte），而 german-nouns 把 Klein/Für/Alt 这类专名也收成名词，自动判定的结果全是假阳性，'
          '所以这一项只做借词对照，其余人工抽查。')
    print('== 7. 变音字母被写成 ae/oe/ue ==')
    print('   共 %d 处（%d 个中文词）' % (len(umlaut), len(set(x[0] for x in umlaut))))
    seen = set()
    for w, g, tok, var in umlaut:
        if w in seen:
            continue
        seen.add(w)
        if len(seen) <= 20:
            print('   %s\t%s   (应为 %s)' % (w, g, var))

    # ---- 8. 格式 ----
    print('== 8. 格式问题（首尾空白 / 连续空格 / 以逗号分号结尾）==')
    print('   共 %d 行' % len(fmt))
    for w, g in fmt[:15]:
        print('   格式: %r\t%r' % (w, g))

    # ---- 9. 重复 ----
    dup_line = collections.Counter((w, g) for w, g, _ in rows)
    dup_line = [(wg, n) for wg, n in dup_line.items() if n > 1]
    dup_word = collections.Counter(w for w, _, _ in rows)
    dup_word = [(w, n) for w, n in dup_word.items() if n > 1]
    print('== 9. 重复 ==')
    print('   完全相同的行 %d 组，同一个中文词出现多行 %d 个' % (len(dup_line), len(dup_word)))
    for (w, g), n in dup_line[:10]:
        print('   重复行 x%d: %s\t%s' % (n, w, g))
    for w, n in dup_word[:10]:
        print('   同词 x%d: %s' % (n, w))

    # ---- 10. 等级表自检 ----
    print('== 10. 等级表自检 ==')
    print('   键 %d 个，重复键 %d 个，非法等级 %d 个，含 CJK 的键 %d 个'
          % (len(keys), len(lv_dup), len(lv_bad), sum(1 for k in keys if CJK.search(k))))
    for k in lv_dup[:10]:
        print('   重复键: %s' % k)
    for k, v in lv_bad[:10]:
        print('   非法等级: %s -> %r' % (k[:60], v))


main()
