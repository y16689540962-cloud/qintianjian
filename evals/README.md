# 评测 · 三层

| 层 | 工具 | 查什么 | 谁跑 |
|---|---|---|---|
| 1 确定性 | `run_evals.py` + `cases.jsonl` | 脚本输出对不对（干支、农历、卦名、飞星、牌序、seed 复现） | CI / 每次改引擎 |
| 2 文本体检 | `lint_reading.py` | 解读是否守输出契约与红线（五段、出处状态、绝对化、术法话术） | 改 SKILL/文档后 |
| 3 人工评分 | `rubric.md` | 路由、降级、校准、多派裁决、可行动性 | 发版前抽 10 条 |

## 1 · 跑确定性用例

```bash
python3 evals/run_evals.py                # 全跑
python3 evals/run_evals.py --filter bazi  # 只跑 id 含 bazi
python3 evals/run_evals.py --verbose
```

`cases.jsonl` 每行一个用例：

```json
{"id": "bazi-1990-0515-1200", "cmd": ["bazi", "--solar", "1990-05-15", "--hour", "12:00", "--sex", "男", "--json"],
 "expect": {"result.pillars.day.ganzhi": "庚辰"}, "status": "oracle-verified", "note": "与 lunar_python 一致"}
```

- `status` 三档：`oracle-verified`（有外部实现交叉核对）/ `rule-verified`（按古籍规则手算）/ `unverified`（结构检查）。
- **新增用例的规矩**：期望值必须先有来源（oracle 输出截图、古籍条文、手算过程），不许把当前输出复制一遍当期望值——那只能测「有没有变」，测不出「对不对」。

## 2 · 体检一段解读

```bash
python3 evals/lint_reading.py evals/samples/good.md   # 应通过
python3 evals/lint_reading.py evals/samples/bad.md    # 应报错
```

`good.md` / `bad.md` 是自检样本：改了 `lint_reading.py` 之后先跑这两个，确认检查器没坏（**先证明验证器有效**）。

## 3 · 人工 / LLM 评分

按 `rubric.md` 逐项 0/1/2，满分 20；任一 ⛔ 项为 0 即不合格。

## 4 · 当前状态

见 `cases.jsonl` 每条用例的 `status` 字段与项目 README 的「验证状态」表。没有 oracle 的模块（奇门、六爻、风水、塔罗）
只用 `rule-verified` / `unverified`，别在 README 里吹成「已验证」。
