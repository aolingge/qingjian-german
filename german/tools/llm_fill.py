# -*- coding: utf-8 -*-
"""用 DeepSeek 补齐德语释义表的缺口（输入法词库里没有德语译文的词）。

工作清单 = assets/lexicon/dict.tsv（青简自己的词库，92,825 条，第三列是词频）
           减去德语表里已有的词（默认 de-glossary/glossary-de-art.tsv）
           按词频从高到低排序 —— 越常用越先补。
英语释义（assets/glossary/glossary-en.tsv）作为提示喂给模型，明显提升准确率。

用法：
    python llm_fill.py --report                 # 只看缺口统计与前 30 个高频缺口词
    python llm_fill.py --limit 200 --out sample-200.tsv    # 跑 200 条小样
    python llm_fill.py --limit 0  --out llm-all.tsv --workers 8   # 全量（0 = 不限）
输出格式与随包德语表一致：`中文词<TAB>词性. 释义`，名词强制带 der/die/das。
"""
import argparse
import collections
import concurrent.futures as cf
import csv
import json
import os
import random
import re
import sys
import time
import urllib.request

SRC = r"C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
DICT = os.path.join(SRC, r"assets\lexicon\dict.tsv")
EN = os.path.join(SRC, r"assets\glossary\glossary-en.tsv")
DE = r"E:\codemain\qingjian-de\de-glossary\glossary-de-art.tsv"
ENV = os.path.join(os.environ["APPDATA"], r"Qingjian\.env")
MODEL = "deepseek-v4-flash"
URL = "https://api.deepseek.com/chat/completions"

SYSTEM = (
    "你是汉德词典编者，为中文输入法写候选旁的德语译文。规则：\n"
    "1. 每条输出一行，格式严格为「中文词<TAB>词性. 释义」，不要序号、不要解释、不要代码块。\n"
    "2. 词性缩写只用这 12 个：n. v. adj. adv. pron. prep. conj. num. m. part. int. phr.\n"
    "   （m. = 量词，part. = 助词/语气词（了/吗/呢/吧），phr. = 短语、句子片段。）\n"
    "3. 名词必须带定冠词（der/die/das），例如「学校\tn. die Schule」。\n"
    "4. 形容词/动词给原形；多个义项用「; 」分隔，最多 3 个，最多 40 个字符。\n"
    "5. 只写德语，不要英语、不要汉语。助词/语气词写短的德语说明，如「吗\tpart. Fragepartikel」。\n"
    "6. 输入行里跟在中文字后面的英语只是「选义提示」，输出必须全部是德语，绝对不要照抄英语单词。\n"
    "7. 查不到或不确定的词，输出该词 + TAB + 空（宁可留空也别编）。\n"
    "8. 输出行数必须与输入词数完全相同，顺序一致。"
)

ALLOWED_POS = ["n.", "v.", "adj.", "adv.", "int.", "num.", "pron.", "conj.", "prep.", "m.", "part.", "phr."]

POS_FIX = {
    "subst": "n.", "substantiv": "n.", "n": "n.", "noun": "n.",
    "v": "v.", "verb": "v.", "vi": "v.", "vt": "v.",
    "adj": "adj.", "adjective": "adj.", "adj./adv": "adj.",
    "adv": "adv.", "adverb": "adv.",
    "int": "int.", "interj": "int.", "interjection": "int.",
    "num": "num.", "nummerale": "num.", "numeral": "num.",
    "pron": "pron.", "pronomen": "pron.",
    "conj": "conj.", "konj": "conj.", "konjunktion": "conj.",
    "präp": "prep.", "praep": "prep.", "prep": "prep.", "präposition": "prep.",
    "phr": "phr.", "phrase": "phr.", "redewendung": "phr.", "expr": "phr.",
    "m": "m.", "meas": "m.", "measure": "m.", "zählwort": "m.", "zähl": "m.", "classifier": "m.",
    "part": "part.", "particle": "part.", "partikel": "part.", "modalpartikel": "part.",
}

# german-nouns（CC-BY-SA-4.0）只有词形没有输入法用法，这里用来给模型漏写冠词的名词兜底补 der/die/das
GENDER_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gender", "nouns.csv")
ARTICLES = {"m": "der", "f": "die", "n": "das"}
_GENDERS = None


def genders():
    global _GENDERS
    if _GENDERS is None:
        table = {}
        with open(GENDER_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lemma = (row.get("lemma") or "").strip()
                genus = (row.get("genus") or "").strip().lower()
                if not lemma or lemma.startswith("-") or genus not in ARTICLES:
                    continue
                table.setdefault(lemma, ARTICLES[genus])
        _GENDERS = table
    return _GENDERS


def with_articles(gloss):
    """`Schule; Lehrer` → `die Schule; der Lehrer`；一个词都查不到性别就返回 None。"""
    table = genders()
    hit = 0
    parts = []
    for part in re.split(r"\s*;\s*", gloss):
        fixed = []
        for seg in part.split(","):
            core = seg.strip().rstrip(".…").strip()
            art = table.get(core) if re.fullmatch(r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]*", core or "") else None
            if art:
                fixed.append("%s %s" % (art, seg.strip()))
                hit += 1
            else:
                fixed.append(seg.strip())
        parts.append(", ".join(fixed))
    return "; ".join(parts) if hit else None


def load_key():
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("QINGJIAN_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("在 %s 里找不到 QINGJIAN_API_KEY" % ENV)


def load_worklist():
    de_words = set()
    with open(DE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            de_words.add(line.split("\t")[0])
    en_map = {}
    with open(EN, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0] not in en_map:
                en_map[p[0]] = p[1]
    seen, items = set(), []
    with open(DICT, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            w = p[0]
            if not w or w in seen or w in de_words:
                continue
            seen.add(w)
            try:
                freq = int(p[2]) if len(p) > 2 else 0
            except ValueError:
                freq = 0
            items.append((w, freq, en_map.get(w, "")))
    items.sort(key=lambda t: (-t[1], t[0]))
    return items


def call(key, messages, max_tokens, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        # 这个模型默认开思维链：不关掉它会把 token 全烧在 reasoning_content 上、content 返回空
        # （青简自己的 [predict] 配置里也是 reasoning_effort = "none"）。
        "reasoning_effort": "none",
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def normalize(word, raw, relaxed=False, en=""):
    """把模型输出的一行规整成 `词\t词性. 释义`；返回 (行 或 None, 原因)。

    relaxed=True 时放宽两条：① 查不到性别的专名/无冠词名词（`n. Qingdao`）也收；
    ② 没写词性前缀时用英语提示的词性兜底。
    """
    line = raw.strip().lstrip("-•*> ").strip()
    if "\t" in line:
        head, gloss = line.split("\t", 1)
    else:
        m = re.match(r"^(\S+?)\s*[:：]\s*(.+)$", line)
        if not m:
            return None, "没有分隔符"
        head, gloss = m.group(1), m.group(2)
    if head.strip() != word:
        # 模型偶尔把词写错（繁简/加空格），以我们的词为准，但记一笔
        if head.strip().replace(" ", "") != word:
            return None, "词不匹配: %s" % head.strip()[:12]
    gloss = gloss.strip().strip("。.;；")
    if not gloss:
        return None, "空释义"
    m = re.match(r"^([A-Za-zÄÖÜäöüß./]{1,12}?)\.\s*(.+)$", gloss)
    if not m:
        if not relaxed:
            return None, "没有词性前缀: %s" % gloss[:20]
        em = re.match(r"^([a-z]{1,4})\.\s", en.strip(), re.I)   # 用英语提示的词性兜底
        if not em:
            return None, "没有词性前缀: %s" % gloss[:20]
        pos_raw, rest, m = em.group(1).lower(), gloss, True
        if POS_FIX.get(pos_raw.replace(" ", "")) is None:
            return None, "没有词性前缀: %s" % gloss[:20]
    else:
        pos_raw, rest = m.group(1).lower().strip(), m.group(2).strip()
    pos = POS_FIX.get(pos_raw.replace(" ", ""))
    if pos is None:
        return None, "词性不认识: %s" % pos_raw
    rest = rest.replace(" ,", ",").replace(" ;", ";").replace("  ", " ")
    rest = re.sub(r"\s*;\s*", "; ", rest).strip().strip(";")
    if pos == "n." and not re.match(r"^(der|die|das)\s", rest) and not re.match(r"^(ein|eine|einen|einem|einer|eines|zwei|drei|vier)\s", rest):
        fixed = with_articles(rest)   # 模型漏冠词时用 german-nouns 兜底
        if fixed is None:
            # 专名（Qingdao、Fujian）与「德语对应词是短语」的名词：只要首词大写就收，不硬加冠词
            if relaxed and re.match(r"^[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.\-]*(?:[ \-][A-ZÄÖÜ][A-Za-zÄÖÜäöüß.\-]*)*$", rest):
                fixed = rest
            else:
                return None, "名词没冠词: %s" % rest[:24]
        rest = fixed
    if len(rest) > 90:
        rest = rest[:90].rsplit(" ", 1)[0].strip(";, ") + "…"
    return "%s\t%s %s" % (word, pos, rest), None


def run(key, items, batch, workers, out_path, max_tokens, relaxed=False, skip_files=()):
    stats = collections.Counter()
    done = set()
    for skip in (out_path,) + tuple(skip_files):
        if not os.path.isfile(skip):
            continue
        with open(skip, encoding="utf-8") as f:
            for line in f:
                if "\t" in line and not line.startswith("#"):
                    done.add(line.split("\t")[0])
    if done:
        print("已有 %d 条结果，跳过它们（续跑）" % len(done))
    todo = [it for it in items if it[0] not in done]
    batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    print("待补 %d 词，分 %d 批（每批 %d 词，%d 并发）" % (len(todo), len(batches), batch, workers))
    out = open(out_path, "a", encoding="utf-8", newline="\n")
    if out.tell() == 0:
        out.write("# 由 llm_fill.py 用 %s 生成；命名与随包德语表一致（词\\t词性. 释义）\n" % MODEL)
        out.flush()
    t0 = time.time()
    lock = __import__("threading").Lock()
    failed = []          # 第一轮没拿到合格结果的词，第二轮严格重试
    retry_suffix = [""]  # 空 = 第一轮

    def work(idx_batch):
        idx, b = idx_batch
        prompt = "\n".join("%s\t%s" % (w, en) if en else w for w, _, en in b)
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "请给出下面 %d 个中文词的德语释义（每行「词<TAB>词性. 释义」）：\n%s%s"
                 % (len(b), prompt, retry_suffix[0])}]
        for attempt in (1, 2, 3):
            try:
                data = call(key, msgs, max_tokens)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    with lock:
                        stats["请求失败"] += len(b)
                        print("  [批 %d] 失败: %s" % (idx, exc))
                    return []
                time.sleep(2 * attempt)
        usage = data.get("usage") or {}
        with lock:
            stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
            stats["completion_tokens"] += usage.get("completion_tokens", 0)
        text = data["choices"][0]["message"]["content"]
        lines = [ln for ln in text.splitlines() if ln.strip()]
        by_word = {}
        for ln in lines:
            head = ln.split("\t", 1)[0].strip().lstrip("-•*> ").strip()
            by_word.setdefault(head, ln)
            by_word.setdefault(head.rstrip("。.;；"), ln)
        rows = []
        retrying = bool(retry_suffix[0])
        en_map = {w: en for w, _, en in b}
        for w, syl, en in b:
            raw = by_word.get(w)
            if raw is None:
                stats["模型漏掉"] += 1
                if not retrying:
                    with lock:
                        failed.append((w, syl, en))
                continue
            norm, why = normalize(w, raw, relaxed, en or "")
            if norm is None:
                stats["丢弃:" + why.split(":")[0]] += 1
                if not retrying:
                    with lock:
                        failed.append((w, syl, en))
                continue
            # 回声过滤：德语释义与英语提示完全一样（且不是纯大小写差别）→ 第一轮退回重问
            if not retrying and en:
                got = re.sub(r"^[a-z]+\.\s*", "", norm.split("\t", 1)[1]).strip().lower()
                hint = re.match(r"^[a-z]+\.\s*(.+)$", en.strip(), re.I)
                hint = (hint.group(1) if hint else en).strip().lower()
                if got and got == hint:
                    stats["疑似照抄英语"] += 1
                    with lock:
                        failed.append((w, syl, en))
                    continue
            rows.append(norm)
            stats["成功"] += 1
        return rows

    def pump(pool, jobs, tag):
        for n, rows in enumerate(pool.map(work, jobs), 1):
            with lock:
                for r in rows:
                    out.write(r + "\n")
                out.flush()
                if n % 10 == 0 or n == len(jobs):
                    el = time.time() - t0
                    print("  %s%d/%d 批  成功 %d  用时 %.0fs  (%.1f 词/秒)"
                          % (tag, n, len(jobs), stats["成功"], el, stats["成功"] / max(el, 1e-9)))

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        pump(pool, list(enumerate(batches)), "")
        if failed:
            pend = list(failed)
            failed.clear()
            retry_suffix[0] = ("\n\n（严格重试）上面这些词里有些上一轮没给出合格结果："
                               "名词必须带 der/die/das；只能是德语，绝对不许出现英语；"
                               "确实想不出的写「词<TAB>」留空。")
            rjobs = list(enumerate([pend[i:i + batch] for i in range(0, len(pend), batch)]))
            print("第二轮严格重试 %d 词（%d 批）" % (len(pend), len(rjobs)))
            pump(pool, rjobs, "重试 ")
            retry_suffix[0] = ""
    out.close()
    print("\n统计:", dict(stats))
    print("输出:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = 不限")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=2400)
    ap.add_argument("--out", default=r"E:\codemain\qingjian-de\de-glossary\llm-fill.tsv")
    ap.add_argument("--skip", action="append", default=[], help="已有结果的文件，里面的词不再处理（可多次给）")
    ap.add_argument("--relaxed", action="store_true", help="放宽：专名/无冠词名词也收，词性缺失用英语提示兜底")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    items = load_worklist()
    print("词库缺口 %d 词（已按词频降序）；其中英语表有提示的 %d" % (len(items), sum(1 for _, _, e in items if e)))
    if args.report:
        print("\n词频分布: >=10000: %d, >=1000: %d, >=100: %d, >=10: %d, <10: %d" % (
            sum(1 for _, f, _ in items if f >= 10000), sum(1 for _, f, _ in items if f >= 1000),
            sum(1 for _, f, _ in items if f >= 100), sum(1 for _, f, _ in items if f >= 10),
            sum(1 for _, f, _ in items if f < 10)))
        print("\n前 30 个高频缺口词:")
        for w, f, e in items[:30]:
            print("   %-6s freq=%-7d %s" % (w, f, e[:40]))
        print("\n随机 20 个（模拟全量里的样子）:")
        for w, f, e in random.Random(7).sample(items[:20000], 20):
            print("   %-6s freq=%-7d %s" % (w, f, e[:40]))
        return
    key = load_key()
    sel = items[args.offset:args.offset + args.limit] if args.limit else items[args.offset:]
    run(key, sel, args.batch, args.workers, args.out, args.max_tokens, args.relaxed, args.skip)


if __name__ == "__main__":
    main()
