"""把 LLM 补出来的德语释义合并进 HanDeDict 版德语表。

规则：
- 随包/已有表（HanDeDict + german-nouns 冠词版）优先，同词不覆盖；
- LLM 表只补已有表里没有的词；
- 输出 UTF-8 无 BOM + LF，注释头保留，附一行来源说明。

用法：python merge_glossary.py <base.tsv> <llm.tsv> <out.tsv>
"""
import sys


def read_tsv(path):
    comments, rows, words = [], [], set()
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                comments.append(line)
                continue
            if "\t" not in line:
                continue
            w = line.split("\t", 1)[0]
            if w in words:
                continue
            words.add(w)
            rows.append(line)
    return comments, rows, words


def main():
    base_path, llm_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    b_comments, b_rows, b_words = read_tsv(base_path)
    l_comments, l_rows, _ = read_tsv(llm_path)
    new = []
    for line in l_rows:
        w = line.split("\t", 1)[0]
        if w in b_words:
            continue
        b_words.add(w)
        new.append(line)
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        for c in b_comments:
            out.write(c + "\n")
        out.write("# 以下 %d 条中文→德语释义由 llm_fill.py 调 DeepSeek (%s) 生成，"
                  "补 HanDeDict 未收录的高频词；名词已按要求带定冠词。\n" % (len(new), "deepseek-v4-flash"))
        for line in b_rows:
            out.write(line + "\n")
        for line in new:
            out.write(line + "\n")
    print("底表 %d 行 + 新增 %d 行 = %d 行 → %s"
          % (len(b_rows), len(new), len(b_rows) + len(new), out_path))


if __name__ == "__main__":
    main()
