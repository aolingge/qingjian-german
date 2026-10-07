# -*- coding: utf-8 -*-
"""llm_tools.py —— 用 DeepSeek 把德语这套数据「补齐 + 质检」的四个阶段。

四个阶段互不阻塞、都基于**同一份底表**，各自写自己的产物文件（可续跑、可小样试跑）：

    gap      词库里还没有德语译文的词（当前 151 个碎片/专名）→ llm-gap.tsv
    articles 名词首义缺 der/die/das 的条目 → 让模型判性别     → llm-articles.tsv
    cefr     释义里的德语实词 → CEFR 等级 A1–C2              → llm-cefr.tsv
    audit    全词表质检，挑出取错义项/词性错/照抄英语/碎片的条目 → llm-audit.tsv
    verify   生僻词（词频 < N）复核：audit/sense 都跳过的那批 → llm-verify.tsv

产物最后由 apply_fixes.py 一次性合并进 glossary-de-merged.tsv；
levels-de.tsv 由 `levels` 子命令在合并后重建（键=释义整串，见 level_table.rs:73-84）。

小样试跑（先看质量再全量）：
    python llm_tools.py audit --limit 60 --workers 4
全量（后台跑，可随时中断续跑，产物文件里以 `# batch N` 记录已完成批次）：
    python llm_tools.py articles --workers 8
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
DICT = os.path.join(SRC, r"assets\lexicon\dict.tsv")
EN = os.path.join(SRC, r"assets\glossary\glossary-en.tsv")
GLOSS = os.path.join(HERE, "glossary-de-merged.tsv")
GENDER_CSV = os.path.join(HERE, "gender", "nouns.csv")
GOETHE = os.path.join(HERE, "levels", "20260716200932-goethe-german-5000.de.tsv")
LEVELS_OUT = os.path.join(HERE, "levels", "levels-de.tsv")
ENV = os.path.join(os.environ["APPDATA"], r"Qingjian\.env")
MODEL = "deepseek-v4-flash"
URL = "https://api.deepseek.com/chat/completions"

POS_PREFIX = re.compile(r"^(n|noun|v|verb|adj|adv|int|interj|pron|num|prep|conj|part|phr|phrase|mw|m)\.\s+", re.I)
ANY_PREFIX = re.compile(r"^([A-Za-zÄÖÜäöüß]{1,10})\.\s+")
ARTICLES = ("der ", "die ", "das ")
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
STOP = set("""der die das den dem des ein eine einen einem einer eines
und oder aber doch denn weil wenn ob dass als wie so zu zur zum im in am an auf aus bei mit nach von vor
für über unter neben zwischen durch gegen ohne um ist sind war waren sein hat haben hatte wird werden
sich sich nicht kein keine keinen keinem keiner mehr sehr auch nur schon noch etwa etwas man es
ich du er sie wir ihr mich dich ihn uns euch mein dein sein ihr unser euer dieser diese dieses
jemand niemand alle alles viele wenige manche jeder jede jedes beide
pl abk ugs fig etw jdn jdm jds bzw ca usw z b
lat dt jap chin engl englisch od the and new of in for university originaltitel ii iii iv vs etc
im am vom zur zum ins ans aufs fürs durchs ums beim eigenname eigennamen samadhi""".split())
# 混在释义里的英语/拼音/缩写碎片：不参与定级（`(Originaltitel: One Hundred and One Dalmatians)` 这类）
EN_STOP = set("""the and new of in for university originaltitel lat dt jap chin engl englisch od
ii iii iv vs etc engl amer originaltitel provinz stadt kreis""".split()) - {"provinz", "stadt", "kreis"}


# --------------------------------------------------------------------------- 基础

def load_key() -> str:
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("QINGJIAN_API_KEY="):
                return line.strip().split("=", 1)[1].strip()
    raise SystemExit("在 %s 里找不到 QINGJIAN_API_KEY" % ENV)


def call(key, messages, max_tokens, timeout=240, retries=3):
    body = json.dumps({
        "model": MODEL, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens,
        # 该模型默认开思维链：不关掉会把 token 全烧在 reasoning_content 上、content 返回空
        "reasoning_effort": "none",
    }).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(URL, data=body, headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                raise RuntimeError("空 content（finish_reason=%s）" % data["choices"][0].get("finish_reason"))
            return content
        except Exception as exc:                      # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last)[:120])


def read_gloss(path=GLOSS):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            w, _, g = line.partition("\t")
            if g:
                rows.append((w, g))
    return rows


def final_or_merged():
    """合并后的成品表优先（apply_fixes.py 的产物），没有就用合并表。"""
    p = os.path.join(HERE, "glossary-de-final.tsv")
    return p if os.path.isfile(p) else GLOSS


def read_dict():
    """输入法词库：[(词, 词频)]。只有这里的词才打得出来、才会出现在候选窗口里。"""
    out = []
    with open(DICT, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            w = p[0].strip()
            if not w:
                continue
            try:
                out.append((w, int(p[2])))
            except (IndexError, ValueError):
                out.append((w, 0))
    return out


def write_lines(path, lines, header=None):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if header:
            f.write(header if header.endswith("\n") else header + "\n")
        for line in lines:
            f.write(line + "\n")


def run_batches(key, batches, build, parse, out_path, workers, max_tokens, note, header=None, marker=None):
    """后台跑批：`# <marker>` 记录已完成批次，中断后重跑会自动跳过。

    marker 缺省是批序号（`# batch N`）；传入 marker(batch) 可以改成按内容记账
    （cefrword 用它防「补跑时批次序号错位导致整批被跳过」）。
    """
    keys = [("batch %d" % i) if marker is None else marker(b) for i, b in enumerate(batches)]
    done = set()
    if os.path.isfile(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("# "):
                    done.add(line[2:].strip())
    todo = [(i, b) for i, b in enumerate(batches) if keys[i] not in done]
    print("[%s] 共 %d 批，已完成 %d，待跑 %d（%d 并发）" % (note, len(batches), len(done), len(todo), workers), flush=True)
    fresh = not os.path.isfile(out_path) or os.path.getsize(out_path) == 0
    out = open(out_path, "a", encoding="utf-8", newline="\n")
    if fresh and header:
        out.write(header + "\n")
    lock = threading.Lock()
    stats = collections.Counter()
    t0 = time.time()

    def work(item):
        i, batch = item
        try:
            return i, call(key, build(batch), max_tokens), None
        except Exception as exc:                        # noqa: BLE001
            return i, None, str(exc)[:100]

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (i, content, err) in enumerate(pool.map(work, todo), 1):
            with lock:
                if err:
                    stats["失败批"] += 1
                    if stats["失败批"] <= 3:
                        print("  批 %d 失败: %s" % (i, err), flush=True)
                else:
                    lines = parse(i, content)
                    out.write("# %s\n" % keys[i])
                    for line in lines:
                        out.write(line + "\n")
                    stats["成功批"] += 1
                    stats["输出行"] += len(lines)
                if n % 100 == 0 or n == len(todo):
                    speed = n / max(time.time() - t0, 1e-6)
                    print("  进度 %d/%d 批，%.1f 批/秒，输出 %d 行%s" % (
                        n, len(todo), speed, stats["输出行"],
                        "，失败 %d" % stats["失败批"] if stats["失败批"] else ""), flush=True)
                out.flush()
    out.close()
    print("[%s] 结束：成功 %d 批、失败 %d 批、输出 %d 行 → %s" % (
        note, stats["成功批"], stats["失败批"], stats["输出行"], out_path), flush=True)


def batched(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]


def parse_pairs(content, allow=("none",), key_index=None):
    """从模型回包里抽 `词<TAB>值` 行（容忍序号、代码块、中文冒号）。"""
    out = []
    for raw in content.splitlines():
        line = raw.strip().lstrip("-•*> \t`").strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        line = re.sub(r"^\d+[.、)]\s*", "", line)
        if "\t" in line:
            w, v = line.split("\t", 1)
        elif "：" in line:
            w, v = line.split("：", 1)
        elif ":" in line:
            w, v = line.split(":", 1)
        else:
            continue
        w, v = w.strip(), v.strip()
        if not w or not v:
            continue
        if allow and allow != ("*",) and v.lower() not in {a.lower() for a in allow}:
            continue
        out.append((w, v))
    return out


# --------------------------------------------------------------------------- gap

GAP_SYSTEM = (
    "你是汉德词典编者。给中文词写德语译文，每条一行，格式严格为「中文词<TAB>词性. 释义」。\n"
    "词性只用这 12 个：n. v. adj. adv. pron. prep. conj. num. m. part. int. phr.\n"
    "名词必须带定冠词（der/die/das）；专有名词（青岛/Qingdao）与生僻字请给出最接近的德语说法，"
    "确实没有对应词的写「中文词<TAB>n. Eigenname」这类最简说明。\n"
    "专名、音译、生僻汉字都照收，不要留空、不要输出解释、不要序号。\n"
    "括号里的英语只是提示，输出必须全部是德语。输出行数必须与输入行数相同、顺序一致。"
)


def cmd_gap(args):
    have = {w for w, _ in read_gloss()}
    en_map = {}
    with open(EN, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0] not in en_map and not line.startswith("#"):
                en_map[p[0]] = p[1]
    items = []
    with open(DICT, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            w = p[0].strip()
            if not w or w in have:
                continue
            try:
                freq = int(p[2])
            except (IndexError, ValueError):
                freq = 0
            items.append((w, freq, en_map.get(w, "")))
    items.sort(key=lambda t: (-t[1], t[0]))
    if args.limit:
        items = items[:args.limit]
    print("缺口 %d 词；前 20：%s" % (len(items), " ".join(w for w, _, _ in items[:20])))
    batches = batched(items, args.batch)

    def build(batch):
        body = "\n".join("%s\t%s" % (w, en) if en else w for w, _, en in batch)
        return [{"role": "system", "content": GAP_SYSTEM},
                {"role": "user", "content": "请为下面 %d 个中文词写德语译文：\n%s" % (len(batch), body)}]

    def parse(_i, content):
        rows = []
        for raw in content.splitlines():
            line = raw.strip().lstrip("-•*> `").strip()
            if not line or line.startswith("#") or line.startswith("```") or "\t" not in line:
                continue
            line = re.sub(r"^\d+[.、)]\s*", "", line)
            w, g = (s.strip() for s in line.split("\t", 1))
            if w and g:
                rows.append("%s\t%s" % (w, g))
        return rows

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "gap",
                header="# llm_tools.py gap：词库里没有德语译文的词（%s）" % MODEL)


# --------------------------------------------------------------------------- articles

ART_SYSTEM = (
    "你是德语的语法与词汇专家。下面每条是「中文词 + 德语释义」，德语是名词但没写定冠词。\n"
    "请判定该名词的定冠词，每条一行，格式严格为「中文词<TAB>der/die/das/none」：\n"
    "  · 阳/中/阴性名词分别写 der / das / die；\n"
    "  · 复合名词按**最后一个**成分的性别（die Straßenbahn, der Zug → der Straßenzug）；\n"
    "  · 国名地名、品牌、机构等专有名词、缩写、化学式、日期、量词、复数只用的词写 none；\n"
    "  · 已经是复数形式的词写 die（die Eltern, die Daten）。\n"
    "只输出这些行，不要解释、不要序号，行数与输入相同、顺序一致。"
)


def cmd_articles(args):
    rows = read_gloss()
    todo = []
    for w, g in rows:
        m = ANY_PREFIX.match(g)
        if not m or m.group(1).lower() not in ("n",):
            continue
        if not re.match(r"^n\.\s", g):        # 只处理名词首义
            continue
        sense = re.split(r"[;；]", g[3:])[0].strip()
        low = sense.lower()
        if low.startswith(ARTICLES) or re.match(r"^(der|die|das)$", low):
            continue
        first = sense.split(",")[0].split("(")[0].strip()
        if not first or re.match(r"^\d", first) or not first[0].isupper():
            continue                          # 数字/日期/小写开头（形容词化用法）交给 audit 处理
        todo.append((w, g, first))
    if args.limit:
        todo = todo[:args.limit]
    print("待判冠词 %d 条；样例：%s" % (len(todo), " | ".join("%s→%s" % (w, f) for w, _, f in todo[:8])))
    batches = batched(todo, args.batch)

    def build(batch):
        body = "\n".join("%s\t%s" % (w, f) for w, _, f in batch)
        return [{"role": "system", "content": ART_SYSTEM},
                {"role": "user", "content": "请判定下列 %d 条名词的定冠词：\n%s" % (len(batch), body)}]

    def parse(_i, content):
        return ["%s\t%s" % (w, v.lower()) for w, v in parse_pairs(content, allow=("der", "die", "das", "none"))]

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "articles",
                header="# llm_tools.py articles：名词首义缺冠词 → der/die/das/none（%s）" % MODEL)


# --------------------------------------------------------------------------- cefr

CEFR_SYSTEM = (
    "你是歌德学院德语考试（Goethe-Zertifikat）的词汇分级专家。给下面的德语词标注 CEFR 等级。\n"
    "每条一行，格式严格为「德语词<TAB>等级」，等级只能是 A1 A2 B1 B2 C1 C2 之一：\n"
    "  A1/A2 = 日常最高频基础词（Haus, gehen, gut, Tag）；B1/B2 = 常见但有门槛（Umwelt, beantragen）；\n"
    "  C1/C2 = 学术、专业、低频、生僻词（Röntgenfluoreszenz, Gemäldegalerie, veranschlagen）。\n"
    "若是变位/变格形式，按它的原形难度定级。只输出这些行，不要解释、不要序号，行数与输入相同。"
)


def cmd_cefr(args):
    # 先收集所有释义里的德语实词（去掉词性前缀、括号、数字、停用词）
    words = collections.Counter()
    for _w, g in read_gloss():
        text = POS_PREFIX.sub("", g) if POS_PREFIX.match(g) else g
        for tok in content_words(text):
            words[tok] += 1
    known = set()
    if os.path.isfile(GOETHE):
        with open(GOETHE, encoding="utf-8") as f:
            header = f.readline().rstrip("\n").split("\t")
            iw, ia = header.index("Word"), header.index("Annotation")
            for line in f:
                cells = line.rstrip("\n").split("\t")
                if len(cells) <= max(iw, ia):
                    continue
                for form in re.split(r"[,\s]+", cells[iw] + " " + cells[ia].split(",")[0]):
                    form = form.strip(" -–—").lower()
                    if form:
                        known.add(form)
    todo = sorted((w for w in words if w not in known), key=lambda w: -words[w])
    if args.limit:
        todo = todo[:args.limit]
    print("释义里的实词 %d 个；Goethe 已覆盖 %d 个；待定级 %d 个；前 15：%s" % (
        len(words), len([w for w in words if w in known]), len(todo), " ".join(todo[:15])))
    batches = batched(todo, args.batch)

    def build(batch):
        return [{"role": "system", "content": CEFR_SYSTEM},
                {"role": "user", "content": "\n".join(batch)}]

    def parse(_i, content):
        return ["%s\t%s" % (w.lower(), v.upper().replace("B2+", "B2"))
                for w, v in parse_pairs(content, allow=("A1", "A2", "B1", "B2", "B2+", "C1", "C2"))]

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "cefr",
                header="# llm_tools.py cefr：德语实词 → CEFR 等级（%s）" % MODEL)


# --------------------------------------------------------------------------- audit

AUDIT_SYSTEM = (
    "你是汉德词典的审校。输入若干条「中文词 + 德语释义」，格式「中文词<TAB>词性. 释义」。\n"
    "只处理一种错：**德语释义跟这个中文词的意思明显不符** —— 取错义项、张冠李戴、把英语提示照抄成德语、整条是乱码残片。\n"
    "下面这些**一律不算错、一个字都不要输出**：近义词或同义表达、语序与风格不同、另一种也说得通的译法、带说明性括号、"
    "缺 der/die/das、词性标注不同、专名的拉丁字母转写（人名地名产品名）。\n"
    "输出格式「中文词<TAB>词性. 正确释义」，词性只用这 12 个：n. v. adj. adv. pron. prep. conj. num. m. part. int. phr.。\n"
    "**没问题的条目不要输出**；也不要复述正确条目（复述等于没改，纯属浪费）；不要写 OK 或 DROP，不要序号、不要解释。"
)


def cmd_audit(args):
    rows = read_gloss()
    llm_seen = set()
    for f in ("llm-fill.tsv", "llm-fill2.tsv", "llm-fill3.tsv", "llm-fill4.tsv", "llm-fill-phrase.tsv"):
        p = os.path.join(HERE, f)
        if os.path.isfile(p):
            for line in open(p, encoding="utf-8"):
                if "\t" in line and not line.startswith("#"):
                    llm_seen.add(line.split("\t")[0])
    if args.only == "llm":
        rows = [(w, g) for w, g in rows if w in llm_seen]
    elif args.only == "handedict":
        rows = [(w, g) for w, g in rows if w not in llm_seen]
    elif args.only == "dict":
        # 只审「输入法真的打得出来」的词（在词库里）——只有这些才会出现在候选窗口里
        freq = dict(read_dict())
        rows = [(w, g) for w, g in rows if w in freq]
    elif args.only == "dict-nonllm":
        freq = dict(read_dict())
        rows = [(w, g) for w, g in rows if w in freq and w not in llm_seen]
    if args.sample:
        import random
        random.seed(args.seed)
        rows = random.sample(rows, args.sample)
    if args.limit:
        rows = rows[:args.limit]
    print("送审 %d 条；样例：%s" % (len(rows), " | ".join("%s→%s" % r for r in rows[:3])))
    batches = batched(rows, args.batch)

    def build(batch):
        body = "\n".join("%s\t%s" % (w, g) for w, g in batch)
        return [{"role": "system", "content": AUDIT_SYSTEM},
                {"role": "user", "content": "以下是 %d 条词表条目：\n%s" % (len(batch), body)}]

    def parse(_i, content):
        out = []
        for raw in content.splitlines():
            line = raw.strip().lstrip("-•*> `").strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            line = re.sub(r"^\d+[.、)]\s*", "", line)
            if "\t" not in line:
                continue
            w, g = (s.strip() for s in line.split("\t", 1))
            if not w or not g:
                continue
            if g.upper() == "DROP":
                out.append("%s\tDROP" % w)
            elif ANY_PREFIX.match(g) or re.match(r"^\d", g):
                out.append("%s\t%s" % (w, g))
        return out

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "audit",
                header="# llm_tools.py audit：只列有问题的条目（%s）" % MODEL)


# --------------------------------------------------------------------------- sense

SENSE_SYSTEM = (
    "你是汉德词典编者。对每条中文词，判断给出的**当前德语释义**是否覆盖了该词最常用的意思。\n"
    "参考英语义项只是提示（它自己的顺序也不代表中文里的常用程度），不要照抄英语。\n"
    "只有当当前德语明显不是常用义时才输出一行，格式严格为「中文词<TAB>词性. 建议的德语常用义」，例如：\n"
    "便宜\tadj. billig; preiswert; günstig\n"
    "建议写 1–3 条德语义，用「; 」分隔；词性前缀只能用这 12 个：n. v. adj. adv. pron. prep. conj. num. m. part. int. phr.；\n"
    "名词必须带定冠词（der/die/das）。当前德语已经覆盖常用义的行**不要输出**。\n"
    "不要解释、不要序号、不要 Markdown；除词性前缀外输出必须全是德语。"
)


def read_en():
    """英语表：一个中文词可能有多条義项（同一行里用 TAB 分隔）。"""
    out = {}
    with open(EN, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            w, rest = line.rstrip("\n").split("\t", 1)
            senses = [s.strip() for s in rest.split("\t") if s.strip()]
            if w and senses:
                out.setdefault(w, senses)
    return out


def cmd_sense(args):
    """常用义修正：拿英语义项当第二意见，找出「德语给的是生僻义」的词。

    只输出**需要改**的词，落地时把建议的常用义**插到最前面**、旧义项保留在后面
    （所以最坏情况是多一个义项，不会丢信息）。
    """
    en = read_en()
    freq = dict(read_dict())
    rows = [(w, g, en[w]) for w, g in read_gloss(final_or_merged()) if w in en and freq.get(w, 0) >= args.min_freq]
    rows.sort(key=lambda t: -freq[t[0]])
    if args.limit:
        rows = rows[:args.limit]
    print("送审 %d 条（词频 ≥ %d，且英语表里有）：%s" % (
        len(rows), args.min_freq, " | ".join("%s→%s" % (w, g) for w, g, _ in rows[:3])))
    batches = batched(rows, args.batch)

    def build(batch):
        body = "\n".join("%s\t%s\t%s" % (w, g, " / ".join(s)) for w, g, s in batch)
        return [{"role": "system", "content": SENSE_SYSTEM},
                {"role": "user", "content": "以下是 %d 条（中文词 / 当前德语 / 参考英语）：\n%s" % (len(batch), body)}]

    def parse(_i, content):
        out = []
        for raw in content.splitlines():
            line = raw.strip().lstrip("-•*> `").strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            line = re.sub(r"^\d+[.、)]\s*", "", line)
            if "\t" not in line:
                continue
            w, g = (s.strip() for s in line.split("\t", 1))
            if w and POS_PREFIX.match(g):        # 必须带合法词性前缀，否则当模型胡说丢掉
                out.append("%s\t%s" % (w, g))
        return out

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "sense",
                header="# llm_tools.py sense：常用义明显不对的词（%s，词频 ≥ %d）" % (MODEL, args.min_freq))


# --------------------------------------------------------------------------- verify

VERIFY_SYSTEM = (
    "你是汉德词典的终审，复核**生僻词**（输入法词频很低、之前没人看过的条目）的现有德语释义。\n"
    "只处理一种错：德语释义跟这个中文词**明显不符** —— 取错义项、张冠李戴（把别的词的意思搬过来）、"
    "整条是英语或拼音、乱码残片。\n"
    "下面这些一律不算错、一个字都不要输出：近义词或同义表达、语序与风格不同、另一种也说得通的译法、"
    "带说明性括号、缺 der/die/das、词性标注不同、专名的拉丁字母转写（人名地名产品名机构名）。\n"
    "生僻词允许沉默：**只要你不能确定现有释义是错的，就不要输出这一行**。宁漏勿错，凭印象猜出来的改动会让词表变坏。\n"
    "输出格式「中文词<TAB>词性. 修正后的释义」，词性只用这 12 个：n. v. adj. adv. pron. prep. conj. num. m. part. int. phr.。\n"
    "没问题的条目不要输出、不要写 OK、不要序号、不要解释；除词性前缀外必须全是德语。"
)

VERIFY_SKIP_BODY = {"eigenname", "eigennamen"}


def cmd_verify(args):
    """生僻词复核：把词频 < --max-freq 的条目交给模型判「现有德语释义是不是错的」，只输出错的。

    这批词是词表里最后一块没被模型看过的数据：audit 全量跑过一次但只挑明显错，
    sense 又按 SENSE_MIN_FREQ（100）跳过了生僻词，所以专门再复核一遍。
    """
    freq = dict(read_dict())
    rows = []
    for w, g in read_gloss(final_or_merged()):
        f = freq.get(w)
        if f is None or f >= args.max_freq or f < args.min_freq:
            continue
        if not POS_PREFIX.match(g):            # 没有词性前缀的条目判不了（HanDeDict 原写法）
            continue
        body = POS_PREFIX.sub("", g, count=1).strip()
        if not has_letters(body):              # 纯数字/型号/符号条目（levels 里按 A1 兜底）
            continue
        if body.lower() in VERIFY_SKIP_BODY:   # 「n. Eigenname」这类标签式释义，人工已处理
            continue
        rows.append((w, g))
    rows.sort(key=lambda t: -freq.get(t[0], 0))
    if args.limit:
        rows = rows[:args.limit]
    print("送审 %d 条（词频 %d–%d）；样例：%s" % (
        len(rows), args.min_freq, args.max_freq, " | ".join("%s→%s" % r for r in rows[:3])))
    batches = batched(rows, args.batch)

    def build(batch):
        body = "\n".join("%s\t%s" % (w, g) for w, g in batch)
        return [{"role": "system", "content": VERIFY_SYSTEM},
                {"role": "user", "content": "以下是 %d 条词表条目：\n%s" % (len(batch), body)}]

    def parse(_i, content):
        out = []
        for raw in content.splitlines():
            line = raw.strip().lstrip("-•*> `").strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            line = re.sub(r"^\d+[.、)]\s*", "", line)
            if "\t" not in line:
                continue
            w, g = (s.strip() for s in line.split("\t", 1))
            if w and POS_PREFIX.match(g):       # 必须带合法词性前缀，否则当模型胡说丢掉
                out.append("%s\t%s" % (w, g))
        return out

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "verify",
                header="# llm_tools.py verify：生僻词（词频 %d–%d）里判为错的条目（%s）" % (
                    args.min_freq, args.max_freq, MODEL),
                marker=lambda b: "v " + (b[0][0] if b else ""))


# --------------------------------------------------------------------------- levels

def load_goethe():
    """德语词形（含带冠词写法）→ 等级；B2+ 归一成 B2。"""
    table = {}
    if not os.path.isfile(GOETHE):
        return table
    with open(GOETHE, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        iw, ia, il = header.index("Word"), header.index("Annotation"), header.index("Level")
        for line in f:
            cells = line.rstrip("\n").split("\t")
            if len(cells) <= max(iw, ia, il):
                continue
            level = cells[il].strip().replace("B2+", "B2")
            if level not in LEVEL_ORDER:
                continue
            forms = [p for p in re.split(r",", cells[iw])]
            for part in forms:
                part = part.strip().strip(" -–—")
                if part:
                    table.setdefault(part.lower(), level)
            anno = cells[ia].split(",")[0].strip()
            if anno:
                table.setdefault(anno.lower(), level)
                for art in ARTICLES:
                    if anno.lower().startswith(art):
                        table.setdefault(anno[len(art):].strip().lower(), level)
                        break
    return table


# 兜底词表：月份/星期/季节/度量/常见技术词。Goethe 表和 LLM 定级里都没有这些词，
# 但日期类条目（11. Oktober、5 Minuten、100-Meter-Lauf）在词表里占了不少，按 A1/A2 兜底。
FALLBACK_LEVELS = {}
for _w in ("januar februar märz april mai juni juli august september oktober november dezember").split():
    FALLBACK_LEVELS[_w] = "A1"
for _w in ("montag dienstag mittwoch donnerstag freitag samstag sonntag").split():
    FALLBACK_LEVELS[_w] = "A1"
for _w in ("frühling sommer herbst winter jahr jahre tag tage monat woche uhr minute stunde "
           "meter kilometer zentimeter millimeter gramm kilogramm kilometer prozent").split():
    FALLBACK_LEVELS[_w] = "A1"
for _w in ("jahrhundert jahrtausend jahrzehnt datum kalender kilobyte megabyte gigabyte "
           "lauf sprint staffel hürdenlauf halbjahr quartal jahreszeit").split():
    FALLBACK_LEVELS[_w] = "A2"


def content_words(text, numeric=False):
    """释义里的德语实词。先去掉括号（英语/拉丁文注释多在里面），再过滤停用词与非德语碎片。

    numeric=True 时额外把数字/数量前缀剥掉（100-Meter-Hürdenlauf、16-Bit-Architektur、8-Ball），
    这样这些条目还有机会被复合词/兜底词表定级——只在真能定级时才采信，见 cmd_levels。
    """
    text = re.sub(r"\([^()]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    out = []
    for tok in re.split(r"[\s,;./()\[\]\"'|]+", text):
        tok = tok.strip(" -–—!?…:")
        if numeric:
            tok = re.sub(r"^[0-9]+([.,][0-9]+)*[-–]?", "", tok)
        if len(tok) < 2 or tok[0].isdigit():
            continue
        low = tok.lower()
        if low in STOP or low in EN_STOP or not re.search(r"[a-zäöüß]", low):
            continue
        if not re.search(r"[aeiouäöü]", low):
            continue
        out.append(low)
    return out


def has_letters(text):
    """释义里是否有真正的字母词（用来区分「型号/数字/符号条目」与「有德语词汇的条目」）。"""
    text = re.sub(r"\([^()]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return bool(re.search(u"[A-Za-z\u00c0-\u024f\u00df]{2,}", text))


def resolve_level(words, word_level):
    """在实词里找等级：① 第一个有等级的词（冠词后的中心词）② 复合词退化 ③ 兜底词表。

    返回 (等级, 来源)；找不到返回 (None, "")。
    """
    for t in words:
        if t in word_level:
            return word_level[t], "中心词"
    for t in words:
        low_t = t.lower()
        hit = None
        # 复合词退化：连字符各段（从后往前）→ 再按词尾逐字缩短找最长命中。
        # 只认真实词表里的形态，命中不了就按 B2 兜底，不猜。
        for part in reversed(re.split(r"[-‐–]", low_t)):
            if len(part) >= 4 and part in word_level:
                hit = word_level[part]
                break
        if hit is None and len(low_t) >= 8:
            for k in range(6, len(low_t) - 3):
                if low_t[k:] in word_level:
                    hit = word_level[low_t[k:]]
                    break
        if hit:
            return hit, "复合词退化"
    for t in words:
        low_t = t.lower()
        hit = FALLBACK_LEVELS.get(low_t)
        if hit is None:
            for part in re.split(r"[-‐–]", low_t):
                if part in FALLBACK_LEVELS:
                    hit = FALLBACK_LEVELS[part]
                    break
        if hit:
            return hit, "兜底词表"
    return None, ""


def cmd_levels(args):
    """用 Goethe 表 + llm-cefr.tsv 给**每条释义**定级（键 = 释义整串小写，运行时精确匹配）。"""
    word_level = dict(load_goethe())
    n_goethe = len(word_level)
    n_llm = 0
    for path, tag in ((os.path.join(HERE, "llm-cefr.tsv"), "llm"),
                      (os.path.join(HERE, "llm-cefrword.tsv"), "word")):
        if not os.path.isfile(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            w, lv = (s.strip() for s in line.split("\t", 1))
            lv = lv.upper().replace("B2+", "B2")
            if lv in LEVEL_ORDER and w:
                if tag == "llm":
                    n_llm += 1
                if w.lower() not in word_level:
                    word_level[w.lower()] = lv
    rows = read_gloss(final_or_merged())
    # 条目级定级（cefrgloss）：给「释义里没有任何可定级实词」的型号/数字/符号条目兜底
    gloss_level = {}
    gloss_path = os.path.join(HERE, "llm-cefrgloss.tsv")
    if os.path.isfile(gloss_path):
        for line in open(gloss_path, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            t, lv = (s.strip() for s in line.split("\t", 1))
            lv = lv.upper().replace("B2+", "B2")
            if t and lv in LEVEL_ORDER:
                gloss_level[t.lower()] = lv
    per = collections.Counter()
    kinds = collections.Counter()
    out = {}
    miss = []
    miss_heads = collections.Counter()
    miss_glosses = collections.Counter()
    for w, g in rows:
        text = (POS_PREFIX.sub("", g) if POS_PREFIX.match(g) else g).strip()
        if not text:
            continue
        low = text.lower()
        words = content_words(text)
        # 口径：取释义里**第一个有等级的词**（名词的定冠词后面那个词就是它的中心词），
        # 这样 `der Kreis Huidong (Provinz Sichuan)` 按 Kreis 定级，不会被括号里的英语/拼音带偏。
        # 退化顺序见 resolve_level()：中心词 → 复合词退化 → 兜底词表。
        level, kind = resolve_level(words, word_level)
        if level is None and any(c.isdigit() for c in text):
            # 再试一次「剥掉数字前缀」的实词（100-Meter-Hürdenlauf、16-Bit-Architektur）。
            # 只有在真能定级时才采信，免得把 A1 兜底变成 B2 兜底。
            alt = content_words(text, numeric=True)
            if alt:
                lv2, kind2 = resolve_level(alt, word_level)
                if lv2 is not None:
                    level, kind = lv2, kind2
                    words = words or alt
        # 条目级定级只在「释义里确实有德语词」时才采信：纯数字/型号/符号条目（1961、1 (Num)）
        # 没有可学的德语词汇，直接按 A1，不采信模型给整串编号打的分。
        if level is None and gloss_level and has_letters(text):
            lv3 = gloss_level.get(low)
            if lv3:
                level, kind = lv3, "条目定级"
        if level is not None:
            kinds[kind] += 1
        else:
            level = "A1" if not words else "B2"   # 没有实词（纯数字/符号）按 A1；有实词但没标注按 B2
            miss.append((w, text))
            miss_glosses[text] += 1
            if words:
                miss_heads[words[0]] += 1
        prev = out.get(low)
        if prev is None or LEVEL_ORDER.index(level) < LEVEL_ORDER.index(prev):
            if prev is not None:
                per[prev] -= 1
            out[low] = level
            per[level] += 1
    lines = [
        "# 德语词汇等级（CEFR）。两级来源：① 歌德学院 5000 词表（A1–B2，权威，"
        "https://github.com/voothi/20260716201616-german-5000 MIT）；",
        "# ② 其余词由 DeepSeek %s 按 Goethe 分级口径标注（llm-cefr.tsv，估算值）。" % MODEL,
        "# 分级口径：取释义里**第一个有等级的实词**（即冠词后的中心词）。",
        "# 由 E:\\codemain\\qingjian-de\\de-glossary\\llm_tools.py levels 生成；键是**释义整串小写**"
        "（青简按 sense.text 精确查表，见 level_table.rs:73-84）。",
        "# levels\t" + "\t".join(LEVEL_ORDER),
    ]
    for text in sorted(out, key=lambda t: (LEVEL_ORDER.index(out[t]), t)):
        lines.append("%s\t%s" % (text, out[text]))
    write_lines(LEVELS_OUT, lines)
    # 兜底中心词清单：交给 `cefrword` 子命令补标注，下一轮 levels 就能吃上
    miss_path = os.path.join(HERE, "levels", "unknown-heads.tsv")
    write_lines(miss_path, ["%s\t%d" % (k, v) for k, v in miss_heads.most_common()],
                header="# llm_tools.py levels 定不了级的中心词（词<TAB>出现次数）"
                       "——用 `python llm_tools.py cefrword` 补标注后重跑 levels")
    gloss_miss_path = os.path.join(HERE, "levels", "unknown-glosses.tsv")
    write_lines(gloss_miss_path, ["%s\t%d" % (k, v) for k, v in miss_glosses.most_common()],
                header="# llm_tools.py levels 连中心词都没有的条目（释义<TAB>出现次数）"
                       "——用 `python llm_tools.py cefrgloss` 按条目补定级后重跑 levels")
    total = len(out) + len(miss)
    print("Goethe 词形 %d，LLM 词形 %d，合计 %d" % (n_goethe, n_llm, len(word_level)))
    print("释义定级 %d / %d（%.1f%%）；未定级 %d；待补定级中心词 %d 个（→ %s）；待补定级条目 %d 条（→ %s）"
          % (len(out), total, 100 * len(out) / max(total, 1), len(miss), len(miss_heads), miss_path,
             len(miss_glosses), gloss_miss_path))
    print("每级：" + "，".join("%s %d" % (l, per[l]) for l in LEVEL_ORDER if per[l]))
    print("定级来源：" + "，".join("%s %d" % kv for kv in kinds.most_common()))
    print("未定级样例：" + " | ".join("%s→%s" % m for m in miss[:10]))
    print("写出 %s（%d B）" % (LEVELS_OUT, os.path.getsize(LEVELS_OUT)))


# --------------------------------------------------------------------------- cefrword

def cmd_cefrword(args):
    """给 levels 兜底的「中心词」补 CEFR 等级（Goethe 与 llm-cefr.tsv 都没有的词）。

    输入是 levels 子命令写出的 levels\\unknown-heads.tsv；产物 llm-cefrword.tsv 会被
    下一次 levels 读进去，从而把「有实词但没标注 → B2 兜底」的那部分降到最低。
    """
    src = os.path.join(HERE, "levels", "unknown-heads.tsv")
    if not os.path.isfile(src):
        raise SystemExit("先跑 `python llm_tools.py levels` 生成 %s" % src)
    done = set()
    if os.path.isfile(args.out):
        for line in open(args.out, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            done.add(line.split("\t", 1)[0].strip().lower())
    items = []
    for line in open(src, encoding="utf-8"):
        if line.startswith("#") or "\t" not in line:
            continue
        w = line.split("\t", 1)[0].strip().lower()
        if w and w not in done:
            items.append(w)
    if args.limit:
        items = items[:args.limit]
    print("待补定级中心词 %d 个（已有 %d）；前 15：%s" % (len(items), len(done), " ".join(items[:15])))
    batches = batched(items, args.batch)

    def build(batch):
        return [{"role": "system", "content": CEFR_SYSTEM},
                {"role": "user", "content": "\n".join(batch)}]

    def parse(_i, content):
        return ["%s\t%s" % (w.lower(), v.upper().replace("B2+", "B2"))
                for w, v in parse_pairs(content, allow=("A1", "A2", "B1", "B2", "B2+", "C1", "C2"))]

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "cefrword",
                header="# llm_tools.py cefrword：levels 兜底中心词的 CEFR 补标注（%s）" % MODEL,
                marker=lambda b: "words " + (b[0] if b else ""))


# --------------------------------------------------------------------------- cefrgloss

CEFRGLOSS_SYSTEM = (
    "你是歌德学院德语考试（Goethe-Zertifikat）的词汇分级专家。下面每行是「编号<TAB>一条德语释义」，"
    "这条释义对应一个中文词条；有些释义里只有数字、型号、单位或符号（1 (Num)、Typ 99、HK MP5）。\n"
    "请按这条释义的**难度**给 CEFR 等级，输出格式严格为「编号<TAB>等级」，等级只能是 A1 A2 B1 B2 C1 C2：\n"
    "  A1/A2 = 日常最高频基础（das Haus、1 (Num)）；B1/B2 = 常见但有门槛（der Keilriemen）；\n"
    "  C1/C2 = 学术、专业、低频、生僻（100-Meter-Hürdenlauf、Röntgenfluoreszenz、besondere Rechtsform）。\n"
    "型号/数字/符号条目按它指代的词判断难度，实在判断不了给 B2。只输出这些行，不要解释、不要序号以外的文字，"
    "行数与输入相同，编号原样照抄。"
)


def cmd_cefrgloss(args):
    """给「释义里没有任何可定级德语词」的条目补 CEFR 等级（按编号回填，模型不必照抄释义）。

    输入是 levels 子命令写出的 levels\\unknown-glosses.tsv；产物 llm-cefrgloss.tsv 会被
    下一次 levels 读进去，作为最后一级依据（在词级定级之后、盲兜底之前）。
    """
    src = os.path.join(HERE, "levels", "unknown-glosses.tsv")
    if not os.path.isfile(src):
        raise SystemExit("先跑 `python llm_tools.py levels` 生成 %s" % src)
    done = set()
    if os.path.isfile(args.out):
        for line in open(args.out, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            done.add(line.split("\t", 1)[0].strip().lower())
    items = []
    for line in open(src, encoding="utf-8"):
        if line.startswith("#") or "\t" not in line:
            continue
        t = line.split("\t", 1)[0].strip()
        if t and t.lower() not in done:
            items.append(t)
    if args.limit:
        items = items[:args.limit]
    print("待补定级条目 %d 条（已有 %d）；前 5：%s" % (len(items), len(done), " | ".join(items[:5])))
    batches = batched(items, args.batch)

    def build(batch):
        body = "\n".join("%d\t%s" % (j + 1, t) for j, t in enumerate(batch))
        return [{"role": "system", "content": CEFRGLOSS_SYSTEM},
                {"role": "user", "content": body}]

    def parse(_i, content):
        out, seen = [], set()
        for raw in content.splitlines():
            line = raw.strip().lstrip("-•*> \t`").strip()
            m = re.match(r"^(\d+)\s*[\t:：.、)）-]\s*([A-Ca-c][12])\b", line)
            if not m:
                continue
            j, lv = int(m.group(1)), m.group(2).upper()
            if 1 <= j <= len(batches[_i]) and j not in seen:
                seen.add(j)
                out.append("%s\t%s" % (batches[_i][j - 1].lower(), lv))
        return out

    run_batches(load_key(), batches, build, parse, args.out, args.workers, args.max_tokens, "cefrgloss",
                header="# llm_tools.py cefrgloss：无可定级实词的条目（型号/数字/符号释义）按条目补定级（%s）" % MODEL,
                marker=lambda b: "gloss " + (b[0][:40] if b else ""))


# --------------------------------------------------------------------------- report

def cmd_report(args):
    rows = read_gloss()
    pos = collections.Counter()
    illegal = []
    for w, g in rows:
        m = ANY_PREFIX.match(g)
        if not m:
            pos["(无前缀)"] += 1
            continue
        p = m.group(1).lower()
        if p in ("n", "v", "adj", "adv", "int", "pron", "num", "prep", "conj", "part", "phr", "m"):
            pos[p] += 1
        else:
            pos["非法:" + p] += 1
            illegal.append((w, g))
    print("词表 %d 条；词性：" % len(rows) + "，".join("%s %d" % kv for kv in pos.most_common()))
    for w, g in illegal[:10]:
        print("   非法前缀 %s → %s" % (w, g[:60]))
    lv = 0
    if os.path.isfile(LEVELS_OUT):
        lv = sum(1 for line in open(LEVELS_OUT, encoding="utf-8") if line.strip() and not line.startswith("#"))
    keys = {POS_PREFIX.sub("", g).strip().lower() if POS_PREFIX.match(g) else g.strip().lower() for _, g in rows}
    print("等级表键 %d；词表去重释义 %d；覆盖 %.1f%%" % (lv, len(keys), 100 * lv / max(len(keys), 1)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("gap", "articles", "cefr", "audit", "sense", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--out", default=os.path.join(HERE, "llm-%s.tsv" % name))
        p.add_argument("--batch", type=int, default={"gap": 20, "articles": 50, "cefr": 60, "audit": 30,
                                                     "sense": 30, "verify": 25}[name])
        p.add_argument("--workers", type=int, default=8)
        p.add_argument("--max-tokens", type=int, default={"gap": 2000, "articles": 1200, "cefr": 1500,
                                                          "audit": 2500, "sense": 2500,
                                                          "verify": 2500}[name])
        p.add_argument("--limit", type=int, default=0, help="只跑前 N 项（小样试跑）")
        if name == "audit":
            p.add_argument("--only", choices=["all", "llm", "handedict", "dict", "dict-nonllm"], default="all")
            p.add_argument("--sample", type=int, default=0, help="随机抽样 N 条（配合 --seed）")
            p.add_argument("--seed", type=int, default=20260927)
        if name == "sense":
            p.add_argument("--min-freq", type=int, default=100, help="只看词频 ≥ N 的词")
        if name == "verify":
            p.add_argument("--max-freq", type=int, default=100, help="只看词频 < N 的词（生僻词）")
            p.add_argument("--min-freq", type=int, default=0, help="只看词频 ≥ N 的词（默认不限）")
    p = sub.add_parser("levels")
    p = sub.add_parser("cefrword")
    p.add_argument("--out", default=os.path.join(HERE, "llm-cefrword.tsv"))
    p.add_argument("--batch", type=int, default=50)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-tokens", type=int, default=1500)
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 个词（小样试跑）")
    p = sub.add_parser("cefrgloss")
    p.add_argument("--out", default=os.path.join(HERE, "llm-cefrgloss.tsv"))
    p.add_argument("--batch", type=int, default=25)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-tokens", type=int, default=2000)
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 条（小样试跑）")
    p = sub.add_parser("report")
    args = ap.parse_args()
    {"gap": cmd_gap, "articles": cmd_articles, "cefr": cmd_cefr, "audit": cmd_audit,
     "sense": cmd_sense, "verify": cmd_verify, "levels": cmd_levels, "cefrword": cmd_cefrword,
     "cefrgloss": cmd_cefrgloss, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
