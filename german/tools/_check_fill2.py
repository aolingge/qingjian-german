# -*- coding: utf-8 -*-
import io, sys, re, collections
sys.path.insert(0, r"E:\codemain\qingjian-de\de-glossary")
import llm_fill as L
items = L.load_worklist()
en_of = {w: (en or "") for w, f, en in items}
freq = {w: f for w, f, en in items}
rows = []
with io.open(r"E:\codemain\qingjian-de\de-glossary\llm-fill2.tsv", encoding="utf-8") as f:
    for ln in f:
        if "\t" in ln and not ln.startswith("#"):
            rows.append(ln.rstrip("\n"))
echo = 0
for ln in rows:
    w, g = ln.split("\t", 1)
    en = en_of.get(w, "")
    sense = re.sub(r"^[a-z]+\.\s*", "", g).strip().lower()
    hint = re.match(r"^[a-z]+\.\s*(.+)$", en.strip(), re.I)
    hint = (hint.group(1) if hint else en).strip().lower()
    if hint and sense == hint:
        echo += 1
print("本轮 %d 行，其中「与英语提示逐字相同」%d 行（%d%%）" % (len(rows), echo, 100*echo//max(len(rows),1)))
rows.sort(key=lambda ln: -freq.get(ln.split("\t")[0], 0))
print("\n=== 补回的词里词频最高的 45 个 ===")
for ln in rows[:45]:
    w, g = ln.split("\t", 1)
    print("  %-8s freq=%-7d %s" % (w, freq.get(w,0), g))
# 可疑：n. der/die/das + 单个大写专名，且英语提示就是同一个词
print("\n=== 疑似「照抄英语/专名硬加冠词」抽样 20 个 ===")
n = 0
for ln in rows:
    w, g = ln.split("\t", 1)
    en = en_of.get(w, "")
    m = re.match(r"^n\.\s+(der|die|das)\s+([A-Za-zÄÖÜäöüß\-]+)$", g)
    if m and en and m.group(2).lower() in en.lower():
        print("  %-8s freq=%-7d %s   (英: %s)" % (w, freq.get(w,0), g, en[:28]))
        n += 1
        if n >= 20: break
