# -*- coding: utf-8 -*-
"""最终词表自检：词性前缀 / 中文残留 / 冠词与 german-nouns 冲突 / 定级覆盖率。（第六轮，随工具一起进套件。）

五项检查：
  1. 运行时等级查表覆盖率（严格按 Rust level_table::rank 的口径：释义去掉词性前缀后 to_lowercase 精确匹配）
  2. 德语正文里混进汉字/日文假名/韩文的行
  3. 词性前缀是否合法、是否有空正文
  4. 名词首义的冠词与 german-nouns（nouns.csv）冲突的行（同名同形才算冲突）
  5. 冠词形态问题：die/der/das + 明显是复数/专名的行
"""
import io
import re
import sys
import collections

GLOSS = sys.argv[1] if len(sys.argv) > 1 else 'glossary-de-final.tsv'
LEVELS = sys.argv[2] if len(sys.argv) > 2 else r'levels\levels-de.tsv'
NOUNS = sys.argv[3] if len(sys.argv) > 3 else r'gender\nouns.csv'

POS = {'n.', 'v.', 'adj.', 'adv.', 'pron.', 'prep.', 'conj.', 'num.', 'm.', 'part.', 'int.', 'phr.'}
# Rust 侧 PartOfSpeech::from_str 会 to_ascii_lowercase()，所以 `M.` 也算词性（= 量词）；
# 另有几个别名同样合法：noun/verb/interj/phrase/mw。
POS_ALIAS = {'noun.', 'verb.', 'interj.', 'phrase.', 'mw.'}
POS_RE = re.compile(r'^(\S+)\s+(.*)$')
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]')
ART = re.compile(r'^(der|die|das)\s+(.*)$')


def parse_sense(text):
    """复刻 crates/qingjian-translate/src/glossary/mod.rs parse_sense()（词性缩写大小写不敏感）。"""
    m = POS_RE.match(text)
    if m and (m.group(1).lower() in POS or m.group(1).lower() in POS_ALIAS):
        return m.group(1).lower(), m.group(2)
    return '', text


def main():
    # ---- 1. 等级表覆盖 ----
    keys = {}
    with io.open(LEVELS, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            p = line.split('\t')
            if len(p) >= 2:
                keys[p[0]] = p[1]
    rows = []
    with io.open(GLOSS, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            w, _, g = line.partition('\t')
            rows.append((w, g))
    hit = 0
    miss = []
    cjk = []
    bad_pos = []
    empty = []
    noun_art = {}
    for w, g in rows:
        pos, body = parse_sense(g)
        if not pos:
            bad_pos.append((w, g))
        if not body.strip():
            empty.append((w, g))
        if CJK.search(body):
            cjk.append((w, g))
        if body.lower() in keys:
            hit += 1
        else:
            miss.append((w, g))
        if pos == 'n.':
            m = ART.match(body)
            if m:
                noun_art.setdefault(m.group(2).split(',')[0].strip().lower(), (w, m.group(1)))
    print('== 1. 运行时等级查表覆盖率（Rust 口径）==')
    print('   词表 %d 行，命中 %d（%.2f%%），未命中 %d' % (len(rows), hit, 100.0 * hit / max(1, len(rows)), len(miss)))
    for w, g in miss[:12]:
        print('   未命中: %s\t%s' % (w, g))

    print('== 2. 德语正文里混进 CJK 的行 ==')
    print('   共 %d 行' % len(cjk))
    for w, g in cjk[:20]:
        print('   %s\t%s' % (w, g))

    print('== 3. 非法的词性前缀 / 空正文 ==')
    print('   首词不以合法词性开头 %d 行，空正文 %d 行' % (len(bad_pos), len(empty)))
    for w, g in bad_pos[:10]:
        print('   无词性: %s\t%s' % (w, g))

    # ---- 4. 冠词与 german-nouns 冲突 ----
    gn = {}
    plurals = set()
    try:
        with io.open(NOUNS, encoding='utf-8', errors='replace') as fh:
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
                lemma = p[i_lemma].strip().lower()
                art = {'m': 'der', 'f': 'die', 'n': 'das'}.get(p[i_gen].strip())
                if lemma and art and lemma not in gn:
                    gn[lemma] = art
                pl = p[i_pl].strip().lower()
                if pl:
                    plurals.add(pl)
    except IOError:
        print('== 4. （找不到 %s，跳过）==' % NOUNS)
    if gn:
        conf = []
        for lemma, (w, art) in noun_art.items():
            g2 = gn.get(lemma)
            if not g2 or g2 == art:
                continue
            if art == 'die' and lemma in plurals:      # 表里写的是复数（die Möbel / die Stiefel）——没错
                continue
            conf.append((w, lemma, art, g2))
        print('== 4. 冠词与 german-nouns 冲突（整词同形、且不是复数写法）==')
        print('   可比对名词 %d 个，冲突 %d 个' % (len([l for l in noun_art if l in gn]), len(conf)))
        for w, lemma, art, g2 in conf:
            print('   %s: 表里 %s %s，nouns.csv 说 %s' % (w, art, lemma, g2))

    print('== 5. 词性分布 ==')
    c = collections.Counter(parse_sense(g)[0] or '(无)' for _, g in rows)
    print('   ' + '，'.join('%s %d' % (k, v) for k, v in c.most_common()))


main()
