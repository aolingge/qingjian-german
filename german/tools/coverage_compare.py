"""对比：英文释义表对 levels-en.tsv 的命中率，用来判断德语 6.1% 是偏低还是同一量级。"""

import re
import sys
from pathlib import Path

POS_PREFIX = re.compile(r"^(?:n|v|adj|adv|int|pron|num|prep|conj|part|art|aux|onom|phrase|abbr)\.\s+")
TRIM = " \t!?.,;:…\"'()[]"


def load_levels(path: Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        w, _, _l = line.partition("\t")
        out.add(w.lower())
    return out


def main() -> int:
    levels_en, glossary_en, levels_de, glossary_de = (Path(a) for a in sys.argv[1:5])
    en = load_levels(levels_en)
    de = load_levels(levels_de)
    for name, lv, gl in (("en", en, glossary_en), ("de", de, glossary_de)):
        total = whole = first = anyword = 0
        for line in gl.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            word, _, gloss = line.partition("\t")
            if not gloss:
                continue
            total += 1
            text = POS_PREFIX.sub("", gloss).strip()
            low = text.lower()
            if low in lv:
                whole += 1
                continue
            seg = re.split(r"[,;(]", text, maxsplit=1)[0].strip().strip(TRIM).lower()
            if seg in lv:
                first += 1
                continue
            words = [w.strip(TRIM).lower() for w in re.split(r"[\s,;()/]+", text) if w.strip(TRIM)]
            if any(w in lv for w in words):
                anyword += 1
        print(
            f"{name}: 总 {total:,} 行；整串命中 {whole:,}；第一段命中 +{first:,}；"
            f"任意词命中 +{anyword:,}；合计 {(whole + first + anyword) / total:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
