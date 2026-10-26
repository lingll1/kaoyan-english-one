#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 lazynote 整卷 docx 转换成 SOURCE.md / SOURCE-others.md 骨架。

用法：
    python _docx2source.py 2025
（需先把 docx 放到 <年份>/<年份>_full.docx）

产物：
    <年份>/SOURCE.md          阅读 Text 1–4（原文分段 + 题干 + A–D 选项，答案留 `**答案 ?**`）
    <年份>/SOURCE-others.md   完形 / 新题型 Part B / 翻译 Part C（同上，译文留 `**参考译文 ?**`）

答案需另行核定后替换占位符。
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

import docx

BASE = Path(__file__).resolve().parent


def safe_write(path, lines, placeholders):
    """拒绝覆盖「已填写过答案」的定稿文件，除非显式传 --force。

    2023 的 SOURCE.md / SOURCE-others.md 是人工定稿（含答案与核验说明），
    本脚本只能生成未填答案的骨架，直接覆盖会丢掉全部答案与说明。
    """
    if path.exists() and "--force" not in sys.argv:
        old = path.read_text(encoding="utf-8")
        has_ph = any(ph in old for ph in placeholders)
        if not has_ph and "**答案" in old:
            raise SystemExit(
                f"拒绝覆盖 {path.name}：该文件已填写过答案（不含占位符）。\n"
                f"  {path}\n"
                f"如确需重新生成骨架，请先备份，或加 --force。"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else ""
    if not year:
        raise SystemExit("用法：python _docx2source.py <年份>")
    root = BASE / year
    docx_p = root / f"{year}_full.docx"
    if not docx_p.exists():
        raise SystemExit(f"缺少 {docx_p}")

    d = docx.Document(str(docx_p))
    ps = [p.text.strip() for p in d.paragraphs]
    ps = [p for p in ps if p]

    idx = {}
    for i, p in enumerate(ps):
        m = re.fullmatch(r"Text ([1-4])", p)
        if m and f"T{m.group(1)}" not in idx:
            idx[f"T{m.group(1)}"] = i
        elif re.fullmatch(r"Part B", p) and "B" not in idx:
            idx["B"] = i
        elif re.fullmatch(r"Part C", p) and "C" not in idx:
            idx["C"] = i
        elif p.startswith("Section III") and "W" not in idx:
            idx["W"] = i
        elif p.startswith("Section I ") and "CL" not in idx:
            idx["CL"] = i

    miss = [k for k in ("T1", "T2", "T3", "T4", "B", "C", "CL") if k not in idx]
    if miss:
        raise SystemExit(f"无法定位区块：{miss}（已找到 {sorted(idx)}）")

    def split_q(block):
        """-> [(no, stem, [opt...])]"""
        qs, cur = [], None
        for p in block:
            m = re.match(r"^(\d+)\.\s*(.*)$", p)
            mo = re.match(r"^\[\s*([A-H])\s*\]\s*(.*)$", p)
            if m and not mo:
                if cur:
                    qs.append(cur)
                cur = [m.group(1), m.group(2).strip(), []]
            elif mo and cur is not None:
                cur[2].append(f"{mo.group(1)} {mo.group(2).strip()}")
            elif cur is not None and not cur[2]:
                cur[1] = (cur[1] + " " + p).strip()
        if cur:
            qs.append(cur)
        return qs

    def body_of(block):
        """题干之前的正文段落"""
        out = []
        for p in block:
            if re.match(r"^\d+\.", p) or re.match(r"^\[\s*[A-H]\s*\]", p):
                break
            if p.startswith("Directions:") or p.startswith("Read the following"):
                continue
            out.append(p)
        return out

    # ---------- SOURCE.md ----------
    lines = [f"# {year} 年全国硕士研究生招生考试 英语（一）阅读理解 Text 1–4", "",
             f"> 文本来源：懒笔记整卷 Word（`{year}_full.docx`）逐段提取；答案待核。", ""]
    for n in (1, 2, 3, 4):
        a = idx[f"T{n}"]
        b = idx[f"T{n + 1}"] if n < 4 else idx["B"]
        block = ps[a + 1:b]
        paras = body_of(block)
        qs = split_q(block)
        lines.append(f"## Text {n}")
        lines.append("")
        for k, t in enumerate(paras, 1):
            lines += [f"### 第 {k} 段", "", t, ""]
        lines += ["### 题目", ""]
        for no, stem, opts in qs:
            lines.append(f"{no}. {stem}")
            lines.append("")
            for o in opts:
                lines.append(o)
            lines += ["", "**答案 ?**", ""]
    safe_write(root / "SOURCE.md", lines, ["**答案 ?**"])
    print(f"SOURCE.md  {len(lines)} 行")

    # ---------- SOURCE-others.md ----------
    # 完形：Section I 之后到第一个 `1.` 之前
    cl_start = idx["CL"] + 1
    cl_end = cl_start
    while cl_end < len(ps) and not re.match(r"^\d+\.$", ps[cl_end]):
        cl_end += 1
    cl_body = [p for p in ps[cl_start:cl_end]
               if not p.startswith("Directions:") and not p.startswith("Read the following")
               and not p.startswith("Section") and not p.startswith("Part ")]
    cl_qs = split_q(ps[cl_end:idx["T1"]])

    o = [f"# {year} 英语（一）其他题型原文", "",
         f"> 完形、新题型、翻译均来自同一 Word 整卷；答案待核。", "",
         "## 一、完形填空 Use of English", ""]
    for k, t in enumerate(cl_body, 1):
        o += [f"### 第 {k} 段", "", t, ""]
    o += ["### 题目", ""]
    for no, stem, opts in cl_qs:
        o += [f"{no}.", ""]
        o += opts
        o += ["", "**答案 ?**", ""]

    # Part B
    pb = ps[idx["B"] + 1:idx["C"]]
    cands = [p for p in pb if re.match(r"^\[\s*[A-H]\s*\]", p)]
    chain = [p for p in pb if "(41)" in p]
    o += ["## 二、新题型 Part B", ""]
    if cands:
        o += ["### 候选段落", ""]
        for p in cands:
            o += [p, ""]
    if chain:
        o += ["### 已知顺序", "", chain[0], ""]
    o += ["### 题目", ""]
    letters = "/".join(c[3] for c in cands) if cands else "A–H"
    for no in range(41, 46):
        o += [f"{no}. 请从 {letters} 中选择第 {no} 空对应的段落。", "", "**答案 ?**", ""]

    # Part C
    pc = [p for p in ps[idx["C"] + 1:idx["W"]]
          if not p.startswith("Directions:") and not p.startswith("Read the following")]
    o += ["## 三、翻译 Part C", "", "### 原文（划线句以 (46)–(50) 标出）", ""]
    for p in pc:
        o += [p, ""]

    # 抽出划线句：从 (N) 起，到一个句末标点 + 空格 + 大写 或段末为止
    sents = {}
    for p in pc:
        for m in re.finditer(r"\((\d+)\)\s*", p):
            no = int(m.group(1))
            tail = p[m.end():]
            end = len(tail)
            for mm in re.finditer(r"\.\s+(?=[A-Z(])", tail):
                end = mm.end()
                break
            sents[no] = tail[:end].strip()
    o += ["### 题目（仅划线句）", ""]
    for no in range(46, 51):
        o += [f"{no}. {sents.get(no, '未获取：docx 中未找到该划线句标记')}", "",
              "**参考译文 ?**", ""]
    (root / "SOURCE-others.md").write_text("\n".join(o), encoding="utf-8")
    print(f"SOURCE-others.md  {len(o)} 行；完形题 {len(cl_qs)}；PartB 候选 {len(cands)}；划线句 {sorted(sents)}")


if __name__ == "__main__":
    main()
