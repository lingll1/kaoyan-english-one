#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2021 英语（一）阅读理解 · 逐词精读文档生成器
------------------------------------------
输入：
  data/textN.words.txt   逐词标注（行式，词|音标|本句词义，@N 分段）
  data/textN.lesson.json 元信息 / 段落译文 / 段落语法 / 真题 / 变体题 / 词汇表
输出：
  docs/Text{N}_*.html    单文件文档（CSS/JS 内联，可离线、可打印）
  docs/index.html        四篇总目录

用法：
  python build.py            # 全量生成
  python build.py --check    # 只做数据校验
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import re
import html
import sys
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent          # 英语一/
YEAR = ""
ROOT = BASE            # 当前年份目录，由 set_year() 切换
DATA = ROOT / "data"
DOCS = ROOT / "docs"


def set_year(y):
    """切换到某个年份目录（BASE/<年份>），后续 DATA / DOCS 都指向它。"""
    global YEAR, ROOT, DATA, DOCS
    YEAR = str(y)
    ROOT = BASE / YEAR
    DATA = ROOT / "data"
    DOCS = ROOT / "docs"
    return ROOT


def year_dirs():
    """BASE 下的四位数字年份目录，升序。"""
    if not BASE.is_dir():
        return []
    return sorted(p.name for p in BASE.iterdir()
                  if p.is_dir() and len(p.name) == 4 and p.name.isdigit())

# ---------------------------------------------------------------- 工具

def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def read(path):
    return Path(path).read_text(encoding="utf-8")


# 纯标点判定
PUNCT_ONLY = re.compile(r"^[^0-9A-Za-z\u4e00-\u9fff]+$")
CLOSE_PUNCT = set('.,;:?!)]}%"”’')
OPEN_PUNCT = set('([{“‘')
DASH_PUNCT = set("—–-")


def norm_part(p):
    """题型归一化：数据里既写过 'A' 也写过 'Part A' / 'Part A 传统阅读'，统一成 A/B/C/cloze。"""
    s = str(p or "A").strip()
    u = s.upper().replace(" ", "")
    for k in ("A", "B", "C"):
        if u.startswith("PART" + k) or u.startswith(k + "节"):
            return k
    return s


def punct_side(w):
    """返回 'L'(紧贴左侧词，如逗号句号) / 'R'(紧贴右侧词) / None"""
    if w in DASH_PUNCT:
        return None
    if w in CLOSE_PUNCT:
        return "L"
    if w in OPEN_PUNCT:
        return "R"
    # 引号等两侧型：按首字符判断
    c0 = w[0]
    if c0 in OPEN_PUNCT:
        return "R"
    if c0 in CLOSE_PUNCT:
        return "L"
    return None


# ---------------------------------------------------------------- 解析 words

def parse_words(path):
    """-> [{'n':1,'tokens':[{'kind':'w'|'p','w','ipa','gl','side'}]}]"""
    if not Path(path).exists():
        raise SystemExit(f"缺少逐词文件：{path}")
    paras, cur = [], None
    for lineno, raw in enumerate(read(path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            try:
                n = int(line[1:].strip())
            except ValueError:
                raise SystemExit(f"{Path(path).name}:{lineno} 段号标记非法：{raw!r}")
            cur = {"n": n, "tokens": []}
            paras.append(cur)
            continue
        if cur is None:
            raise SystemExit(f"{Path(path).name}:{lineno} 首个词条前缺少 '@段号' 标记")
        parts = line.split("|")
        if len(parts) < 3:
            raise SystemExit(
                f"{Path(path).name}:{lineno} 行格式错误，需为 词|音标|释义 —— 实得：{raw!r}")
        w = parts[0].strip()
        ipa = parts[1].strip()
        gl = "|".join(parts[2:]).strip()
        if not w:
            raise SystemExit(f"{Path(path).name}:{lineno} 词为空")
        kind = "p" if PUNCT_ONLY.match(w) else "w"
        cur["tokens"].append({
            "kind": kind, "w": w, "ipa": ipa, "gl": gl,
            "side": punct_side(w) if kind == "p" else None,
        })
    if not paras:
        raise SystemExit(f"{Path(path).name} 未解析到任何段落")
    return paras


# ---------------------------------------------------------------- 解析 quiz（题干/选项逐词）

def parse_quiz(path):
    """解析题目逐词文件 data/textN.quiz.txt。
    块标记：@stem:21 / @opt:21:A / @v1 / @v1:A
    块内：词行 `词|音标|释义`；`~` 开头的一行是该块的中文整句译文。
    -> {'stem:21': {'tokens':[...], 'cn':'...'}, ...}
    """
    quiz = {}
    if not Path(path).exists():
        return quiz
    cur = None
    for lineno, raw in enumerate(read(path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            cur = {"tokens": [], "cn": ""}
            quiz[line[1:].strip()] = cur
            continue
        if cur is None:
            raise SystemExit(f"{Path(path).name}:{lineno} 首个词条前缺少 '@块名' 标记")
        if line.startswith("~"):
            cur["cn"] = line[1:].strip()
            continue
        parts = line.split("|")
        if len(parts) < 3:
            raise SystemExit(
                f"{Path(path).name}:{lineno} 行格式错误，需为 词|音标|释义 —— 实得：{raw!r}")
        w = parts[0].strip()
        ipa = parts[1].strip()
        gl = "|".join(parts[2:]).strip()
        if not w:
            raise SystemExit(f"{Path(path).name}:{lineno} 词为空")
        kind = "p" if PUNCT_ONLY.match(w) else "w"
        cur["tokens"].append({
            "kind": kind, "w": w,
            "ipa": "" if ipa == "_" else ipa,
            "gl": "" if gl == "_" else gl,
            "side": punct_side(w) if kind == "p" else None,
        })
    return quiz


# ---------------------------------------------------------------- 极简 markdown

def md_lite(text):
    if not text:
        return ""
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)

    blocks, buf, in_ul = [], [], False
    def flush():
        if buf:
            blocks.append("<p>" + "<br>".join(buf) + "</p>")
            del buf[:]

    for line in [x.strip() for x in t.split("\n")]:
        if not line:
            flush()
            continue
        m = re.match(r"^[-·•]\s+(.*)$", line)
        if m:
            if not in_ul:
                flush()
                blocks.append("<ul>")
                in_ul = True
            blocks.append("<li>" + m.group(1) + "</li>")
        else:
            if in_ul:
                blocks.append("</ul>")
                in_ul = False
            buf.append(line)
    flush()
    if in_ul:
        blocks.append("</ul>")
    return "\n".join(blocks)


# ---------------------------------------------------------------- 渲染：逐词段落

def render_para(tokens):
    """标点并入相邻词：贴左标点并入前词尾，贴右标点并入后词首，
    保证不会出现行首/行末孤立标点，也不产生额外字距。
    破折号（side=None）保留为独立位，避免抹掉原文两侧空格感。"""
    # 直引号 " 本身分不出开闭：按出现顺序奇偶配对（第 1、3、5…个是开引号 → 贴右，
    # 第 2、4、6…个是闭引号 → 贴左）。弯引号 “ ” 已在字典里天然区分，不受影响。
    qn, toks = 0, []
    for t in tokens:
        if t["kind"] == "p" and t["w"] == '"':
            qn += 1
            t = dict(t, side=("R" if qn % 2 == 1 else "L"))
        toks.append(t)

    items, pre = [], []
    for t in toks:
        if t["kind"] == "p":
            if t["side"] == "R":
                pre.append(t["w"])
            elif t["side"] == "L" and items:
                items[-1]["post"] += t["w"]
            else:
                # 破折号或段首孤立标点：独立展示
                items.append({"w": t["w"], "ipa": "", "gl": "",
                              "pre": "".join(pre), "post": "", "pc": True})
                pre = []
            continue
        items.append({"w": t["w"], "ipa": t["ipa"], "gl": t["gl"],
                      "pre": "".join(pre), "post": "", "pc": False})
        pre = []

    out = []
    for it in items:
        word = esc(it["pre"] + it["w"] + it["post"])
        if it["pc"]:
            out.append(f'<span class="wd wd-pc"><span class="an"></span>'
                       f'<span class="tx">{word}</span></span>')
        else:
            out.append(
                '<span class="wd">'
                f'<span class="an"><span class="ipa">{esc(it["ipa"])}</span>'
                f'<span class="gl">{esc(it["gl"])}</span></span>'
                f'<span class="tx">{word}</span>'
                '</span>'
            )
    return "".join(out)


# ---------------------------------------------------------------- 渲染：题目

KIND_CLASS = {"原句含义": "k1", "语法辨析": "k2", "难点解析": "k3", "易错点解析": "k4"}


def _qline(text, key, quiz):
    """题目区一行英文：有逐词数据就渲染「音标+本句词义在上、英文在下」的词块，
    再在其下方给整句中文译文；没有数据则退回纯文本。"""
    d = (quiz or {}).get(key) or (quiz or {}).get(str(key).lower())
    if d and d.get("tokens"):
        out = f'<div class="para qz">{render_para(d["tokens"])}</div>'
        if d.get("cn"):
            out += (f'<div class="qzcn"><b>译</b>'
                    f'<div class="qzw">{md_lite(d["cn"])}</div></div>')
        return out
    return f'<div class="plain">{esc(text)}</div>'


def render_question(q, is_variant=False, quiz=None):
    no = esc(q.get("no", ""))
    qkey = str(q.get("no", ""))
    qtype = esc(q.get("type", ""))
    stem = _qline(q.get("stem", ""), f"stem:{qkey}", quiz)
    raw_answer = (q.get("answer") or "").strip()
    has_opts = bool(q.get("options"))
    answer = raw_answer.upper() if has_opts else raw_answer
    locate = esc(q.get("locate", ""))

    head_bits = []
    if no:
        head_bits.append(f'<span class="qno">{"变体" if is_variant else "第"} {no} {"题" if not is_variant else ""}</span>'
                         if not is_variant else f'<span class="qno">{no}</span>')
    if qtype:
        head_bits.append(f'<span class="chip">{qtype}</span>')
    if q.get("tag"):
        head_bits.append(f'<span class="chip chip-2">{esc(q["tag"])}</span>')

    opts = []
    for k in sorted(q.get("options", {})):
        val = q["options"][k]
        if val is None:
            continue
        ok = " ok" if k == answer else ""
        body = _qline(val, f"opt:{qkey}:{k}", quiz)
        opts.append(f'<div class="opt{ok}"><span class="k">{esc(k)}</span>'
                    f'<div class="obody">{body}</div></div>')
    opts_html = f'<div class="opts">{"".join(opts)}</div>' if opts else ""

    blocks = []
    for b in q.get("blocks", []):
        k = b.get("k", "")
        blocks.append(
            f'<div class="blk {KIND_CLASS.get(k, "k2")}">'
            f'<span class="tag">{esc(k)}</span>'
            f'{md_lite(b.get("t", ""))}'
            '</div>'
        )

    ans_html = ""
    if has_opts:
        if answer:
            ans_html = (f'<div class="ansline"><span class="anspill">答案 {answer}</span>'
                        + (f'<span class="locate">定位：{locate}</span>' if locate else "")
                        + '</div>')
    elif raw_answer:
        # 翻译题：没有选项，answer 存的是参考译文
        ans_html = (f'<div class="reftrans"><span class="tag">参考译文</span>'
                    f'{md_lite(raw_answer)}</div>')

    return f'''<article class="q">
  <div class="q-head">{''.join(head_bits)}</div>
  <div class="stem">{stem}</div>
  {opts_html}
  {ans_html}
  <div class="analysis">{''.join(blocks)}</div>
</article>'''


# ---------------------------------------------------------------- 渲染：语法卡

def render_grammar(points):
    if not points:
        return ""
    items = []
    for p in points:
        h = esc(p.get("h", ""))
        b = md_lite(p.get("b", ""))
        # 把「结构 / 考点 / 例」之间的软换行升级为独立段落，避免整块挤成一团
        if b:
            b = b.replace("<br>", '</p><p class="gr">')
        items.append(f'<li><b>{h}</b>{("<br>" + b) if b else ""}</li>')
    return ('<div class="gram"><div class="gram-h">'
            '<span class="gram-ico">语</span>本段语法点 · 必须掌握</div>'
            f'<ul>{"".join(items)}</ul></div>')


# ---------------------------------------------------------------- 页面模板

CSS = r"""
:root{
  --bg:#f7f4ed; --card:#ffffff; --ink:#23262b; --ipa:#a4682f; --gloss:#28738a;
  --accent:#b8452d; --green:#3f6b45; --blue:#33628f; --muted:#7c7668;
  --line:#e6dfd2; --tx:17.5px; --an:10.5px; --rowgap:30px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink); line-height:1.85;
  font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1280px;margin:0 auto;padding:26px 78px 96px 28px}

/* ---------- 页头 ---------- */
.hd{background:linear-gradient(158deg,#fffdf7 0%,#f5eee1 100%);border:1px solid var(--line);
  border-radius:18px;padding:26px 28px 22px;box-shadow:0 2px 16px rgba(122,101,70,.07)}
.kicker{font-size:12.5px;letter-spacing:.16em;color:var(--muted)}
h1{font-family:Georgia,"Songti SC",serif;font-size:29px;margin:.3em 0 .12em;
  letter-spacing:.01em;color:#1f2226;font-weight:600}
.sub{color:#514c42;font-size:15px;line-height:1.8}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.badge{font-size:12.5px;padding:3px 11px;border-radius:11px;background:#efe7d7;
  color:#7a6338;letter-spacing:.03em}
.badge.b2{background:#e6efe4;color:#3f6b45}
.badge.b3{background:#e5eef6;color:#33628f}

/* ---------- 目录 ---------- */
.toc{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;padding-top:14px;border-top:1px dashed #ddd3c0}
.toc a{font-size:13px;color:#6f5a38;text-decoration:none;background:#f9f4e9;
  border:1px solid #e8dfcc;padding:4px 11px;border-radius:12px}
.toc a:hover{background:#f1e6d1;color:#4d3d21}

/* ---------- 卡片 ---------- */
.sec{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:22px 24px 24px;margin:22px 0;box-shadow:0 1px 12px rgba(122,101,70,.05)}
.sec-title{display:flex;align-items:center;gap:10px;font-size:15px;color:#5a5344;
  margin:0 0 16px;font-weight:600;letter-spacing:.06em}
.sec-title .no{display:inline-flex;width:27px;height:27px;border-radius:50%;
  background:#efe6d4;color:#8a6b43;align-items:center;justify-content:center;
  font-family:Georgia,serif;font-size:13.5px;font-weight:700;flex:none}
.sec-title .en{font-family:Georgia,serif;font-size:12.5px;color:#a09480;letter-spacing:.1em;font-weight:400}
.slotbadge{margin-left:auto;padding:3px 11px;border-radius:20px;background:#f2e7d2;color:#8a6b43;
  font-size:12.5px;font-weight:500;letter-spacing:.02em;white-space:nowrap}
.para-empty{padding:10px 14px;border:1px dashed #d9ccb2;border-radius:9px;background:#fbf7ed;
  color:#9a8d75;font-size:13.5px}

/* ---------- 逐词段落 ---------- */
.para{display:flex;flex-wrap:wrap;align-items:flex-end;column-gap:0;
  row-gap:var(--rowgap);padding:8px 2px 12px}
.wd{display:inline-flex;flex-direction:column;align-items:center;
  padding:0 3.8px;line-height:1;max-width:100%}
.wd .an{display:flex;flex-direction:column;align-items:center;gap:2px;
  margin-bottom:5px;max-width:134px;text-align:center}
.wd .ipa{white-space:nowrap}
.wd .ipa{font-family:"Segoe UI","Lucida Sans Unicode","Charis SIL","Gentium Plus",sans-serif;
  font-size:var(--an);color:var(--ipa);letter-spacing:.015em;line-height:1.2}
.wd .gl{font-size:var(--an);color:var(--gloss);line-height:1.2}
.wd .tx{font-family:Georgia,"Times New Roman",serif;font-size:var(--tx);color:#1d2024;
  white-space:nowrap;line-height:1.35;letter-spacing:.005em}
.pc{font-family:Georgia,"Times New Roman",serif;font-size:var(--tx);color:#3a3a3a;
  line-height:1.35;padding:0 2px}
.pc-l{padding-left:0;padding-right:3px}
.pc-r{padding-right:0;padding-left:3px}

/* ---------- 译文 / 语法 ---------- */
.trans{margin:16px 0 0;padding:13px 17px;border-left:3px solid #d9c9a6;background:#fbf8f0;
  border-radius:0 10px 10px 0;font-size:14.5px;color:#514c40;line-height:1.95}
.trans b{color:#8a6b43;font-weight:700;margin-right:7px;letter-spacing:.06em}
.trans p{margin:0}
.trans p + p{margin-top:6px}

.gram{margin:16px 0 0;padding:15px 18px 17px;background:#f2f7f1;
  border:1px solid #dbe8d8;border-radius:12px}
.gram-h{font-size:13px;color:var(--green);font-weight:700;letter-spacing:.07em;
  margin:0 0 10px;display:flex;gap:8px;align-items:center}
.gram-ico{display:inline-flex;width:19px;height:19px;border-radius:5px;background:#dcebd9;
  color:#3f6b45;align-items:center;justify-content:center;font-size:12px}
.gram ul{margin:0;padding-left:20px}
.gram li{margin:13px 0;font-size:14.5px;line-height:2.0;color:#343a30}
.gram li>b{color:#2f5c37}
.gram p{margin:5px 0 0}
.gram p.gr{margin:9px 0 0}
.gram code{background:#e6f0e4;color:#33603c;padding:1px 5px;border-radius:4px;
  font-family:Consolas,"Courier New",monospace;font-size:13px}
.gram strong{color:#2b5533}

/* ---------- 题目 ---------- */
.q{background:#fff;border:1px solid var(--line);border-radius:14px;
  padding:18px 20px 16px;margin:16px 0;box-shadow:0 1px 6px rgba(122,101,70,.04)}
.q-head{display:flex;gap:9px;align-items:center;margin-bottom:9px;flex-wrap:wrap}
.qno{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:26px;
  padding:0 9px;border-radius:13px;background:var(--accent);color:#fff;font-size:13px;
  font-weight:700;letter-spacing:.03em}
.chip{font-size:12px;padding:2px 10px;border-radius:10px;background:#efe7d7;
  color:#7a6338;letter-spacing:.04em}
.chip-2{background:#e5eef6;color:#33628f}
.stem{font-family:Georgia,"Times New Roman",serif;font-size:16.5px;line-height:1.8;
  color:#1f2226;margin:2px 0 12px}
/* 选项：两列并排，字号比题干更小，节省纵向空间 */
.opts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px 22px;margin-bottom:4px}
.opt{display:flex;align-items:flex-start;gap:8px;
  font-family:Georgia,"Times New Roman",serif;
  font-size:14px;color:#2d3036;padding:3px 10px;border-radius:7px;line-height:1.6}
.opt .k{color:var(--accent);font-weight:700;min-width:13px;flex:none;
  font-size:14px;padding-top:23px}
.opt .obody{flex:1;min-width:0}
.opt .plain{font-family:Georgia,"Times New Roman",serif;font-size:14px;line-height:1.65}
/* 题目区逐词块：字号略小于正文，注释仍压在词上方 */
.para.qz{--tx:15px;--an:9.5px;--rowgap:15px;margin-bottom:0}
/* 选项内再缩小一档 */
.opt .para.qz{--tx:13.5px;--an:8.5px;--rowgap:12px}
.qzcn{display:flex;align-items:flex-start;gap:8px;
  font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:14px;line-height:1.95;
  color:#42505a;background:#f2f6f8;border-left:3px solid #a9c4d1;border-radius:0 9px 9px 0;
  padding:6px 13px;margin:11px 0 2px}
.qzcn b{flex:none;color:#33628f;font-weight:600;font-size:12px;letter-spacing:.1em;
  line-height:2.28;padding-top:1px}
.qzcn .qzw{flex:1;min-width:0}
.qzcn .qzw p{margin:0}
.opt .qzcn{font-size:12.5px;line-height:1.8;padding:4px 10px;margin:7px 0 1px}
.opt .qzcn b{font-size:11px;line-height:2.05}
.opt.ok{background:#eef7ec;box-shadow:inset 0 0 0 1px #cfe6cb}
.opt.ok .k::after{content:"✓";font-size:11px;margin-left:2px}
.ansline{margin:13px 0 2px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.anspill{background:#e8f3e6;border:1px solid #bfdcbb;color:#2f6b34;font-size:13.5px;
  font-weight:700;padding:3px 13px;border-radius:12px;letter-spacing:.04em}
.locate{font-size:12.5px;color:var(--muted)}
/* 翻译题的参考译文（无选项，answer 存中文译文） */
.reftrans{margin:13px 0 2px;padding:12px 15px 13px;border-radius:10px;font-size:14.5px;
  line-height:1.95;color:#2b3a31;background:#f2f8f3;border:1px solid #d5e6d9}
.reftrans .tag{display:inline-block;font-size:11.5px;font-weight:700;color:#2f6b47;
  background:#dcefe2;padding:2px 10px;border-radius:9px;margin-right:10px;vertical-align:2px;
  letter-spacing:.03em}
.reftrans p{margin:6px 0 0}
.reftrans p:first-of-type{margin-top:2px}

/* ---------- 解析块 ---------- */
.analysis{margin-top:8px}
.blk{margin:11px 0 0;padding:12px 15px 13px;border-radius:10px;font-size:14.5px;
  line-height:1.95;color:#2e3239}
.blk .tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.06em;
  padding:1px 10px;border-radius:9px;margin-bottom:7px}
.blk p{margin:0}
.blk p+p{margin-top:6px}
.blk ul{margin:4px 0 0;padding-left:20px}
.blk li{margin:5px 0}
.blk strong{color:#1f2226}
.blk.k1{background:#fdf8ec;box-shadow:inset 0 0 0 1px #f0e3c6}
.blk.k1 .tag{background:#f2e2bd;color:#7d5a1e}
.blk.k2{background:#f1f6fb;box-shadow:inset 0 0 0 1px #dbe7f3}
.blk.k2 .tag{background:#d8e6f5;color:#2b5680}
.blk.k3{background:#f6f2fa;box-shadow:inset 0 0 0 1px #e4dbf0}
.blk.k3 .tag{background:#e4dbf0;color:#5c4880}
.blk.k4{background:#fdf3f1;box-shadow:inset 0 0 0 1px #f3dcd6}
.blk.k4 .tag{background:#f6dcd5;color:#9c4430}

/* ---------- 词汇表 ---------- */
.gloss{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px}
.gi{border:1px solid var(--line);border-radius:11px;padding:10px 13px;background:#fffdf9}
.gi .gw{font-family:Georgia,serif;font-size:15.5px;color:#1f2226;font-weight:600}
.gi .gi2{font-family:"Segoe UI","Lucida Sans Unicode",sans-serif;font-size:11.5px;color:var(--ipa)}
.gi .gc{font-size:13.5px;color:#4a4438;line-height:1.8;margin-top:3px}
.gi .gn{font-size:12.5px;color:var(--muted);line-height:1.75;margin-top:3px}

/* ---------- 结构简析 ---------- */
.outline{border-left:3px solid #cdd9c9;padding-left:15px;margin:6px 0 0}
.outline li{margin:7px 0;font-size:14.5px;line-height:1.9;color:#343a30}
.outline b{color:#2f5c37}

/* ---------- 工具条 ---------- */
.toolbar{position:fixed;right:18px;bottom:22px;display:flex;flex-direction:column;gap:9px;z-index:60}
.toolbar button{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);
  background:#fffdf8;color:#6b6355;font-size:13px;cursor:pointer;
  box-shadow:0 2px 12px rgba(122,101,70,.16);font-family:inherit;line-height:1}
.toolbar button:hover{background:#f3ece0}
.toolbar button:active{transform:scale(.95)}
.toolbar button.off{opacity:.42}
.toolbar button#t-rate{font-size:11.5px;letter-spacing:-.3px;font-family:Consolas,"SF Mono",monospace;font-weight:600}
.toolbar button#t-rate.fast{background:#c0653a;color:#fff;border-color:#c0653a}

/* ---------- 语音朗读 ---------- */
.spk{flex:none;align-self:flex-end;width:17px;height:17px;margin:0 3px 3px 0;padding:0;
  display:inline-flex;align-items:center;justify-content:center;
  border:1px solid #e2d8c4;border-radius:5px;background:#fbf7ed;color:#b3a58b;
  cursor:pointer;line-height:1;transition:background .15s,color .15s,border-color .15s}
.spk:hover{background:#f0e5cf;color:#8a6b43;border-color:#cdbfa2}
.spk.on{background:#8a6b43;color:#fff;border-color:#8a6b43}
.spk svg{display:block}
.wd.reading{background:#f8e7a8;border-radius:5px;box-shadow:0 0 0 1.5px #ddbe66}
.wd.reading .tx{color:#6b4a12}
.wd.reading .ipa,.wd.reading .gl{color:#8a6a2a}
.para.qz .spk{width:15px;height:15px;margin-bottom:2px}
.para.qz .spk svg{width:11px;height:11px}
.dbgbox{position:fixed;left:12px;top:12px;z-index:999;max-width:420px;max-height:260px;overflow:auto;
  background:rgba(24,22,18,.92);color:#f5efe2;font:12px/1.6 Consolas,monospace;padding:10px 12px;
  border-radius:9px;white-space:pre-wrap;pointer-events:none}
body.no-ann .wd .an{display:none}
body.no-gloss .wd .gl{display:none}
body.no-ipa .wd .ipa{display:none}
body.no-ann .wd .an{margin-bottom:0}

/* ---------- 页脚 ---------- */
.ft{margin-top:34px;padding-top:16px;border-top:1px dashed #ddd3c0;font-size:12.5px;
  color:var(--muted);line-height:1.9}
.ft a{color:#8a6b43}

/* ---------- 响应式 ---------- */
@media (max-width:980px){
  .opts{grid-template-columns:1fr}
}
@media (max-width:640px){
  :root{--tx:15.5px;--an:9.5px;--rowgap:24px}
  .wrap{padding:16px 48px 84px 12px}
  h1{font-size:23px}
  .sec{padding:16px 14px 18px;border-radius:13px}
  .hd{padding:18px 16px}
  .stem{font-size:15.5px}
  .opt{font-size:13.5px}
  .opt .para.qz{--tx:13px;--an:8px;--rowgap:11px}
  .toolbar{right:10px;bottom:14px}
  .toolbar button{width:40px;height:40px}
  .gloss{grid-template-columns:1fr}
}

/* ---------- 打印 ---------- */
@media print{
  :root{--tx:15px;--an:9px;--rowgap:22px}
  body{background:#fff}
  .wrap{max-width:none;padding:0}
  .toolbar,.toc{display:none}
  .hd,.sec,.q,.gi{box-shadow:none}
  .sec,.q,.gi,.gi,.wd{break-inside:avoid}
  .sec{page-break-inside:avoid}
  @page{size:A4;margin:13mm 14mm}
  a{color:inherit;text-decoration:none}
}
"""

JS = r"""
(function(){
  var b=document.body;
  document.getElementById('t-ann').addEventListener('click',function(){
    if(!b.classList.contains('no-ann')){b.classList.add('no-ann');this.textContent='注';}
    else{b.classList.remove('no-ann');this.textContent='注';}
  });
  document.getElementById('t-gloss').addEventListener('click',function(){
    if(!b.classList.contains('no-gloss')){b.classList.add('no-gloss');this.textContent='义';}
    else{b.classList.remove('no-gloss');this.textContent='义';}
  });
  document.getElementById('t-ipa').addEventListener('click',function(){
    if(!b.classList.contains('no-ipa')){b.classList.add('no-ipa');this.textContent='音';}
    else{b.classList.remove('no-ipa');this.textContent='音';}
  });
  var sizes=['small','normal','big'], idx=1;
  document.getElementById('t-size').addEventListener('click',function(){
    idx=(idx+1)%3;
    document.documentElement.style.setProperty('--tx', idx===0?'16px':(idx===1?'17.5px':'19.5px'));
    document.documentElement.style.setProperty('--an', idx===0?'10px':(idx===1?'10.5px':'11.5px'));
    this.textContent=idx===0?'小':(idx===1?'中':'大');
  });
  document.getElementById('t-top').addEventListener('click',function(){
    window.scrollTo({top:0,behavior:'smooth'});
  });

  /* ---------------- 语音朗读 ---------------- */
  var synth=window.speechSynthesis, Utter=window.SpeechSynthesisUtterance;
  var CK='ykyy_tts', cfg={on:true,rate:1};
  try{ var sv=localStorage.getItem(CK); if(sv){ var ov=JSON.parse(sv); cfg.on=(ov.on!==false); cfg.rate=parseFloat(ov.rate)||1; } }catch(e){}
  if([1,0.9,0.8,0.75,2].indexOf(cfg.rate)<0) cfg.rate=1;
  function saveCfg(){ try{ localStorage.setItem(CK,JSON.stringify(cfg)); }catch(e){} }

  function allVoices(){ try{ return synth?(synth.getVoices()||[]):[]; }catch(e){ return []; } }
  function scoreV(v){
    var s=0;
    if(/natural/i.test(v.name)) s+=10;
    if(/^en-GB/i.test(v.lang)) s+=4;
    if(/^en-US/i.test(v.lang)) s+=2;
    if(/libby|sonia|ryan|thomas|aria|guy|maisie|hazel|george|natasha/i.test(v.name)) s+=1;
    return s;
  }
  function pickEn(){
    var vs=allVoices().filter(function(v){ return /^en/i.test(v.lang||''); });
    if(!vs.length) return null;
    var loc=vs.filter(function(v){ return v.localService; });
    var pool=loc.length?loc:vs;
    pool.sort(function(x,y){ return scoreV(y)-scoreV(x); });
    return pool[0];
  }
  var VOICE=null;
  function refreshVoice(){ VOICE=pickEn(); }
  refreshVoice();
  try{ synth.onvoiceschanged=refreshVoice; }catch(e){}

  var curWds=[], curBtn=null;
  function clearHi(){
    for(var i=0;i<curWds.length;i++){
      curWds[i].classList.remove('reading');
      curWds[i].style.background='';
      curWds[i].style.borderRadius='';
      curWds[i].style.boxShadow='';
    }
    if(curBtn) curBtn.classList.remove('on');
    curWds=[]; curBtn=null;
  }
  function stopSpeak(){ try{ synth.cancel(); }catch(e){} clearHi(); }

  function markReading(wds,btn){
    curWds=wds||[]; curBtn=btn||null;
    for(var i=0;i<curWds.length;i++){
      curWds[i].classList.add('reading');
      curWds[i].style.background='#f8e7a8';
      curWds[i].style.borderRadius='5px';
      curWds[i].style.boxShadow='0 0 0 1.5px #ddbe66';
    }
    if(curBtn) curBtn.classList.add('on');
  }

  var seq=0;
  function speak(text,wds,btn){
    if(!synth || !Utter) return;
    if(!VOICE) refreshVoice();
    if(!VOICE){
      alert('本机没有可用的英文语音。可在 Windows「设置 → 时间和语言 → 语言」中为 English 安装语音包后重试。');
      return;
    }
    var my=++seq;
    try{ synth.cancel(); }catch(e){}
    clearHi();
    markReading(wds,btn);
    setTimeout(function(){
      if(my!==seq || !text) return;
      var u=new Utter(text);
      u.voice=VOICE; u.lang=VOICE.lang;
      u.rate=cfg.rate; u.pitch=1; u.volume=1;
      u.onend=function(){ if(my===seq) clearHi(); };
      u.onerror=function(){ if(my===seq) clearHi(); };
      synth.speak(u);
    },150);
  }

  function sentWds(btn){
    var out=[], n=btn.nextElementSibling;
    while(n){
      if(n.classList && n.classList.contains('spk')) break;
      if(n.classList && n.classList.contains('wd')) out.push(n);
      n=n.nextElementSibling;
    }
    return out;
  }

  var ENDRE=/[.?!]["'\u201d\u2019)\]]*$/;
  var ABBRRE=/^([A-Za-z]\.)+$|^(Mr|Mrs|Ms|Dr|St|No|vs|etc|Prof|Jr|Sr|Fig)\.$/i;

  function buildSpk(){
    var paras=document.querySelectorAll('.para');
    for(var p=0;p<paras.length;p++){
      var para=paras[p];
      if(para.getAttribute('data-spk')) continue;
      var wds=[];
      for(var i=0;i<para.children.length;i++){
        var el=para.children[i];
        if(el.classList && el.classList.contains('wd')) wds.push(el);
      }
      if(!wds.length) continue;
      para.setAttribute('data-spk','1');
      var groups=[], cur=[];
      for(var k=0;k<wds.length;k++){
        cur.push(wds[k]);
        var t=(wds[k].querySelector('.tx')||wds[k]).textContent.replace(/\s+/g,'');
        var nx=wds[k+1]?((wds[k+1].querySelector('.tx')||wds[k+1]).textContent.replace(/\s+/g,'')):'';
        if(ENDRE.test(t) && !ABBRRE.test(t) && !(nx && /^[a-z]/.test(nx))){ groups.push(cur); cur=[]; }
      }
      if(cur.length) groups.push(cur);
      for(var g=0;g<groups.length;g++){
        var txt=groups[g].map(function(w){
          var q=w.querySelector('.tx');
          return (q||w).textContent.trim();
        }).join(' ').replace(/\s+([,.;:?!])/g,'$1');
        var btn=document.createElement('button');
        btn.type='button'; btn.className='spk';
        btn.title='朗读这一句（再点一次停止）';
        btn.setAttribute('aria-label','朗读这一句');
        btn.setAttribute('data-text',txt);
        btn.innerHTML='<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3z"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v3.5"/></svg>';
        groups[g][0].parentNode.insertBefore(btn,groups[g][0]);
      }
    }
  }
  buildSpk();

  var DBG=/[?&]dbg=1/.test(location.search), dbgEl=null;
  function dbg(msg){
    if(!DBG) return;
    if(!dbgEl){ dbgEl=document.createElement('div'); dbgEl.className='dbgbox'; document.body.appendChild(dbgEl); }
    dbgEl.textContent=msg+'\n'+dbgEl.textContent;
  }

  document.addEventListener('click',function(e){
    var t=e.target;
    var tn=(t.tagName||'')+'.'+((t.className&&t.className.baseVal!==undefined)?t.className.baseVal:(t.className||''));
    var spk=t.closest?t.closest('.spk'):null;
    if(spk){
      e.preventDefault();
      dbg('click '+tn+' → SPK  text="'+(spk.getAttribute('data-text')||'').slice(0,46)+'"');
      if(spk.classList.contains('on')){ stopSpeak(); dbg('  → stop'); return; }
      speak(spk.getAttribute('data-text'),sentWds(spk),spk);
      return;
    }
    var wd=t.closest?t.closest('.wd'):null;
    if(!wd){ dbg('click '+tn+' → 未命中 .wd / .spk'); return; }
    if(wd.classList.contains('wd-pc')){ dbg('click '+tn+' → wd-pc 跳过'); return; }
    var tx=wd.querySelector('.tx');
    if(!tx){ dbg('click '+tn+' → 无 .tx'); return; }
    var w=tx.textContent.trim().replace(/^[^0-9A-Za-z\u00c0-\u024f'\-]+/,'').replace(/[^0-9A-Za-z\u00c0-\u024f'\-]+$/,'');
    if(!w){ dbg('click → 词为空'); return; }
    if(!cfg.on){ dbg('click '+tn+' → 词 "'+w+'" 但朗读开关已关'); return; }
    dbg('click '+tn+' → 单词 "'+w+'"（VOICE='+(VOICE?VOICE.name:'null')+'）');
    speak(w,[wd],null);
  });

  var spb=document.getElementById('t-speak');
  if(spb){
    spb.textContent=cfg.on?'读':'静';
    if(!cfg.on) spb.classList.add('off');
    spb.addEventListener('click',function(){
      cfg.on=!cfg.on; saveCfg();
      this.textContent=cfg.on?'读':'静';
      this.classList.toggle('off',!cfg.on);
      if(!cfg.on) stopSpeak();
    });
  }
  var rtb=document.getElementById('t-rate');
  var CYCLE=[1,0.9,0.8,0.75], LP_RATE=2;
  function rateLabel(r){ return r+'x'; }
  function paintRate(){
    if(!rtb) return;
    rtb.textContent=rateLabel(cfg.rate);
    rtb.title='朗读倍速 '+rateLabel(cfg.rate)+'　单击：1x → 0.9x → 0.8x → 0.75x → 1x　长按（0.5 秒）：2x，再单击回 1x';
    rtb.classList.toggle('fast', cfg.rate===LP_RATE);
  }
  function setRate(r){ cfg.rate=r; saveCfg(); paintRate(); }
  function stepRate(){
    if(cfg.rate===LP_RATE){ setRate(1); return; }
    var i=CYCLE.indexOf(cfg.rate);
    setRate(CYCLE[(i<0?0:(i+1))%CYCLE.length]);
  }
  if(rtb){
    paintRate();
    var lpT=null, lpFired=false;
    rtb.addEventListener('pointerdown',function(e){
      e.preventDefault();
      lpFired=false;
      lpT=setTimeout(function(){ lpT=null; lpFired=true; setRate(LP_RATE); }, 500);
    });
    rtb.addEventListener('pointerup',function(e){
      if(lpT){ clearTimeout(lpT); lpT=null; }
      if(lpFired){ lpFired=false; return; }
      stepRate();
    });
    rtb.addEventListener('pointercancel',function(){ if(lpT){ clearTimeout(lpT); lpT=null; } });
    rtb.addEventListener('pointerleave',function(){ if(lpT){ clearTimeout(lpT); lpT=null; } });
  }
})();
"""


def page(title, body, subtitle=""):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{body}
</div>
<div class="toolbar">
  <button id="t-ipa" title="显示/隐藏音标">音</button>
  <button id="t-gloss" title="显示/隐藏词义">义</button>
  <button id="t-ann" title="显示/隐藏全部小字注释">注</button>
  <button id="t-size" title="字号：小/中/大">中</button>
  <button id="t-rate" title="朗读倍速：单击 1x→0.9x→0.8x→0.75x→1x；长按 2x，再单击回 1x">1x</button>
  <button id="t-speak" title="点击单词自动朗读：开 / 关">读</button>
  <button id="t-top" title="回到顶部">↑</button>
</div>
<script>{JS}</script>
</body>
</html>
"""


# ---------------------------------------------------------------- 主构建

CN_NUM = "零一二三四五六七八九十"


def cn(n):
    return CN_NUM[n] if 0 <= n <= 10 else str(n)


def build_doc(key, words_path, lesson_path):
    meta = {}
    paras_words = parse_words(words_path)
    quiz = parse_quiz(Path(words_path).with_name(Path(words_path).name.replace(".words.txt", ".quiz.txt")))

    lesson = {}
    if Path(lesson_path).exists():
        txt = read(lesson_path)
        try:
            lesson = json.loads(txt)
        except json.JSONDecodeError as e:
            raise SystemExit(f"lesson JSON 解析失败 {Path(lesson_path).name}: {e}")
    else:
        print(f"  ! 缺少 {Path(lesson_path).name}，仅输出文章部分")

    meta = lesson.get("meta", {})
    notes = {p["n"]: p for p in lesson.get("para_notes", [])}

    # ---- 页头
    part = norm_part(meta.get("part"))
    q_unit = {"A": "题", "cloze": "空", "B": "题", "C": "句"}.get(part, "题")
    part_cn = {"A": "Part A", "cloze": "Use of English", "B": "Part B",
               "C": "Part C"}.get(part, str(meta.get("part") or "Part A"))
    _paper = f"{meta.get('year', '2021')} {meta.get('paper', '英语（一）')}"
    title = {
        "A": f"{_paper} · 阅读 Text {meta.get('no', key)} 逐词精读",
        "cloze": f"{_paper} · 完形填空逐词精读",
        "B": f"{_paper} · 新题型 Part B 逐词精读",
        "C": f"{_paper} · 翻译 Part C 逐句精读",
    }.get(part, f"{_paper} · 逐词精读")
    badges = [
        f"<span class='badge'>{esc(meta.get('paper','英语（一）'))} · {esc(part_cn)}</span>",
        f"<span class='badge'>第 {esc(meta.get('qs',''))} {q_unit}</span>",
        f"<span class='badge b2'>约 {esc(meta.get('words',''))} 词</span>",
        f"<span class='badge b3'>难度：{esc(meta.get('difficulty',''))}</span>",
    ]
    for tg in meta.get("tags", []):
        badges.append(f"<span class='badge'>{esc(tg)}</span>")

    # 题型：A=阅读理解 / cloze=完形填空 / B=新题型 / C=翻译
    unit = {"A": "段", "cloze": "段", "B": "段", "C": "句"}.get(part, "段")
    unit_en = {"A": "PARAGRAPH", "cloze": "PARAGRAPH",
               "B": "PARAGRAPH", "C": "SENTENCE"}.get(part, "PARAGRAPH")
    h1_text = {
        "A": f"阅读理解 Text {esc(meta.get('no', key))}",
        "cloze": "完形填空 Use of English",
        "B": "新题型 Part B",
        "C": "翻译 Part C",
    }.get(part, f"阅读理解 Text {esc(meta.get('no', key))}")
    q_unit = {"A": "题", "cloze": "空", "B": "题", "C": "句"}.get(part, "题")

    toc = []
    ids = []
    for p in paras_words:
        toc.append(f"<a href='#p{p['n']}'>第 {cn(p['n'])} {unit}</a>")
        ids.append(f"p{p['n']}")
    toc.append(f"<a href='#qs'>真题 {len(lesson.get('questions', [])) or 5} 题</a>")
    toc.append(f"<a href='#vs'>变体 {len(lesson.get('variants', [])) or 6} 题</a>")
    if lesson.get("glossary"):
        toc.append("<a href='#gl'>核心词汇</a>")

    body = [f"""<header class="hd">
  <div class="kicker">{esc(meta.get('source','2021 年全国硕士研究生招生考试 英语（一）阅读理解'))}</div>
  <h1>{h1_text}</h1>
  <div class="sub">{esc(meta.get('theme',''))}</div>
  <div class="chips">{''.join(badges)}</div>
  <nav class="toc">{''.join(toc)}</nav>
</header>"""]

    # ---- Part B 排序/七选五/匹配：把段首 (41)…(45) 标记转成段头徽章，正文按正确顺序读成一篇
    part_b_ans = {}
    part_b_fill = True
    if str(meta.get("part") or "").strip() == "B":
        _pbq = lesson.get("questions", [])
        for q in _pbq:
            k = str(q.get("no", "")).strip()
            a = str(q.get("answer") or "").strip()
            if k and a:
                part_b_ans[k] = a
        # 题干写 “Paragraph (41)” 的是填空/排序题；写 “(41) Hannah” 的是人物观点匹配题
        part_b_fill = "Paragraph" in " ".join(str(q.get("stem") or "") for q in _pbq)

    # ---- 文章主体
    for p in paras_words:
        n = p["n"]
        note = notes.get(n, {})
        trans = note.get("trans", "")
        gram = note.get("grammar", [])
        toks = p["tokens"]
        slot = ""
        if part_b_ans and toks:
            m = re.fullmatch(r"\((\d+)\)", (toks[0].get("w") or "").strip())
            if m and m.group(1) in part_b_ans:
                slot = m.group(1)
                toks = toks[1:]
        badge = ""
        if slot:
            _lab = "空" if part_b_fill else "题"
            _tail = "原选项" if part_b_fill else "答案"
            badge = (f'<span class="slotbadge">第 {slot} {_lab} · {_tail} '
                     f'{part_b_ans[slot]}</span>')
        if toks:
            para_html = render_para(toks)
        else:
            para_html = f'<div class="para-empty">本空正文待补（原选项 {part_b_ans.get(slot, "?")}）</div>'
        body.append(f"""<section class="sec" id="p{n}">
  <h2 class="sec-title"><span class="no">{n}</span>第 {cn(n)} {unit}<span class="en">{unit_en} {n}</span>{badge}</h2>
  <div class="para">{para_html}</div>
  {f'<div class="trans"><b>段意</b>{md_lite(trans)}</div>' if trans else ''}
  {render_grammar(gram)}
</section>""")
        if not gram:
            print(f"  ! 第 {n} 段缺少语法点")

    # ---- 真题
    qs = lesson.get("questions", [])
    body.append('<section class="sec" id="qs">')
    body.append(f'<h2 class="sec-title"><span class="no">Q</span>真题原题 · {len(qs)} {q_unit}'
                '<span class="en">ORIGINAL QUESTIONS</span></h2>')
    if lesson.get("summary", {}).get("main_idea"):
        body.append(f'<div class="trans" style="margin-top:0"><b>全文主旨</b>{md_lite(lesson["summary"]["main_idea"])}</div>')
    for q in qs:
        body.append(render_question(q, quiz=quiz))
    body.append('</section>')

    # ---- 变体
    vs = lesson.get("variants", [])
    if vs:
        body.append('<section class="sec" id="vs">')
        body.append(f'<h2 class="sec-title"><span class="no">V</span>同类型变体题 · {len(vs)} 题'
                    '<span class="en">VARIANTS</span></h2>')
        for i, q in enumerate(vs, 1):
            q2 = dict(q)
            q2["no"] = f"V{i}"
            q2["tag"] = q.get("tag", "")
            body.append(render_question(q2, is_variant=True, quiz=quiz))
        body.append('</section>')

    # ---- 词汇表
    gl = lesson.get("glossary", [])
    if gl:
        items = []
        for g in gl:
            items.append(
                f'<div class="gi"><div><span class="gw">{esc(g.get("w",""))}</span> '
                f'<span class="gi2">{esc(g.get("ipa",""))}</span> '
                f'<span class="gi2" style="color:#7a6338">{esc(g.get("pos",""))}</span></div>'
                f'<div class="gc">{esc(g.get("cn",""))}</div>'
                + (f'<div class="gn">{md_lite(g.get("note",""))}</div>' if g.get("note") else "")
                + '</div>'
            )
        body.append(f'<section class="sec" id="gl"><h2 class="sec-title">'
                    f'<span class="no">词</span>核心词汇与搭配<span class="en">GLOSSARY</span></h2>'
                    f'<div class="gloss">{"".join(items)}</div></section>')

    # ---- 结构简析
    sc = lesson.get("summary", {}).get("structure", [])
    if sc:
        lis = "".join(f"<li><b>{esc(x.get('h',''))}</b>{('：' + esc(x.get('b',''))) if x.get('b') else ''}</li>" for x in sc)
        body.append(f'<section class="sec"><h2 class="sec-title"><span class="no">构</span>'
                    f'文章结构简析<span class="en">STRUCTURE</span></h2>'
                    f'<ul class="outline">{lis}</ul></section>')

    body.append(f"""<footer class="ft">
  <p>本文档由本地生成器 <code>build.py</code> 依真题原文排版，逐词音标与词义为学习目的的注解，非考试官方材料。原题文字以考试院真题为准。</p>
  <p>操作：右下角「音 / 义 / 注」可分别隐藏音标、词义、全部注释，用于自测；「中」切换字号；「↑」回到顶部。打印或导出 PDF 时自动适配 A4。</p>
  <p style="margin-top:8px">生成时间：{datetime.date.today().isoformat()}</p>
</footer>""")

    out = page(title, "\n".join(body))
    DOCS.mkdir(parents=True, exist_ok=True)
    # 文件名统一为 英语一2021_阅读Text{N}.html，忽略 lesson.json 里的自定义名，
    # 保证四篇在资源管理器与 index.html 中排序一致、引用可预测。
    _part = norm_part(meta.get("part"))
    if _part == "cloze":
        fname = f"英语一{YEAR}_完形填空.html"
    elif _part == "B":
        fname = f"英语一{YEAR}_新题型PartB.html"
    elif _part == "C":
        fname = f"英语一{YEAR}_翻译PartC.html"
    else:
        fname = f"英语一{YEAR}_阅读Text{meta.get('no', key)}.html"
    (DOCS / fname).write_text(out, encoding="utf-8")
    return fname, paras_words, lesson


# ---------------------------------------------------------------- 校验

def check(words_path, lesson_path):
    ok = True
    paras = parse_words(words_path)
    total = 0
    for p in paras:
        total += len([t for t in p["tokens"] if t["kind"] == "w"])
        for t in p["tokens"]:
            if t["kind"] != "w":
                continue
            # 完形 / 新题型的空位占位 token 形如 (1) (2) ... (20)，本身没有读音，
            # 音标写 `_` 或 `/—/` 都合法，跳过音标格式校验。
            is_blank = bool(re.fullmatch(r"\(\d+\)", t["w"]))
            if not is_blank and (len(t["ipa"]) < 2 or not t["ipa"].startswith("/") or not t["ipa"].endswith("/")):
                print(f"  ! 音标格式可疑：{t['w']} -> {t['ipa']!r}")
                ok = False
            cn_part = re.sub(r"^[a-z]+\.\s*", "", t["gl"])
            cn_part = re.sub(r"（[^）]*）|\([^)]*\)", "", cn_part)
            if len(cn_part) > 11:
                print(f"  ! 释义过长（{len(cn_part)} 字）：{t['w']} -> {t['gl']!r}")
                ok = False
            if not t["gl"]:
                print(f"  ! 缺释义：{t['w']}")
                ok = False
    if Path(lesson_path).exists():
        try:
            les = json.loads(read(lesson_path))
        except json.JSONDecodeError as e:
            print(f"  ! JSON 错误：{e}")
            return False, total
        pn = {p["n"] for p in paras}
        for x in les.get("para_notes", []):
            if x["n"] not in pn:
                print(f"  ! para_notes 段号 {x['n']} 在 words 中不存在")
                ok = False
            if not x.get("grammar"):
                print(f"  ! 第 {x['n']} 段无语法点")
                ok = False
        # 题型决定题数与选项字母：A=阅读（5 题 A-D）、cloze=完形（20 题 A-D）、
        # B=新题型（5 题 A-G）、C=翻译（5 题，无选项，answer 存参考译文）
        meta = les.get("meta", {})
        part = norm_part(meta.get("part"))
        opt_letters = {"A": "ABCD", "cloze": "ABCD", "B": "ABCDEFG", "C": ""}.get(part, "ABCD")
        want_q = {"A": 5, "cloze": 20, "B": 5, "C": 5}.get(part, 5)
        # 新题型选项数逐年不同（A–G / A–H），以 lesson.json 首题的 options 为准
        if part == "B":
            _qs = les.get("questions") or []
            if _qs and _qs[0].get("options"):
                opt_letters = "".join(sorted(_qs[0]["options"]))

        for q in les.get("questions", []):
            if opt_letters:
                if q.get("answer") not in tuple(opt_letters):
                    print(f"  ! 题 {q.get('no')} 答案非法：{q.get('answer')}")
                    ok = False
            elif not (q.get("answer") or "").strip():
                print(f"  ! 题 {q.get('no')} 缺参考译文（answer 字段）")
                ok = False
            if len(q.get("blocks", [])) < 4:
                print(f"  ! 题 {q.get('no')} 解析块少于 4 个")
                ok = False
        if len(les.get("questions", [])) != want_q:
            print(f"  ! 真题数量 {len(les.get('questions', []))}（应为 {want_q}）")
            ok = False
        if len(les.get("variants", [])) != 6:
            print(f"  ! 变体数量 {len(les.get('variants', []))}（应为 6）")
            ok = False
        # 题干与选项的逐词标注（data/textN.quiz.txt）
        qp = Path(words_path).with_name(Path(words_path).name.replace(".words.txt", ".quiz.txt"))
        if not qp.exists():
            print(f"  ! 缺少 {qp.name}（题干与选项的逐词标注 + 中文整句译文）")
            ok = False
        else:
            quiz = parse_quiz(qp)
            allq = list(les.get("questions", []))
            for i, v in enumerate(les.get("variants", []), 1):
                v2 = dict(v)
                v2["no"] = f"V{i}"
                allq.append(v2)
            for q in allq:
                qk = str(q.get("no", ""))
                need = [f"stem:{qk}"] + [f"opt:{qk}:{x}" for x in opt_letters]
                for blk in need:
                    d = quiz.get(blk) or quiz.get(blk.lower())
                    if not d or not d.get("tokens"):
                        print(f"  ! 题 {qk} 缺少逐词块 @{blk}")
                        ok = False
                    elif not d.get("cn"):
                        print(f"  ! 题 {qk} 的 @{blk} 缺少中文整句译文（~ 开头一行）")
                        ok = False
    else:
        print(f"  ! 缺少 {Path(lesson_path).name}")
        ok = False
    return ok, total


def main():
    only_check = "--check" in sys.argv
    # 位置参数：不给 → 全部年份；`2021` → 该年全部；
    # `2021 2` → 该年 Text 2；`2` → 各年份的 Text 2
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    year_filter = text_filter = None
    if pos:
        if len(pos[0]) == 4 and pos[0].isdigit():
            year_filter = pos[0]
            if len(pos) > 1:
                text_filter = pos[1].lower().replace("text", "").strip()
        else:
            text_filter = pos[0].lower().replace("text", "").strip()

    targets = [year_filter] if year_filter else year_dirs()
    if not targets:
        raise SystemExit("没找到年份目录：应在 英语一/ 下建 2021 这样的四位数字子目录")

    total = 0
    for y in targets:
        set_year(y)
        texts = sorted(DATA.glob("*.words.txt")) if DATA.exists() else []
        if not texts:
            print(f"[{YEAR}] data/ 下暂无 *.words.txt，跳过")
            continue

        rows = []
        for wp in texts:
            key = wp.name.split(".")[0].replace("text", "")
            if text_filter and key != text_filter:
                continue
            lp = wp.with_name(wp.name.replace(".words.txt", ".lesson.json"))
            print(f"[{YEAR} · {key}]")
            ok, nwords = check(wp, lp)
            print(f"  词数 {nwords} / 校验 {'通过' if ok else '有问题'}")
            if only_check:
                continue
            if not ok:
                print("  → 跳过生成（先修正上面的问题）")
                continue
            fname, paras, les = build_doc(key, wp, lp)
            lm = les.get("meta", {})
            _p = norm_part(lm.get("part"))
            rows.append(({"cloze": 0, "A": 1, "B": 2, "C": 3}.get(_p, 9),
                         str(lm.get("no", key)), lm.get("theme", ""),
                         lm.get("qs", ""), fname, _p))
            print(f"  → {YEAR}/docs/{fname}")

        if only_check or not rows or text_filter:
            continue

        # ---- 总目录（按试卷顺序：完形 → 阅读 Text1-4 → 新题型 → 翻译）
        rows.sort(key=lambda r: (r[0], str(r[1])))
        lis = []
        LBL = {"cloze": ("完形填空", "Use of English"),
               "B": ("新题型", "Part B"),
               "C": ("翻译", "Part C")}
        for order, no, theme, qs, fname, part in rows:
            if part in LBL:
                bk, sub = LBL[part]
                lis.append(f'<li><a href="{esc(fname)}"><b>{esc(bk)}</b>'
                           f'<span class="tt">{esc(theme)}</span>'
                           f'<span class="tq">{esc(sub)}</span></a></li>')
            else:
                lis.append(f'<li><a href="{esc(fname)}"><b>Text {esc(no)}</b>'
                           f'<span class="tt">{esc(theme)}</span>'
                           f'<span class="tq">第 {esc(qs)} 题</span></a></li>')
        idx_css = """
    .ix{max-width:760px;margin:60px auto;padding:0 20px}
    h1{font-family:Georgia,serif;font-size:27px;font-weight:600;color:#1f2226;margin:0 0 6px}
    .ix p.sub{color:#6f6757;font-size:14.5px;margin:0 0 26px}
    ul{list-style:none;padding:0;margin:0}
    li{margin:12px 0}
    a{display:block;text-decoration:none;background:#fff;border:1px solid #e6dfd2;
      border-radius:14px;padding:16px 20px;box-shadow:0 1px 10px rgba(122,101,70,.05);
      transition:.15s}
    a:hover{background:#fffdf6;transform:translateY(-1px);box-shadow:0 4px 16px rgba(122,101,70,.10)}
    a b{font-family:Georgia,serif;font-size:18px;color:#b8452d;margin-right:12px}
    a .tt{font-size:15px;color:#2e3239}
    a .tq{float:right;font-size:12.5px;color:#8a7d63;background:#f2ecdf;padding:2px 10px;border-radius:10px}
        """
        idx = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{YEAR} 英语（一）阅读精读 · 目录</title><style>{idx_css}</style></head><body>
<div class="ix"><h1>{YEAR} 英语（一）阅读理解 · 逐词精读</h1>
<p class="sub">Part A 四篇 · 逐词音标与语境词义 · 逐段语法 · 真题解析 · 同类变体（点击进入）</p>
<ul>{''.join(lis)}</ul>
<p style="margin-top:34px;font-size:12.5px;color:#8a8272">
四篇均可离线打开；右下角可切换注释显示、字号，可直接打印为 A4。</p>
</div></body></html>"""
        (DOCS / "index.html").write_text(idx, encoding="utf-8")
        print(f"→ {YEAR}/docs/index.html（{len(rows)} 篇）")
        total += len(rows)

    if not only_check and total:
        print(f"\n全部完成：共 {total} 篇")


if __name__ == "__main__":
    main()
