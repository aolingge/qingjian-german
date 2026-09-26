"""一次性体检：当前德语词表 / 词库 / 等级表的全部缺口口径与样本。

用法： python gaps_now.py [glossary.tsv] [dict.tsv] [levels-de.tsv] [user-glossary-de.tsv]
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

DEF_GLOSS = r"E:\codemain\qingjian-de\de-glossary\glossary-de-merged.tsv"
DEF_DICT = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926\assets\lexicon\dict.tsv"
DEF_LEVELS = r"D:\application\Qingjian\assets\levels\levels-de.tsv"
DEF_USER = r"C:\Users\aolin\AppData\Roaming\Qingjian\user-glossary-de.tsv"

POS_PREFIX = re.compile(r"^(?:n|v|adj|adv|int|pron|num|prep|conj|part|art|aux|onom|phrase|abbr)\.\s+")
ARTICLES = ("der ", "die ", "das ", "den ", "dem ", "des ")
DET = re.compile(r"^(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines|dein|mein|sein|ihr|unser|euer|"
                 r"kein|dieser|diese|dieses|jeder|jede|jedes|welcher|welche|welches|zwei|drei|vier|fünf|sechs|"
                 r"sieben|acht|neun|zehn|man|es|du|er|sie|wir|ihr)\s+", re.I)


def read_gloss(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        word, _, gloss = line.partition("\t")
        if gloss:
            rows.append((word, gloss))
    return rows


def first_sense(gloss: str) -> str:
    """`n. die Schule, -n` -> `die Schule`；多个词性取第一段。"""
    body = POS_PREFIX.sub("", gloss)
    return re.split(r"[;；]", body, maxsplit=1)[0].strip()


def head_noun(sense: str) -> str:
    """取首义里第一个实词（去冠词、去括号、去变格尾）。"""
    s = sense.split(",")[0].split("(")[0].strip()
    s = DET.sub("", s).strip()
    return s.split()[0].strip(" -–—") if s.split() else ""


def main() -> int:
    gloss_p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEF_GLOSS)
    dict_p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEF_DICT)
    levels_p = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(DEF_LEVELS)
    user_p = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(DEF_USER)

    gloss = read_gloss(gloss_p)
    print(f"词表：{gloss_p}")
    print(f"  条目 {len(gloss):,}；去重词头 {len({w for w, _ in gloss}):,}；"
          f"去重释义 {len({g for _, g in gloss}):,}")
    pos = Counter(POS_PREFIX.match(g).group(0).strip(" .") if POS_PREFIX.match(g) else "(无)" for _, g in gloss)
    print("  词性分布：" + "，".join(f"{k} {v:,}" for k, v in pos.most_common()))

    # —— 词库缺口 ——
    if dict_p.is_file():
        dict_rows = []
        for line in dict_p.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):     # dict.tsv 开头有几行 `# 来源：…` 注释
                continue
            cells = line.split("\t")
            if len(cells) >= 1 and cells[0].strip():
                freq = int(cells[2]) if len(cells) > 2 and cells[2].strip().isdigit() else 0
                dict_rows.append((cells[0].strip(), freq))
        have = {w for w, _ in gloss}
        missing = [(w, f) for w, f in dict_rows if w not in have]
        print(f"词库：{dict_p}")
        print(f"  词条 {len(dict_rows):,}；有德语 {len(dict_rows) - len(missing):,}"
              f"（{(len(dict_rows) - len(missing)) / len(dict_rows):.2%}）；缺德语 {len(missing):,}")
        missing.sort(key=lambda t: -t[1])
        print("  缺口里词频最高的 25 个：" + " ".join(f"{w}({f:,})" for w, f in missing[:25]))
        print("  缺口词频分档：" + "，".join(
            f"≥{th:,}: {sum(1 for _, f in missing if f >= th):,}" for th in (10000, 1000, 100, 10, 1)))
        print("  缺口里单字/拉丁/含空格的：" +
              "，".join(f"{k} {v:,}" for k, v in Counter(
                  "单字" if len(w) == 1 else "拉丁" if re.fullmatch(r"[A-Za-z0-9.\-]+", w) else
                  "含空格" if " " in w else "其他" for w, _ in missing).most_common()))
        print("  低频缺口样例(20)：" + " ".join(w for w, _ in missing[-20:]))
    else:
        print(f"词库缺失：{dict_p}")

    # —— 冠词缺口 ——
    noun_rows = [(w, g) for w, g in gloss if g.startswith("n. ")]
    no_art = [(w, g) for w, g in noun_rows if not g[3:].lower().startswith(ARTICLES)]
    print(f"名词性首义 {len(noun_rows):,}；其中首义无冠词 {len(no_art):,}")
    ok_head = [(w, g) for w, g in no_art if head_noun(first_sense(g))]
    print(f"  无冠词里能取出首词干的 {len(ok_head):,}")
    print("  无冠词样例(15)：" + " | ".join(f"{w}→{g}" for w, g in no_art[:15]))
    multi = [(w, g) for w, g in no_art if re.search(r"[,;]| und ", first_sense(g))]
    print(f"  无冠词中首义含多词/并列的 {len(multi):,}；样例：" + " | ".join(f"{w}→{g}" for w, g in multi[:8]))

    # —— 等级表覆盖 ——
    lv_keys = {}
    if levels_p.is_file():
        for line in levels_p.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("\t")
            lv_keys[k.lower()] = v
    all_senses = {}
    for w, g in gloss:
        all_senses.setdefault(POS_PREFIX.sub("", g).strip().lower(), w)
    if user_p.is_file():
        for w, g in read_gloss(user_p):
            all_senses.setdefault(POS_PREFIX.sub("", g).strip().lower(), w)
    hit = [k for k in all_senses if k in lv_keys]
    print(f"等级表：{levels_p}")
    print(f"  表内键 {len(lv_keys):,}；词表去重释义 {len(all_senses):,}；"
          f"精确命中 {len(hit):,}（{len(hit) / len(all_senses):.1%}）")
    print("  未命中样例(25)：" + " | ".join(list(all_senses)[:25]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
