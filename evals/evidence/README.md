# `evals/evidence/` —— 让"验证过了"这句话能被别人重放

> 起因：评审的共识之一是「测试与验证声称不可复现——只有一句『210 条全绿』，没有能重放的证据文件」。
> 这个目录就是补那个洞：**每条声称都配一条命令、一段真实输出、一份已知偏差。**

## 0 · 一句话结论

| 声称 | 证据 | 重放成本 |
|---|---|---|
| 引擎单测 216 条全绿 | `test-run.txt`（真实输出全文） | **零依赖**，`python3` 一条命令 |
| 端到端跑批 32 条全绿 | `test-run.txt`（同上文件下半段） | **零依赖**，`python3` 一条命令 |
| 历法 1850–2100 与 `lunar_python` 逐日比对：91,466/91,676 一致，7 个月首差异经仲裁判我方正确 | `calendar-vs-lunarpython.md` + `calendar_cmp.py` | 需另装 `lunar_python==1.4.9`（外部 oracle），**不是本 skill 依赖** |
| 紫微 546 盘与 `iztro@2.6.2` 逐字段比对：543 盘 0 差异，3 盘归 2 类根因 | `ziwei-vs-iztro.md` | 需 `npm i iztro@2.6.2` + Node ≥ 18，**不是本 skill 依赖** |
| 上面这些数字对应**哪一版代码** | `hashes.txt`（`scripts/*.py` 与 `references/*.md` 的 sha256） | **零依赖**，`shasum -a 256` |

## 1 · 文件清单

| 文件 | 是什么 |
|---|---|
| `README.md` | 本文件：怎么复现、期望输出、已知偏差 |
| `test-run.txt` | `unittest discover` 与 `run_evals.py` 的**真实输出全文**（含命令与时间戳，可直接 eyeball 比对） |
| `calendar-vs-lunarpython.md` | 历法比对的方法、区间、7 个争议月首的朔时刻与 USNO 仲裁记录、重跑方式 |
| `calendar_cmp.py` | 上述比对的可运行脚本（缺 oracle 时明确报错并给安装命令，不会静默跳过） |
| `ziwei-vs-iztro.md` | 紫微比对的口径、546 盘覆盖、2 类已知差异的逐条实测输出、重跑方式 |
| `hashes.txt` | 生成当时的 `scripts/*.py` 与 `references/*.md` 的 sha256 |

`hashes.txt` 生成于 **2026-11-18 07:02 CST**（24 个文件，全部可校验）。在仓库根目录运行：

```bash
shasum -a 256 -c evals/evidence/hashes.txt     # 期望 24 行 "OK"
```

> 注意：`references/*.md` 在本目录生成时正被并行编辑。hash 只代表**那一刻**的版本；
> 若校验出现 `FAILED`，先用 `git log --oneline -- <文件>` 看是不是文档改动，再决定是否重算。
> 产品代码（`scripts/*.py`）在本目录定稿后未再改动。

## 2 · 三条重放路径

### 2.1 不需要任何外部工具（先跑这条）

```bash
cd <repo>
python3 -m unittest discover -s scripts/tests -q
python3 evals/run_evals.py
python3 evals/lint_reading.py evals/samples/good.md   # 应「通过」（可有 WARN）
python3 evals/lint_reading.py evals/samples/bad.md    # 应「不合格」（有 ERROR，exit 1）
python3 scripts/xuan.py doctor                        # 第三方依赖：无
```

期望尾部（与 `test-run.txt` 一致）：

```
Ran 216 tests in ...s
OK

=== 汇总：32 passed, 0 failed ===
```

**已知偏差**：`test-run.txt` 里的耗时与时间戳随机器不同，测试条数与 `PASS` 行数必须一致；
`good.md` 会有 1 条 `S2` WARN（书名有引号但出处状态写在括号内，检查器识别不了这种写法），
**WARN 不影响通过**；`bad.md` 必须 exit 1。

### 2.2 历法比对（要 `lunar_python`，外部 oracle）

```bash
python3 -m venv /tmp/oracle-venv
/tmp/oracle-venv/bin/pip install lunar_python==1.4.9
/tmp/oracle-venv/bin/python evals/evidence/calendar_cmp.py     # 全量，本次实测 1 分 26 秒
```

期望：`checked: 91676` / `mismatch: 210` / `kernel_error: 0`，7 段各 30 天。
细节与逐条朔时刻见 `calendar-vs-lunarpython.md`。

### 2.3 紫微比对（要 `iztro`，外部 oracle）

```bash
mkdir -p /tmp/iztro-check && cd /tmp/iztro-check
npm init -y && npm i iztro@2.6.2
# 用 gen.mjs dump 盘面 → python3 cmp.py / cmp2.py / cmp3.py 逐字段比
```

期望：第 1 批 208 盘 `fails: 0`；第 2 批 330 盘 `fails: 12`（全部落在 `1916-02-15` 一盘的主星集合）；
第 3 批晚子时 8 盘里 2 盘（1990-05-15、2020-06-15）整盘错位。细节见 `ziwei-vs-iztro.md`。

## 3 · 零依赖纪律怎么守住的

- `scripts/` 下的**产品脚本**一个第三方 import 都没有；`scripts/xuan.py doctor` 用 AST 扫
  `scripts/*.py` 的 import，出现非标准库就报错（`evals/` 不在扫描范围，也不该在）。
- `calendar_cmp.py` 是**核对工具**，必须借外部实现当 oracle。它把 `import lunar_python`
  放在函数里并用 `try/except ImportError` 包住，缺了就给安装命令 + `exit 2`——**它不是依赖，是尺子**。
- 紫微的比对脚本没进仓库（是 `/tmp` 里的一次性 Node 脚本），因为 `iztro` 只能在 Node 侧跑；
  文档里给了完整口径与代码骨架，任何人可重建。

## 4 · 已知偏差清单（知道自己在哪不严谨）

| 项 | 偏差 | 处置 |
|---|---|---|
| `references/calendar.md` 写「91 672 天」 | 闭区间实为 **91,676** 天（`(2100-12-31 − 1850-01-01) + 1`） | 已在本目录注明；该文件不属本次改动范围，留给维护者订正 |
| README「546 盘 0 差异（2 处例外）」 | 按**盘**数是 3 盘（1916-02-15、1990-05-15、2020-06-15），归为 **2 类根因** | 两种说法都对，本目录以分盘清单为准 |
| `good.md` 的 1 条 S2 WARN | 检查器只认 `（pub）` 这类紧贴的写法，认不出「（《书》，pub）」 | 已记录；S 系检查是启发式，误报按 WARN 处理不判不合格 |
| `evals/cases.jsonl` 的「无某 warning」断言 | `run_evals.py` 只有正向断言（且不属本次可改文件），故用 **warnings 全量等值**实现否定断言 | 已用探针验证：多一条 `AI_CAST_RANDOM` 就会红（见 `README` 第 5 节） |
| USNO 月相那一列 | 构建期查询记录，本次**未联网重跑** | 表里已标注；能复算的是本仓朔时刻三列 |
| 32 条端到端用例以外 的"综合解读质量" | 无自动化评判 | 只有 `lint_reading.py` 查形式与红线，不查"算得准不准" |

## 5 · 否定断言真的是否定断言吗（自证）

`cases.jsonl` 里 `liuyao-lines-cast-by-user` 用「warnings 全量等值」表达"不得出现 AI_CAST_RANDOM"。
直接验证它会不会红：

```bash
cd <repo>
python3 -c "
import sys; sys.path.insert(0,'evals')
import run_evals as R
base={'id':'probe','cmd':['liuyao','--lines','101011','--date','2026-11-18','--hour','10:30','--json']}
bad=dict(base); bad['expect_warnings']=['AI_CAST_RANDOM']   # 逼它找不到 → 必须 FAIL
print(R.run_case(bad))
print(R.run_case({'id':'probe2','cmd':base['cmd'],'expect':{'warnings':[{'code':'STATIC_GUA','message':'x'}]}}))
"
# 实测（2026-11-18）：
# ('probe', False, "缺 warning AI_CAST_RANDOM（实际：['STATIC_GUA']）")
# ('probe2', False, "warnings 期望 [{'code': 'STATIC_GUA', 'message': 'x'}] 实际 [...手输无动爻...]")
```

两行都 `False`，说明跑批器对"多一条不该有的警告"和"少一条该有的警告"都会判红——不是只报喜。

## 6 · 这些证据**没有**证明的事

- 没有证明六爻/奇门/风水的盘面"与某个外部实现一致"——它们**没有**第三方 oracle，属规则级验证（README 已标）。
- 没有证明解读层面的吉凶判断"正确"——那是流派口径，`lint_reading.py` 只查形式与红线。
- 没有证明 `lunar_python` / `iztro` 本身正确；恰恰相反，历法那 7 段是我们**判 oracle 错**并给出仲裁依据的。
- 没有覆盖 1850 年以前、2100 年以后；内核直接拒绝外推。
