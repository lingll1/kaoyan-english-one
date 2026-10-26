#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把已核定的答案与参考译文填回 SOURCE.md / SOURCE-others.md 的占位符。

用法：
    python _fillans.py 2023

需要先准备好 `<年份>/_ans.json`：
{
  "reading": "CBACD...",      # 21–40，按题号顺序，20 个字母
  "cloze":   "CADCC...",      # 1–20，20 个字母
  "partb":   {"41": "B", "42": "F", ...},
  "trans":   {"46": "译文…", ...}   # 可选；缺省则尝试从 _web/SOURCE-others.web.md 提取
}

替换规则：
- SOURCE.md 里按出现顺序把第 i 个 `**答案 ?**` 换成 reading[i]
- SOURCE-others.md 里前 20 个 `**答案 ?**` 换成 cloze，再往后 5 个换成 partb
- `**参考译文 ?**` 按 46→50 顺序填入
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def fill_sequential(text, placeholder, values, label, errs, wrap=None):
    """按出现顺序替换占位符；wrap 可把裸值包装成 Markdown 片段"""
    parts = text.split(placeholder)
    if len(parts) - 1 != len(values):
        errs.append(f"{label}: 占位符 {len(parts) - 1} 个，待填 {len(values)} 个")
    out = parts[0]
    for i, p in enumerate(parts[1:]):
        v = values[i] if i < len(values) else "?"
        if wrap and v != "?":
            v = wrap(v)
        out += v + p
    return out


def extract_web_trans(root):
    """从 _web/SOURCE-others.web.md 提取 (46)–(50) 的参考译文"""
    p = root / "_web" / "SOURCE-others.web.md"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8")
    res = {}
    for m in re.finditer(r"###\s*划线句（(\d+)）[^\n]*\n+(.+?)\n+参考译文[:：]\s*([^\n]+)", t, re.S):
        no = m.group(1)
        tr = m.group(3).strip().split("\n")[0].strip()
        if no not in res and tr:
            res[no] = tr
    return res


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else ""
    if not year:
        raise SystemExit("用法：python _fillans.py <年份>")
    root = BASE / year
    ap = root / "_ans.json"
    if not ap.exists():
        raise SystemExit(f"缺少 {ap}")
    a = json.loads(ap.read_text(encoding="utf-8"))
    errs = []

    # ---- SOURCE.md（阅读 21–40）----
    sp = root / "SOURCE.md"
    txt = sp.read_text(encoding="utf-8")
    reading = [c for c in a.get("reading", "") if c.isalpha()]
    txt = fill_sequential(txt, "**答案 ?**", reading, "SOURCE.md 阅读答案", errs)
    sp.write_text(txt, encoding="utf-8")

    # ---- SOURCE-others.md（完形 + PartB + 译文）----
    op = root / "SOURCE-others.md"
    otxt = op.read_text(encoding="utf-8")
    cloze = [c for c in a.get("cloze", "") if c.isalpha()]
    partb = a.get("partb", {}) or {}
    pb_vals = [partb.get(str(n), "?") for n in range(41, 46)]
    otxt = fill_sequential(otxt, "**答案 ?**", cloze + pb_vals, "SOURCE-others.md 答案", errs)

    trans = a.get("trans") or {}
    if not trans:
        trans = extract_web_trans(root)
        if trans:
            print(f"  从 web 版提取译文 {len(trans)} 条")
    tv = [trans.get(str(n), "?") for n in range(46, 51)]
    otxt = fill_sequential(otxt, "**参考译文 ?**", tv, "SOURCE-others.md 译文", errs)
    op.write_text(otxt, encoding="utf-8")

    # 校验
    for f, name in ((sp, "SOURCE.md"), (op, "SOURCE-others.md")):
        left = f.read_text(encoding="utf-8").count("**答案 ?**") + f.read_text(encoding="utf-8").count("**参考译文 ?**")
        print(f"  {name}: 剩余占位 {left}")
        if left:
            errs.append(f"{name} 仍有 {left} 个占位")
    if errs:
        print("\n问题：")
        for e in errs:
            print("  !", e)
        raise SystemExit(1)
    print(f"{year} 答案与译文填充完成。")


if __name__ == "__main__":
    main()
