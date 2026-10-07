import json, os, sys
sys.path.insert(0, r"E:\codemain\qingjian-de\de-glossary")
import llm_fill as L
key = L.load_key()
items = L.load_worklist()
b = [it for it in items if it[0] in ("了","吗","呢","嘛","都是","不会","你是","不知道","狗","这是")]
prompt = "\n".join("%s\t%s" % (w, e) if e else w for w, _, e in b)
msgs = [{"role":"system","content":L.SYSTEM},
        {"role":"user","content":"请给出下面 %d 个中文词的德语释义（每行「词<TAB>词性. 释义」）：\n%s" % (len(b), prompt)}]
data = L.call(key, msgs, 1200)
print("usage:", data.get("usage"))
msg = data["choices"][0]["message"]
print("message keys:", list(msg.keys()))
print("finish_reason:", data["choices"][0].get("finish_reason"))
print("---------- RAW ----------")
print(repr(msg.get("content"))[:3000])
print("---------- reasoning? ----------")
print(repr(msg.get("reasoning_content"))[:600] if msg.get("reasoning_content") else "(none)")
