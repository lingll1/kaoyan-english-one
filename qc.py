# -*- coding: utf-8 -*-
"""qc.py —— 题目区数据自检（不依赖 build.py）。

检查三件事：
1. lesson.json 的每道真题/变体，quiz.txt 里都有对应的 @stem 与 @opt:A..D 块；
2. 每块都有 `~` 中文整句译文；
3. 把 quiz 块的词序列规范化后，与 lesson.json 的 stem/options 词序列比对，
   抓「漏词 / 多词 / 拼错」（只比字母序列，忽略标点与空白差异）。

用法：python qc.py [N]   不带 N 检查全部四篇。
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
DATA = BASE / "data"          # 由 set_year() 切换


def set_year(y):
    global YEAR, DATA
    YEAR = str(y)
    DATA = BASE / YEAR / "data"
    return DATA


def year_dirs():
    if not BASE.is_dir():
        return []
    return sorted(p.name for p in BASE.iterdir()
                  if p.is_dir() and len(p.name) == 4 and p.name.isdigit())

PUNCT = set(".,;:!?\"'“”‘’()[]{}—–-…·&/\\|*+*=<>@#$%^~`")


def parse_quiz(path):
    """返回 {块名: {"tokens": [词...], "cn": str}}"""
    blocks = {}
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("@"):
            cur = {"tokens": [], "cn": ""}
            blocks[line[1:].strip()] = cur
            continue
        if cur is None:
            continue
        if line.startswith("~"):
            cur["cn"] = line[1:].strip()
            continue
        w = line.split("|")[0].strip()
        if w:
            cur["tokens"].append(w)
    return blocks


def norm(s):
    """只留字母与数字，小写；引号统一。用于词序列比对。"""
    s = (s.replace("’", "'").replace("‘", "'")
           .replace("“", '"').replace("”", '"'))
    return re.sub(r"[^0-9a-z]+", "", s.lower())


def norm_tokens(tokens):
    return re.sub(r"[^0-9a-z]+", "", "".join(tokens).lower())


def check(n):
    tag = f"text{n}" if str(n).isdigit() else str(n)
    words_p = DATA / f"{tag}.quiz.txt"
    lesson_p = DATA / f"{tag}.lesson.json"
    if not words_p.exists():
        return [f"{tag}: 缺少 {words_p.name}"]
    if not lesson_p.exists():
        return [f"{tag}: 缺少 {lesson_p.name}"]

    quiz = parse_quiz(words_p)
    d = json.loads(lesson_p.read_text(encoding="utf-8"))
    errs = []
    part = str((d.get("meta") or {}).get("part") or "A").strip()
    nopt = {"A": 4, "cloze": 4, "B": 7, "C": 0}.get(part, 4)

    items = [("真题", q, str(q.get("no", ""))) for q in d.get("questions", [])]
    # 与 build.py 一致：变体渲染时忽略 lesson.json 里的 no，强制编号 V1..V6
    items += [("变体", v, f"V{i}") for i, v in enumerate(d.get("variants", []), 1)]

    for kind, q, qk in items:
        want = [(f"stem:{qk}", q.get("stem", ""))]
        for k, val in (q.get("options") or {}).items():
            want.append((f"opt:{qk}:{k}", val))

        for key, text in want:
            blk = quiz.get(key)
            if blk is None:
                errs.append(f"{tag} {kind} {qk}: 缺少块 @{key}")
                continue
            if not blk["cn"]:
                errs.append(f"{tag} {kind} {qk}: @{key} 缺少 ~ 中文译文")
            # 翻译题（part=C）的真题 stem 按设计为空串（原文在 paras 里），
            # quiz.txt 里的 @stem 块装的是该句直译版逐词，故只校验块存在与译文，不比对词序列。
            if not str(text).strip():
                continue
            a, b = norm_tokens(blk["tokens"]), norm(text)
            if a != b:
                # 找首个差异位置，便于定位
                i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]),
                         min(len(a), len(b)))
                errs.append(
                    f"{tag} {kind} {qk}: @{key} 词序列不一致\n"
                    f"    quiz  : ...{a[max(0, i-18):i+18]}\n"
                    f"    lesson: ...{b[max(0, i-18):i+18]}"
                )
    # 反向：quiz 里多余块
    want_keys = set()
    for _, q, qk in items:
        want_keys.add(f"stem:{qk}")
        for k in (q.get("options") or {}):
            want_keys.add(f"opt:{qk}:{k}")
    for extra in sorted(set(quiz) - want_keys):
        errs.append(f"{tag}: quiz.txt 有多余块 @{extra}（lesson.json 里没有对应题目/选项）")

    total = sum(1 + len(q.get("options") or {}) for _, q, _ in items)
    print(f"[{tag}] 题目 {len(items)} 道（{len(d.get('questions',[]))} 真题 + "
          f"{len(d.get('variants',[]))} 变体）/ 应有块 {total} / quiz 实际块 {len(quiz)}")
    if not errs:
        print("  全部对应正确。")
    return errs


def _key(a):
    """'1'/'2' → 1；'cloze'/'partb'/'trans' → 原字符串"""
    return int(a) if a.isdigit() else a


def _auto_targets():
    """未指定篇目时，自动发现 DATA 下所有 *.lesson.json 的 key"""
    keys = []
    for p in sorted(DATA.glob("*.lesson.json")):
        k = p.name[: -len(".lesson.json")]
        keys.append(_key(k[4:]) if k.startswith("text") and k[4:].isdigit() else k)
    order = {"cloze": 0, "partb": 5, "trans": 6}
    return sorted(keys, key=lambda k: (order.get(k, 1), str(k)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    year_filter = text_filter = None
    if pos:
        if len(pos[0]) == 4 and pos[0].isdigit():
            year_filter = pos[0]
            if len(pos) > 1:
                text_filter = _key(pos[1])
        else:
            text_filter = _key(pos[0])

    years = [year_filter] if year_filter else year_dirs()
    all_errs = []
    for y in years:
        set_year(y)
        if not DATA.is_dir():
            continue
        targets = [text_filter] if text_filter else _auto_targets()
        for n in targets:
            tag = f"text{n}" if str(n).isdigit() else str(n)
            if not (DATA / f"{tag}.quiz.txt").exists():
                continue
            all_errs += check(n)
    print()
    if all_errs:
        print(f"发现 {len(all_errs)} 个问题：")
        for e in all_errs:
            print("  ! " + e)
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
