# SPEC-OTHER —— 完形填空 / 新题型 Part B / 翻译 Part C 的数据规格

阅读（Part A）的规格见 `SPEC.md` 与 `SPEC-QUIZ.md`，本文件只写**三种新题型**与阅读的差异。
除本文件明确改写的字段外，`words.txt` / `lesson.json` / `quiz.txt` 的行格式、音标规则、
释义长度、解析四块（`原句含义`→`语法辨析`→`难点解析`→`易错点解析`）等**全部沿用 SPEC.md**。

---

## 一、共同点

| 项 | 值 |
|---|---|
| 目录 | `英语一/<年份>/data/` |
| 文本来源 | 各年 `SOURCE-others.md`（英文一字不得改） |
| 变体数量 | **每篇 6 道**（`variants` 数组长度 6） |
| 每道题解析块 | 4 块，`k` 依次为 `原句含义` `语法辨析` `难点解析` `易错点解析` |
| quiz.txt 块标记 | `@stem:<题号>`、`@opt:<题号>:<字母>`、`~中文整句译文` |

## 二、完形填空（`meta.part = "cloze"`）

- 文件名：`data/cloze.words.txt`、`data/cloze.lesson.json`、`data/cloze.quiz.txt`
- `meta`：`{"paper":"英语（一）","year":2021,"part":"cloze","no":"cloze","qs":"1–20","theme":"…","words":…,"difficulty":"…","tags":[…],"file":"…","source":"…"}`
- **原文正文**：`words.txt` 用 `@1`…`@5` 分 5 段，与 `SOURCE-others.md` 的 5 段一一对应。
  空格 token 写作 `(1)`…`(20)`，音标写 `_`（或 `/—/`，两者都合法；`build.py` 的 `check()` 对 `(N)` 这类空位 token 跳过音标格式校验），释义写 `第 1 空`（阿拉伯数字，不写「第十空」）。
- `para_notes`：5 段，每段 `trans` + **3 条**语法点。
- `questions`：**20 道**，`no` 为 1–20（整数）。
  - `stem`：该空**所在的完整句子**（把 `(N)` 写回去，其余空保留 `(M)`），逐词标注放 quiz.txt。
  - `options`：A–D 四个候选词。
  - `answer`：单个大写字母。
  - `locate`：如 `第 3 段第②句`。
  - `blocks`：四块。
- `quiz.txt` 块：`@stem:1`…`@stem:20` + 每题 `@opt:1:A`…`@opt:20:D`，共 **100 块**，每块末行 `~译文`。
- `variants`：6 道，自己另出 6 个空（可用原文其他词），格式同 `questions`，`no` 写 `"V1"`…`"V6"`。

## 三、新题型 Part B（`meta.part = "B"`）

- 文件名：`data/partb.words.txt`、`data/partb.lesson.json`、`data/partb.quiz.txt`
- `meta.qs`：如 `41–45`
- **原文正文**：`words.txt` 按原文自然段用 `@1`…`@N` 分段；41–45 的空格写作 `(41)`…`(45)`。
- `questions`：**5 道**，`no` 为 41–45。
  - `stem`：如 `Paragraph (41)` 或题面要求的指示语，简短。
  - `options`：**A–G 七个**（`{"A":…,"B":…,…, "G":…}`），与 `build.py` 的 `opt_letters="ABCDEFG"` 对应。
  - `answer`：单个大写字母。
- `quiz.txt`：`@stem:41`…`@stem:45` + `@opt:41:A`…`@opt:45:G`，共 **5×(1+7)=40 块**。
- `variants`：6 道，自拟同类型小题（可用选项 A–D 简化），`no` 写 `"V1"`…`"V6"`。

## 四、翻译 Part C（`meta.part = "C"`）

- 文件名：`data/trans.words.txt`、`data/trans.lesson.json`、`data/trans.quiz.txt`
- `meta.qs`：如 `46–50`
- **原文正文**：`words.txt` 用 `@1`…`@5` 分 5 段，**每段就是一句待译句**（句子编号不写进正文）。
- `para_notes`：5 段，`trans` 写**该句参考译文**，`grammar` 写该句的 3 条句法拆解（`h` 标题、`b` 结构/考点/例）。
- `questions`：**5 道**，`no` 为 46–50。
  - `stem`：**空字符串 `""`**（句子已在正文逐词展示，题目区不再重复）。
  - `options`：**空对象 `{}`** —— `build.py` 会渲染「参考译文」块。
  - `answer`：**参考译文全文**（中文）。
  - `blocks`：四块，`原句含义` 里给「直译 + 意译」两版。
- `quiz.txt`：**不需要**（无题干无选项）。若 `build.py` 因缺文件告警，请创建只有注释行的空文件。
- `variants`：6 道，另选/自拟 6 个英文长句，格式同 `questions`（`stem` 可为该句英文，`options` 为空对象）。

## 五、自检（必须全部通过）

```bash
cd "D:\职业\考研\英语一"
python verify.py <年份>     # 阅读原文比对
python qc.py <年份>         # 块齐全、词序列与 lesson.json 一致
python build.py <年份>      # 无 `!` 告警
python _final.py <年份>     # 结构计数
```

翻译篇因为没有 quiz.txt，`qc.py` 与 `build.py` 对它的块校验会自动跳过（`opt_letters` 为空）。
