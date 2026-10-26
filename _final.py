# -*- coding: utf-8 -*-
"""最终验收：结构计数 + 常见硬编码错误扫描（按年份目录遍历）。

用法：python _final.py [年份]     不给年份则检查全部年份。
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent

BAD = [
    (r"变体 3 题", "目录锚点仍写「变体 3 题」"),
    (r"同类型变体题 · 3 题", "变体区标题仍是 3 题"),
    (r"§", "出现 § 符号"),
    (r"meta\.file", "残留 meta.file 引用"),
    # 释义用了省略号却完全没有汉字（真正的空释义）。
    # 不算错误的情形：`prep. 在……中`（中文词典标准写法，含实义汉字）、
    # `num. 2017` / `n. LUMI`（数字与专有名词，本来无需中文）。
    (r'<span class="gl">(?![^<]*[\u4e00-\u9fff])[^<]*(?:……|\.\.\.)[^<]*</span>', "释义只有省略号，没有实义"),
]

# 说明：`...` 在语法结构描述（如 `It is all very well ..., but ...`）里是必需的教学符号；
# `……` 在词义里是中文词典标准写法（`prep. 在……中`）。二者均不判为错误。


def year_dirs():
    if not BASE.is_dir():
        return []
    return sorted(p.name for p in BASE.iterdir()
                  if p.is_dir() and len(p.name) == 4 and p.name.isdigit())


def check_year(year):
    docs = BASE / year / "docs"
    if not docs.is_dir():
        return True, 0
    ok, n = True, 0
    for p in sorted(docs.glob("*Text*.html")):
        h = p.read_text(encoding="utf-8")
        print("== [%s] %s (%s B)" % (year, p.name, f"{len(h.encode('utf-8')):,}"))
        print("   para qz %d / qzcn %d / opt %d / plain %d / article.q %d"
              % (h.count('class="para qz"'), h.count('class="qzcn"'),
                 h.count('class="opt'), h.count('class="plain"'),
                 h.count('<article class="q">')))
        m = re.search(r"同类型变体题 · (\d+) 题", h)
        print("   变体区标题:", m.group(0) if m else "(未找到)")
        t = re.findall(r"<a href='#vs'>[^<]*</a>", h)
        print("   目录锚点:", t[0] if t else "(未找到)")
        for pat, msg in BAD:
            if re.search(pat, h):
                print("   ! ", msg)
                ok = False
        n += 1

    idx_p = docs / "index.html"
    if idx_p.exists():
        idx = idx_p.read_text(encoding="utf-8")
        print("== [%s] index.html (%s B)" % (year, f"{len(idx.encode('utf-8')):,}"))
        print("   链接:", re.findall(r'href="([^"]+\.html)"', idx))
    return ok, n


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    years = [pos[0]] if pos else year_dirs()
    ok, total = True, 0
    for y in years:
        o, n = check_year(y)
        ok = ok and o
        total += n
    print()
    if not total:
        print("没有可检查的产物。")
    print("全部检查通过。" if ok else "发现问题，见上。")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
