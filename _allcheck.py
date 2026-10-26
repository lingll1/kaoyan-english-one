"""成品核验：按各年 data/*.lesson.json 逐个检查生成的 HTML 体例是否齐全。

用法：
    python _allcheck.py            # 检查全部年份
    python _allcheck.py 2021       # 只查某一年
    python _allcheck.py 2021 2022  # 查多年

与前几个脚本不同，本脚本**不要求固定篇数**：有多少份数据就核验多少篇，
所以既能用于完整项目（7 年 49 篇），也能用于只有一两篇样例的仓库。
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
TAGS = ["原句含义", "语法辨析", "难点解析", "易错点解析"]


def html_name(year, key, meta):
    """复现 build.py 的文件名规则。"""
    part = str(meta.get("part") or "A").strip()
    if part == "cloze":
        return f"英语一{year}_完形填空.html"
    if part == "B":
        return f"英语一{year}_新题型PartB.html"
    if part == "C":
        return f"英语一{year}_翻译PartC.html"
    return f"英语一{year}_阅读Text{meta.get('no', key)}.html"


def years():
    return sorted(p.name for p in BASE.iterdir()
                  if p.is_dir() and len(p.name) == 4 and p.name.isdigit())


def check_year(y):
    docdir = BASE / y / "docs"
    datadir = BASE / y / "data"
    bad, total = [], 0
    print(f"\n== {y} ==")
    files = sorted(datadir.glob("*.lesson.json"))
    if not files:
        print("  （无数据文件，跳过）")
        return bad, total
    for jf in files:
        try:
            meta = json.loads(jf.read_text(encoding="utf-8")).get("meta") or {}
        except Exception as e:
            bad.append(f"{y}/{jf.name}: 解析失败 {e}")
            print(f"  !! {jf.name} 解析失败")
            continue
        key = jf.name[: -len(".lesson.json")]
        name = html_name(y, key, meta)
        p = docdir / name
        if not p.exists():
            bad.append(f"{y} 缺文件 {name}")
            print(f"  !! 缺 {name}")
            continue
        h = p.read_text(encoding="utf-8")
        wd = h.count('class="wd')
        qz = h.count('class="para qz"')
        cn = h.count('class="qzcn"')
        k = [h.count(f'class="blk k{i}"') for i in (1, 2, 3, 4)]
        tagok = all((f"<span class='tag'>{t}</span>" in h)
                    or (f'<span class="tag">{t}</span>' in h) for t in TAGS)
        v6 = "同类型变体题 · 6 题" in h
        ok = wd > 0 and all(x > 0 for x in k) and tagok and v6
        total += 1
        print(f"  {'OK' if ok else '!!'} {name:34s} wd={wd:5d} qz={qz:3d} "
              f"cn={cn:3d} k={k} tags={tagok} v6={v6}")
        if not ok:
            bad.append(f"{y}/{name}: wd={wd} qz={qz} cn={cn} k={k} tags={tagok} v6={v6}")
    return bad, total


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    targets = args if args else years()
    bad, total = [], 0
    for y in targets:
        if not (BASE / y).is_dir():
            print(f"跳过 {y}：目录不存在")
            continue
        b, t = check_year(y)
        bad += b
        total += t
    print(f"\n共核验 {total} 篇")
    if bad:
        print("\n有问题：")
        for b in bad:
            print("  -", b)
        sys.exit(1)
    print(f"全部 {total} 篇结构核验通过。")


if __name__ == "__main__":
    main()
