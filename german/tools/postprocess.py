"""把 llm-fill.tsv（严格轮）与 llm-fill2.tsv（放宽轮）合成 llm-fill-all.tsv，并做一处清洗：

专名被硬加冠词的（`n. der Nick`，英语提示就是同一个名字）→ 去掉冠词，因为德语人名/地名条目不带冠词。
判据：词性 n.、释义形如 `der/die/das <一个词>`、且这个词与英语提示的义项完全一致。

用法：python postprocess.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_fill as L  # noqa: E402

IN = [os.path.join(HERE, "llm-fill.tsv"), os.path.join(HERE, "llm-fill2.tsv")]
OUT = os.path.join(HERE, "llm-fill-all.tsv")


def hint_sense(en):
    m = re.match(r"^[a-z]+\.\s*(.+)$", (en or "").strip(), re.I)
    return (m.group(1) if m else (en or "")).strip().lower()


def main():
    items = L.load_worklist()
    en_of = {w: en for w, _, en in items}
    seen, kept, stripped, dup = set(), [], 0, 0
    for path in IN:
        if not os.path.isfile(path):
            continue
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if "\t" not in line or line.startswith("#"):
                    continue
                w, gloss = line.split("\t", 1)
                if w in seen:
                    dup += 1
                    continue
                seen.add(w)
                m = re.match(r"^n\.\s+(der|die|das)\s+([A-Za-zÄÖÜäöüß\-]+)$", gloss)
                if m and hint_sense(en_of.get(w)) == m.group(2).lower():
                    gloss = "n. " + m.group(2)
                    stripped += 1
                kept.append("%s\t%s" % (w, gloss))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as out:
        out.write("# llm-fill.tsv（严格轮）+ llm-fill2.tsv（放宽轮，含专名/数量短语）合并；"
                  "专名上多余的冠词已去掉\n")
        for line in kept:
            out.write(line + "\n")
    print("合并 %d 条（去重 %d；去掉专名多余冠词 %d）→ %s" % (len(kept), dup, stripped, OUT))


if __name__ == "__main__":
    main()
