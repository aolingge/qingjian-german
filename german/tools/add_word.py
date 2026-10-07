# -*- coding: utf-8 -*-
"""add_word.py —— 给德语个人释义表快速加词/改词（一条命令，不用重打包）。

个人释义表 `%APPDATA%\\Qingjian\\user-glossary-de.tsv` **叠在随包释义表上面**：
同一个词以它为准（`qingjian-translate\\src\\layered_translator.rs:40-44`），格式与随包表相同
（`词<TAB>[词性. ]译词[|读音]`，`#` 开头是注释），可以手改，输入法重启后生效。

    查一下模型会怎么译（只打印，不写文件）：
        python add_word.py 森饰 甜头 "拜仁慕尼黑"
    现在词表里是什么、个人表里又是什么：
        python add_word.py --list 森饰
    真写进个人释义表（会先备份）：
        python add_word.py 森饰 --write
    写完顺手重启 server，让新表立刻生效（会停掉 qingjian-server，宿主会自动拉起）：
        python add_word.py 森饰 --write --reload

生僻词/自造词/网络用语这类「随包表里没有或译得不对」的词，用这个工具就地覆盖，
不用改词表、不用重打包、也不影响别人。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_tools as T                                        # noqa: E402

PERSONAL = os.path.join(os.environ["APPDATA"], "Qingjian", "user-glossary-de.tsv")
HEADER = [
    "# 青简个人释义表（de）：格式同随包释义表，可手改。词<TAB>[词性. ]译词[|读音]",
    "# 个人表叠在随包表上面：同一个词以这里为准（layered_translator.rs:40-44）。",
    "# 由 de-glossary\\add_word.py 写入（也可手工编辑）。",
]
ADD_SYSTEM = (
    T.GAP_SYSTEM
    + "\n这次只处理给定的这几个中文词：每个词给 1–2 条最常用的德语说法，用「; 」分隔；"
      "只输出这几行，顺序与输入一致，不要多输出别的词。\n"
      "输入行里可能带「参考英语」和「现有德语」：现有德语**已经是对的**时，就把它原样复制到输出"
      "（它没有词性前缀时也不要自己加 n./v. 之类；只有确实译错、或缺少更常用的说法时才改）。"
)


def read_kv(path):
    out, order = {}, []
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            w, g = (s.strip() for s in line.rstrip("\n").split("\t", 1))
            if w and g:
                if w not in out:
                    order.append(w)
                out[w] = g
    return out, order


def packaged_gloss():
    rows, _ = read_kv(T.final_or_merged())
    return rows


def word_level_map():
    lv = dict(T.load_goethe())
    for path in (os.path.join(HERE, "llm-cefr.tsv"), os.path.join(HERE, "llm-cefrword.tsv")):
        if not os.path.isfile(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            w, v = (s.strip() for s in line.rstrip("\n").split("\t", 1))
            v = v.upper().replace("B2+", "B2")
            if w and v in T.LEVEL_ORDER and w.lower() not in lv:
                lv[w.lower()] = v
    return lv


def level_of(gloss, levels):
    body = T.POS_PREFIX.sub("", gloss, count=1).strip() if T.POS_PREFIX.match(gloss) else gloss
    lvl, kind = T.resolve_level(T.content_words(body), levels)
    return ("%s（%s）" % (lvl, kind)) if lvl else "-"


LEGAL_POS = {"n", "v", "adj", "adv", "int", "pron", "num", "prep", "conj", "part", "phr", "m"}


def sanitize(gloss):
    """模型偶尔会写 `Eigenname. Bayern München` 这种非法词性前缀：不是那 12 个就去掉前缀。"""
    m = re.match(r"^([A-Za-zÄÖÜäöüß]{1,12})\.\s+(.+)$", gloss.strip())
    if m and m.group(1).lower() not in LEGAL_POS:
        return m.group(2).strip()
    return gloss.strip()


def ask(words, glosses, en, freq):
    """一次调用生成所有词的德语释义（有英语提示就带上，模型自己判断用法）。"""
    lines = []
    for w in words:
        hint = en.get(w, "")
        old = glosses.get(w, "")
        tag = []
        if hint:
            tag.append(hint)
        if old:
            tag.append("现有德语: " + old)
        lines.append("%s\t%s" % (w, " | ".join(tag)) if tag else w)
    msgs = [{"role": "system", "content": ADD_SYSTEM},
            {"role": "user", "content": "请为下面 %d 个中文词写德语译文：\n%s" % (len(words), "\n".join(lines))}]
    content = T.call(T.load_key(), msgs, max(600, 120 * len(words)))
    out = {}
    for raw in content.splitlines():
        line = raw.strip().lstrip("-•*> `").strip()
        if not line or line.startswith("#") or line.startswith("```") or "\t" not in line:
            continue
        line = re.sub(r"^\d+[.、)]\s*", "", line)
        w, g = (s.strip() for s in line.split("\t", 1))
        if w in words and g and w not in out:
            out[w] = sanitize(g)
    return out


def write_personal(new_entries):
    """把新条目 upsert 进个人释义表（原文件先备份成 .bak-<时间戳>）。"""
    old, order = read_kv(PERSONAL)
    if os.path.isfile(PERSONAL):
        bak = PERSONAL + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(PERSONAL, bak)
        print("已备份个人释义表 → %s" % bak)
    added = [w for w in new_entries if w not in old]
    for w, g in new_entries.items():
        if w not in old:
            order.append(w)
        old[w] = g
    os.makedirs(os.path.dirname(PERSONAL), exist_ok=True)
    with open(PERSONAL, "w", encoding="utf-8", newline="\n") as f:
        for line in HEADER:
            f.write(line + "\n")
        for w in order:
            f.write("%s\t%s\n" % (w, old[w]))
    print("写入 %d 条（新增 %d、覆盖 %d）→ %s" % (
        len(new_entries), len(added), len(new_entries) - len(added), PERSONAL))


def reload_server():
    exe = "qingjian-server.exe"
    try:
        r = subprocess.run(["taskkill", "/IM", exe, "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("已停止 %s（返回码 %d）：输入法宿主会在下一次输入时自动拉起，加载新的个人释义表" % (exe, r.returncode))
    except Exception as exc:                                  # noqa: BLE001
        print("停 server 失败（%s）：请手动重启输入法，或等下次切换语言" % str(exc)[:80])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="*", help="中文词（可多个）")
    ap.add_argument("--write", action="store_true", help="真的写进个人释义表（默认只打印）")
    ap.add_argument("--reload", action="store_true", help="写完停掉 qingjian-server，让新表立刻生效")
    ap.add_argument("--list", action="store_true", help="只列出个人释义表里已有的条目")
    ap.add_argument("--no-llm", action="store_true",
                    help="只查表（随包表/个人表/词频/CEFR/英语义项），不调模型——纯离线查询")
    ap.add_argument("--personal", default=PERSONAL, help="个人释义表路径（默认 %s）" % PERSONAL)
    args = ap.parse_args()
    globals()["PERSONAL"] = args.personal

    personal, order = read_kv(args.personal)
    if args.list and not args.words:
        print("个人释义表 %s：%d 条" % (args.personal, len(personal)))
        for w in order:
            print("   %s\t%s" % (w, personal[w]))
        return 0
    if not args.words:
        ap.print_help()
        return 0

    glosses = packaged_gloss()
    en = {w: v[0] for w, v in T.read_en().items()}
    freq = dict(T.read_dict())
    levels = word_level_map()
    print("词 %d 个；随包表里有 %d 个；个人表里有 %d 个\n" % (
        len(args.words), sum(1 for w in args.words if w in glosses),
        sum(1 for w in args.words if w in personal)))

    new = {} if args.no_llm else ask(args.words, glosses, en, freq)
    if args.no_llm:
        print("（离线查询模式，不调模型）\n")
    elif not new:
        print("模型没有返回任何条目，请重试或检查 API key")
        return 1
    for w in args.words:
        print("【%s】 词频 %s" % (w, freq.get(w, "不在词库")))
        print("   随包表: %s%s" % (glosses.get(w, "（没有）"),
                                 ("    CEFR " + level_of(glosses[w], levels)) if w in glosses else ""))
        print("   个人表: %s" % personal.get(w, "（没有）"))
        if en.get(w):
            print("   英语义项: %s" % " / ".join(T.read_en()[w]))
        if w in new:
            print("   模型给出: %s    CEFR %s" % (new[w], level_of(new[w], levels)))
        elif not args.no_llm:
            print("   模型没有给出（可再跑一次）")
        print("")
    if args.no_llm:
        return 0
    if not args.write:
        print("（预览模式，没写文件；加 --write 才写进个人释义表）")
        return 0
    write_personal(new)
    if args.reload:
        reload_server()
    else:
        print("输入法下次启动（或切换学习语言）时会加载新表；加 --reload 可以立刻重启 server。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
