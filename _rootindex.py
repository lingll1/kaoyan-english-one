#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成跨年份总入口页 docs/index.html

用法：python _rootindex.py
- 扫描 2020–2026 各年 data/*.lesson.json
- 读取 meta（part / no / qs / theme / words）与已生成的 HTML 是否存在
- 输出 BASE/docs/index.html：按年份分节，列出每篇的标题、主题、题号、词数、链接
- 不修改任何既有文件，只写 docs/index.html
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
OUT = BASE / "docs" / "index.html"

ORDER = {"cloze": 0, "text1": 1, "text2": 2, "text3": 3, "text4": 4, "partb": 5, "trans": 6}
PART_ORDER = {"cloze": 0, "A": 1, "B": 2, "C": 3}

# 每种题型的：(中文标签, 英文标签, 右侧题型标签)
LBL = {
    "cloze": ("完形填空", "Use of English", "第 1–20 空"),
    "B": ("新题型", "Part B", "Part B"),
    "C": ("翻译", "Part C", "Part C"),
}

CN = "零一二三四五六七八九"


def cn(n):
    n = int(n)
    if n < 10:
        return CN[n]
    if n < 20:
        return "十" + (CN[n % 10] if n % 10 else "")
    return str(n)


def norm_part(p):
    """题型归一化：数据里既写过 'A' 也写过 'Part A' / 'Part A 传统阅读'，统一成 A/B/C/cloze。"""
    s = str(p or "A").strip()
    u = s.upper().replace(" ", "")
    for k in ("A", "B", "C"):
        if u.startswith("PART" + k) or u.startswith(k + "节"):
            return k
    return s


def fname_of(year, key, meta):
    part = norm_part(meta.get("part"))
    if part == "cloze":
        return f"英语一{year}_完形填空.html"
    if part == "B":
        return f"英语一{year}_新题型PartB.html"
    if part == "C":
        return f"英语一{year}_翻译PartC.html"
    return f"英语一{year}_阅读Text{meta.get('no', key)}.html"


def title_of(key, meta):
    part = norm_part(meta.get("part"))
    if part == "cloze":
        return "完形填空", "Use of English"
    if part == "B":
        return "新题型", "Part B"
    if part == "C":
        return "翻译", "Part C"
    return f"阅读 Text {meta.get('no', key)}", "Reading Comprehension"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def real_words(year, key):
    """从 words.txt 实际统计非标点词数（与 build.py 的 parse_words 规则一致）"""
    p = BASE / year / "data" / f"{key}.words.txt"
    if not p.exists():
        return None
    punct = re.compile(r"^[^0-9A-Za-z\u4e00-\u9fff]+$")
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("@") or line.startswith("#"):
            continue
        w = line.split("|")[0].strip()
        if w and not punct.match(w):
            n += 1
    return n


def scan_year(year):
    """-> [(sortkey, key, html_row_dict)]"""
    data = BASE / year / "data"
    docs = BASE / year / "docs"
    rows = []
    if not data.is_dir():
        return rows
    for lj in sorted(data.glob("*.lesson.json")):
        key = lj.name[: -len(".lesson.json")]
        try:
            d = json.loads(lj.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {year}/{key} lesson.json 解析失败：{e}")
            continue
        meta = d.get("meta") or {}
        part = norm_part(meta.get("part"))
        fname = fname_of(year, key, meta)
        exists = (docs / fname).exists()
        zh, en = title_of(key, meta)
        qs = str(meta.get("qs") or "")
        theme = str(meta.get("theme") or "").strip()
        words = real_words(year, key)
        if words is None:
            words = meta.get("words") or ""
        nq = len(d.get("questions") or [])
        nv = len(d.get("variants") or [])
        order = PART_ORDER.get(part, 9)
        no = meta.get("no")
        sub = str(no) if part == "A" else ""
        sk = (order, sub if sub.isdigit() else 99, key)
        rows.append(
            {
                "sk": sk,
                "key": key,
                "zh": zh,
                "en": en,
                "qs": qs,
                "theme": theme,
                "words": words,
                "nq": nq,
                "nv": nv,
                "href": f"{year}/docs/{fname}" if exists else "",
                "fname": fname,
                "exists": exists,
            }
        )
    rows.sort(key=lambda r: r["sk"])
    return rows


CSS = """
:root{--ink:#2b2722;--muted:#7a7167;--line:#e6dccb;--paper:#faf7f0;--card:#fffdf8;
--brown:#8a6b43;--teal:#28738a;--green:#2f6b47;--red:#a33b32}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:40px 28px 100px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:.5px}
.sub{color:var(--muted);font-size:14.5px;margin-bottom:8px}
.lede{color:#5d554b;font-size:15px;line-height:2;margin:18px 0 30px;
border-left:3px solid var(--brown);padding:2px 0 2px 16px;background:#fbf6ea;border-radius:0 8px 8px 0}
.yr{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:20px 22px 8px;margin:0 0 22px;box-shadow:0 1px 0 #fff inset,0 2px 10px rgba(120,100,70,.05)}
.yh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:4px}
.yh b{font-size:23px;letter-spacing:.5px}
.yh .cnt{font-size:12.5px;color:#fff;background:var(--brown);border-radius:20px;padding:2px 11px}
.yh .done{font-size:12.5px;color:#fff;background:var(--green);border-radius:20px;padding:2px 11px}
.yh .part{font-size:12.5px;color:#fff;background:#9a8a72;border-radius:20px;padding:2px 11px}
table{width:100%;border-collapse:collapse;margin:8px 0 14px}
td{padding:9px 8px;border-bottom:1px dashed #ece3d4;vertical-align:top}
tr:last-child td{border-bottom:none}
.t{font-weight:600;font-size:15.5px;white-space:nowrap}
.t small{display:block;font-weight:400;color:var(--muted);font-size:11.5px;letter-spacing:.6px}
.th{color:#4a4238;font-size:14.5px}
.qs{color:var(--teal);font-size:13px;white-space:nowrap;text-align:right}
.wc{color:var(--muted);font-size:13px;white-space:nowrap;text-align:right;width:74px}
a.go{display:inline-block;font-size:13.5px;color:#fff;background:var(--teal);
border-radius:8px;padding:3px 12px;text-decoration:none;white-space:nowrap}
a.go:hover{background:#1f5f74}
span.todo{display:inline-block;font-size:13px;color:#a4988a;background:#f3ece0;
border-radius:8px;padding:3px 12px;white-space:nowrap}
.ft{color:var(--muted);font-size:13px;margin-top:30px;line-height:2;border-top:1px solid var(--line);padding-top:16px}
code{background:#f1e9db;border-radius:4px;padding:1px 6px;font-size:13px}
"""


def build():
    years = sorted(
        d.name for d in BASE.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}", d.name)
    )
    blocks = []
    total = 0
    for year in years:
        rows = scan_year(year)
        if not rows:
            blocks.append(
                f'<div class="yr"><div class="yh"><b>{year}</b>'
                f'<span class="part">尚未开始</span></div>'
                f'<table><tr><td class="th" style="color:#a4988a">该年份还没有任何精读数据</td></tr></table></div>'
            )
            continue
        ok_n = sum(1 for r in rows if r["exists"])
        total += ok_n
        badge = (
            f'<span class="done">已生成 {ok_n} 篇</span>'
            if ok_n == len(rows)
            else f'<span class="cnt">已生成 {ok_n} / {len(rows)} 篇</span>'
        )
        trs = []
        for r in rows:
            act = (
                f'<a class="go" href="{esc(r["href"])}">打开</a>'
                if r["exists"]
                else '<span class="todo">待生成</span>'
            )
            theme = esc(r["theme"])
            wc = f'{esc(r["words"])} 词' if r["words"] != "" else ""
            trs.append(
                "<tr>"
                f'<td class="t">{esc(r["zh"])}<small>{esc(r["en"])}</small></td>'
                f'<td class="th">{theme}</td>'
                f'<td class="qs">{esc(r["qs"])}</td>'
                f'<td class="wc">{wc}</td>'
                f"<td style=\"text-align:right\">{act}</td>"
                "</tr>"
            )
        blocks.append(
            f'<div class="yr"><div class="yh"><b>{year} 年</b>{badge}</div>'
            "<table>" + "".join(trs) + "</table></div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>考研英语（一）逐词精读 · 2020–2026</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>考研英语（一）逐词精读</h1>
<div class="sub">2020 – 2026 · 阅读理解 / 完形填空 / 新题型 / 翻译</div>
<p class="lede">每篇独立成文档：正文逐段分开，每段下方给出本段语法点，行距拉大；<b>每个单词上方标小字音标与本句词义</b>；
真题题干与选项同样逐词标注，并附中文整句译文；题目后为四块解析（原句含义 · 语法辨析 · 难点解析 · 易错点解析），
另配 6 道同类型变体题。已生成 <b>{total}</b> 篇。</p>
{"".join(blocks)}
<div class="ft">
重新生成：<code>python build.py</code>（全部年份）· <code>python build.py 2024</code>（单年）· <code>python build.py 2024 2</code>（单篇）<br>
自检：<code>python verify.py 2024 2</code> · <code>python qc.py 2024 2</code> · <code>python _final.py 2024</code><br>
本页由 <code>_rootindex.py</code> 自动生成。
</div>
</div>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"→ {OUT.relative_to(BASE)}（{len(years)} 个年份，已生成 {total} 篇）")


if __name__ == "__main__":
    sys.exit(build())
