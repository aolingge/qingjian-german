"""生成 levels-de.tsv：`释义文本\\t等级`。

为什么键是「整条释义文本」而不是单个德语词：青简学习记录（`VocabularyBook`）按 `sense.text`
（也就是释义表里 `词性. ` 之后那整串）记账，偏好设置「统计」页用同一个串去 `LevelTable::rank()`
查等级（`crates\\qingjian-learning\\src\\vocabulary_book.rs:150`，`crates\\qingjian-translate\\src\\level_table.rs:73-84`
只做 to_lowercase + 日文词尾回退）。英文表能对上是因为英文释义多半是单个词（实测整串命中
23,124 / 232,213）；德语释义是 `das Auto, Wagen, der Kraftwagen` 这种整串，只能按整串建键。

等级来源：Goethe-Institut 5000 词表（voothi/20260716201616-german-5000，MIT，
`20260716200932-goethe-german-5000.de.tsv`，列 Word/Annotation/Sense/Part of Speech/Level/English，
Level = A1/A2/B1/B2+）。

匹配顺序（前者优先，命中即止）：
  1. 整串（`das Auto`）
  2. 第一段（`，`/`；`/`(` 之前）——含带冠词与去冠词两种写法
  3. 兜底：整串里任意一个实词命中，取**最易**的那一级（冠词/功能词不参与兜底）
没命中的释义不进表（统计页只按表里有的级别分档，其余仍计入总数）。

用法：
    python build_levels_de.py <goethe.tsv> <glossary-de-art.tsv> <out levels-de.tsv> [个人释义表.tsv ...]
（第 4 个及以后的 TSV 只补充条目，比如 `%APPDATA%\\Qingjian\\user-glossary-de.tsv`。）
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

LEVEL_ORDER = ["A1", "A2", "B1", "B2+", "C1", "C2"]
ARTICLES = ("der ", "die ", "das ", "den ", "dem ", "des ")
ARTICLE_WORDS = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines"}
POS_PREFIX = re.compile(r"^(?:n|v|adj|adv|int|pron|num|prep|conj|part|art|aux|onom|phrase|abbr)\.\s+")
TOKEN_SPLIT = re.compile(r"[\s,;()/\[\]\"']+")
TRIM = " \t!?.,;:…\"'()[]"


def rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)


def load_goethe(path: Path) -> dict[str, str]:
    """德语词形（含带冠词形式）-> 等级。同一词形出现在多级时取最易的一级。"""
    table: dict[str, str] = {}
    rows = path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split("\t")
    i_word, i_anno = header.index("Word"), header.index("Annotation")
    i_level = header.index("Level")

    def add(form: str, level: str) -> None:
        form = form.strip().strip(TRIM).lower()
        if not form:
            return
        old = table.get(form)
        if old is None or rank(level) < rank(old):
            table[form] = level

    for line in rows[1:]:
        cells = line.split("\t")
        if len(cells) <= max(i_word, i_anno, i_level):
            continue
        level = cells[i_level].strip()
        if not level:
            continue
        # `abbauen, baut ab, baute ab, hat abgebaut` -> 第一个形式就是原形
        for part in cells[i_word].split(","):
            add(part, level)
        # `der Abbau, -e` -> 带冠词的形式（加冠词后的释义就是这个写法）
        anno = cells[i_anno].split(",")[0]
        add(anno, level)
        bare = anno.lower()
        for art in ARTICLES:
            if bare.startswith(art):
                add(anno[len(art):], level)
                break
    return table


def first_segment(gloss: str) -> str:
    return re.split(r"[,;(]", gloss, maxsplit=1)[0].strip().strip(TRIM)


def variants(form: str) -> list[str]:
    out = [form]
    low = form.lower()
    for art in ARTICLES:
        if low.startswith(art):
            out.append(form[len(art):].strip())
            break
    no_paren = form.split("(")[0].strip().strip(TRIM)
    if no_paren and no_paren not in out:
        out.append(no_paren)
    return [v for v in out if v]


def match_level(table: dict[str, str], text: str) -> tuple[str | None, str]:
    whole = text.strip().strip(TRIM)
    for form in variants(whole):
        if form.lower() in table:
            return table[form.lower()], "整串"
    for form in variants(first_segment(whole)):
        if form.lower() in table:
            return table[form.lower()], "第一段"
    pre_paren = whole.split("(")[0]
    for tok in TOKEN_SPLIT.split(pre_paren):
        tok = tok.strip(TRIM)
        if not tok or tok.lower() in ARTICLE_WORDS:
            continue
        if tok.lower() in table:
            return table[tok.lower()], "兜底"
    return None, "未命中"


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    goethe, glossary, out_path = (Path(a) for a in sys.argv[1:4])
    extras = [Path(a) for a in sys.argv[4:]]
    table = load_goethe(goethe)

    matched: dict[str, str] = {}
    per_level: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    unmatched_samples: list[str] = []
    total = 0
    for path in [glossary, *extras]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            word, _, gloss = line.partition("\t")
            if not gloss:
                continue
            total += 1
            text = POS_PREFIX.sub("", gloss).strip()
            level, kind = match_level(table, text)
            kinds[kind] += 1
            if level is None:
                if len(unmatched_samples) < 10:
                    unmatched_samples.append(f"{word} -> {text}")
                continue
            key = text.lower()
            old = matched.get(key)
            if old is None:
                matched[key] = level
                per_level[level] += 1
            elif rank(level) < rank(old):
                per_level[old] -= 1
                per_level[level] += 1
                matched[key] = level

    levels = [l for l in LEVEL_ORDER if per_level.get(l)]
    lines = [
        "# 德语词汇等级（CEFR）。来源：Goethe-Institut 5000 词表（Goethe-Zertifikat A1–B2 词汇），",
        "# 经 https://github.com/voothi/20260716201616-german-5000 整理为 TSV（MIT License）；",
        "# 等级 A1–B2+ 是 Goethe-Institut 的划分。",
        "# 由 E:\\codemain\\qingjian-de\\de-glossary\\levels\\build_levels_de.py 生成。"
        "格式：词\\t等级；`# levels` 行是等级从易到难的顺序。",
        "# 注意：键是**释义整串**（青简按 `sense.text` 记账并查等级），不是单个德语词。",
        "# levels\t" + "\t".join(levels),
    ]
    for text in sorted(matched, key=lambda t: (rank(matched[t]), t)):
        lines.append(f"{text}\t{matched[text]}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(f"德语词形表：{len(table):,} 条")
    print(f"释义表总条数：{total:,}")
    print(f"能定级的释义：{len(matched):,}（{len(matched) / total:.1%}）")
    print("匹配方式：" + "，".join(f"{k} {v:,}" for k, v in kinds.most_common()))
    print("每级释义数：" + "，".join(f"{l} {per_level[l]:,}" for l in levels))
    print("未命中的样例：" + " | ".join(unmatched_samples[:6]))
    print(f"写出：{out_path}（{out_path.stat().st_size:,} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
