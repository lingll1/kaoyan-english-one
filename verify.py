#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原文一致性校验：把 data/textN.words.txt 的 token 重新拼回句子，与 SOURCE.md 原文比对。
用来抓「漏词、多词、拼写走样、漏标点」。

用法：
  python verify.py         # 检查全部
  python verify.py 2       # 只查 Text 2
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

BASE = Path(__file__).resolve().parent


def year_dirs():
    if not BASE.is_dir():
        return []
    return sorted(p.name for p in BASE.iterdir()
                  if p.is_dir() and len(p.name) == 4 and p.name.isdigit())


def norm(s):
    s = (s.replace("\u2019", "'").replace("\u2018", "'")
          .replace("\u201c", '"').replace("\u201d", '"')
          .replace("\u2014", "-").replace("\u2013", "-")
          .replace("\u00a0", " "))
    s = re.sub(r"\s+", "", s)
    return s.lower()


def parse_source(path):
    """-> {(text_no, para_no): sentence}"""
    out, cur_t, cur_p = {}, None, None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = re.match(r"^##\s*Text\s*(\d+)", line)
        if m:
            cur_t, cur_p = int(m.group(1)), None
            continue
        m = re.match(r"^###\s*第\s*(\d+)\s*段", line)
        if m and cur_t is not None:
            cur_p = (cur_t, int(m.group(1)))
            out.setdefault(cur_p, [])
            continue
        if line.startswith("###") or line.startswith("##"):
            cur_p = None
            continue
        if cur_p and line.strip() and not line.startswith(">"):
            out[cur_p].append(line.strip())
    return {k: " ".join(v) for k, v in out.items()}


def parse_words(path):
    paras, cur = [], None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            cur = {"n": int(line[1:]), "tokens": []}
            paras.append(cur)
            continue
        if cur is None:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            cur["tokens"].append(parts[0].strip())
    return paras


def check_year(year, filt):
    """校验某一年：words.txt 拼回的句子 vs 该年 SOURCE.md。返回问题数。"""
    root = BASE / str(year)
    data = root / "data"
    src_p = root / "SOURCE.md"
    if not src_p.exists():
        print(f"[{year}] 缺少 SOURCE.md，跳过")
        return 0
    if not data.is_dir():
        print(f"[{year}] 缺少 data/，跳过")
        return 0

    src = parse_source(src_p)
    bad = 0
    files = sorted(data.glob("text*.words.txt"))
    if not files:
        print(f"[{year}] data/ 下没有 text*.words.txt，跳过")
        return 0
    for wp in files:
        n = wp.name.split(".")[0].replace("text", "")
        if filt and n != filt:
            continue
        paras = parse_words(wp)
        print(f"[{year} · Text {n}] 共 {len(paras)} 段")
        for p in paras:
            key = (int(n), p["n"])
            if key not in src:
                print(f"  ! 第 {p['n']} 段在 SOURCE.md 中找不到")
                bad += 1
                continue
            mine = norm("".join(p["tokens"]))
            ref = norm(src[key])
            if mine == ref:
                print(f"  第 {p['n']} 段  ✓ 一致（{len(p['tokens'])} 个 token）")
                continue
            bad += 1
            i = 0
            while i < min(len(mine), len(ref)) and mine[i] == ref[i]:
                i += 1
            print(f"  ✗ 第 {p['n']} 段 与原文不符（首个差异在第 {i} 字符）")
            print(f"     你的：…{mine[max(0, i - 30):i + 45]}…")
            print(f"     原文：…{ref[max(0, i - 30):i + 45]}…")
        # 段数比对
        ref_paras = sorted(k[1] for k in src if k[0] == int(n))
        mine_paras = sorted(p["n"] for p in paras)
        if ref_paras and mine_paras != ref_paras:
            print(f"  ! 段号不一致：你的 {mine_paras}，原文 {ref_paras}")
            bad += 1
    return bad


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    year_filter = text_filter = None
    if pos:
        if len(pos[0]) == 4 and pos[0].isdigit():
            year_filter = pos[0]
            if len(pos) > 1:
                text_filter = pos[1].lower().replace("text", "").strip()
        else:
            text_filter = pos[0].lower().replace("text", "").strip()

    years = [year_filter] if year_filter else year_dirs()
    if not years:
        raise SystemExit("没找到年份目录：应在 英语一/ 下建 2021 这样的四位数字子目录")

    bad = 0
    for y in years:
        bad += check_year(y, text_filter)

    print("")
    print("全部一致。" if bad == 0 else f"发现 {bad} 处问题，请修正后重跑。")


if __name__ == "__main__":
    main()
