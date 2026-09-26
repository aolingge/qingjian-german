"""给德语释义表里的名词加定冠词（der / die / das）。

数据来源：gambolputty/german-nouns（~10 万德语名词，取自德语维基词典，CC-BY-SA-4.0）
    https://github.com/gambolputty/german-nouns  →  german_nouns/nouns.csv

做法是**只改释义文本**，不动词条与顺序：
  * 只处理词性前缀是 `n. ` 的行（其他词性不动，避免给专名乱加冠词）；
  * 把释义按 `;` / `,` 切成片段，片段是**单个首字母大写的德语词**（可选带结尾 `...`）才查表；
  * 查不到（复数形式、专名、短语）就原样保留——宁可不加，不加错。

用法：
    D:\\tools\\Miniconda\\python.exe E:\\codemain\\qingjian-de\\de-glossary\\add_articles.py
输出：
    E:\\codemain\\qingjian-de\\de-glossary\\glossary-de-art.tsv     （新表，UTF-8 无 BOM、LF）
    E:\\codemain\\qingjian-de\\de-glossary\\articles-report.txt      （统计与抽样对照）
"""
from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
GENDER_CSV = os.path.join(HERE, "gender", "nouns.csv")
TSV_IN = os.path.join(os.environ["APPDATA"], "Qingjian", "custom", "glossary-de-hd.tsv")
TSV_OUT = os.path.join(HERE, "glossary-de-art.tsv")
REPORT = os.path.join(HERE, "articles-report.txt")

ARTICLES = {"m": "der", "f": "die", "n": "das"}
SEGMENT = re.compile(r"^([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]*(?:\s[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]*)*)(\.\.\.)?$")
NOUN_PREFIX = "n. "


def load_genders(path: str) -> tuple[dict[str, str], Counter]:
    table: dict[str, str] = {}
    stats: Counter = Counter()
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            lemma = (row.get("lemma") or "").strip()
            pos = (row.get("pos") or "").strip()
            genus = (row.get("genus") or "").strip().lower()
            if not lemma or lemma.startswith("-"):
                continue
            if "Substantiv" not in pos:
                stats["非名词"] += 1
                continue
            if genus not in ARTICLES:
                stats["无性"] += 1
                continue
            article = ARTICLES[genus]
            if lemma in table and table[lemma] != article:
                stats["性冲突"] += 1
                continue  # 冲突的保守处理：留第一个
            table[lemma] = article
    return table, stats


def add_articles(gloss: str, table: dict[str, str], stats: Counter) -> str:
    """给 `n. ` 行里的裸名词加冠词；返回新的释义文本"""
    if not gloss.startswith(NOUN_PREFIX):
        stats["非 n. 行"] += 1
        return gloss
    body = gloss[len(NOUN_PREFIX):]
    # 括号里是补充说明（`(lat: …)`、`(S, Zool)`、中文解释里的举例），不是释义本身：
    # 只处理第一个 `(` 之前的部分，括号原样保留。
    cut = body.find("(")
    head, tail = (body, "") if cut < 0 else (body[:cut], body[cut:])
    out: list[str] = []
    for piece in re.split(r"([;,])", head):
        if piece in (";", ","):
            out.append(piece)
            continue
        stripped = piece.strip()
        if not stripped:
            out.append(piece)
            continue
        leading = piece[: len(piece) - len(piece.lstrip())]
        trailing = piece[len(piece.rstrip()):]
        match = SEGMENT.match(stripped)
        if not match:
            stats["片段非单词"] += 1
            out.append(piece)
            continue
        word, dots = match.group(1), match.group(2) or ""
        if re.search(r"\s", word):
            stats["片段多词"] += 1
            out.append(piece)
            continue
        # 全大写缩略语（CT / DVD / PC / X 射线里的 X）不加：词表里这类词的性不可靠
        # （`CT` 在源表里是 f，实际是 das CT），宁可空着也不写错。
        if word == word.upper():
            stats["缩略语"] += 1
            out.append(piece)
            continue
        article = table.get(word)
        if article is None:
            stats["查不到"] += 1
            out.append(piece)
            continue
        stats["加冠词"] += 1
        out.append(f"{leading}{article} {word}{dots}{trailing}")
    return NOUN_PREFIX + "".join(out) + tail


def main() -> int:
    table, gender_stats = load_genders(GENDER_CSV)
    print(f"名词表：{len(table)} 条（{dict(gender_stats)}）")

    stats: Counter = Counter()
    rows: list[tuple[str, str, str]] = []
    changed = 0
    with open(TSV_IN, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                rows.append((line, "", ""))
                continue
            parts = line.split("\t")
            word, gloss = parts[0], parts[1]
            new = add_articles(gloss, table, stats)
            if new != gloss:
                changed += 1
            rows.append((word, gloss, new))

    with open(TSV_OUT, "w", encoding="utf-8", newline="\n") as handle:
        for word, old, new in rows:
            handle.write(word if not old else f"{word}\t{new}")
            handle.write("\n")

    samples = [(w, o, n) for w, o, n in rows if o and n and o != n]
    report: list[str] = []
    report.append(f"名词表：{len(table)} 条  {dict(gender_stats)}")
    report.append(f"处理统计：{dict(stats)}")
    report.append(f"改动行数：{changed} / {len(samples)} 行有释义")
    report.append("")
    report.append("抽样（前 60 条改动）：")
    for word, old, new in samples[:60]:
        report.append(f"  {word}\t{old}\t→\t{new}")
    report.append("")
    report.append("抽样（改动里最长的 20 条）：")
    for word, old, new in sorted(samples, key=lambda r: -len(r[2]))[:20]:
        report.append(f"  {word}\t{old}\t→\t{new}")
    with open(REPORT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report) + "\n")

    print(f"改动 {changed} 行 → {TSV_OUT}")
    print(f"报告 → {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
