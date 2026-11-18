# v1.2 · P0 质量加固：问题清单与修改方案

> 规则：本文件先于任何代码修改提交。修复顺序按「会静默骗人」的严重度排：doctor → lint → run_evals → install.sh。
> 不改动 `calendar_core.py` / `bazi.py` 等术数规则与历法逻辑；只改自检、评测、安装这三层「质量基础设施」。

## 0. 复现方式（修之前先证明问题存在）

| 问题 | 复现命令 / 输入 | 当前错误行为 |
|---|---|---|
| doctor 漏报 | 把 `scripts/tarot.py` 改名后 `python3 scripts/xuan.py doctor; echo $?` | 仍输出 `ok:true`、exit 0 |
| doctor 不看 Python 版本 | 用 3.8 解释器跑（或改 `python_ok` 判断为假） | `ok` 仍为 true |
| lint 跳过表格 | 第 2 段写一行 `\| 流年 \| 今年宜守 \|` | 0 ERROR（S8 跳过 `\|` 开头行） |
| lint 模糊出处 | 只写「据《滴天髓》……」不给状态 | 0 WARN/ERROR（`CITATION_STATE_RE` 把 `据《` 当状态） |
| lint 一行掩盖 | 一行两句：「今年宜守（model）；明年必有变动」 | 整行通过（正则只要求行内出现一次 basis） |
| run_evals 负向只看退出码 | `expect_exit:2`，脚本因 segfault/参数错误也 exit 2 | 判 PASS |
| run_evals 不查错误码 | 同上看 `"error":{"code":...}` | 完全不校验 |
| install 吞失败 | 让 doctor 失败后跑 `./install.sh claude` | `\|\| true` 吞掉，exit 0 |
| install 危险目标 | `./install.sh ~/.dsh/skills` | 会往 skills 根目录写文件并 `rm -rf` 同名子目录 |
| uninstall 无保护 | `./install.sh --uninstall /some/user/dir` | 直接 `rm -rf` |

## 1. P0-1 `scripts/xuan.py` doctor

**根因**：`_doctor()` 里 `payload["ok"] = not third_party` —— 只有第三方依赖参与判定；`python_ok`、`has_calendar_core` 只写进结果不参与；模块缺失/导入失败也没有汇总成失败；没有任何「历法内核真能算」的检查；失败原因只散在人类可读文本里。

**方案**
1. 抽出纯函数 `diagnose(base_dir=HERE, python_version=None) -> dict`，返回 `{ok, failures[], checks{}, modules{}}`，CLI 只负责打印与退出码。**可测**：测试可以传入临时目录与伪造的 Python 版本。
2. 检查项（全部参与 `ok`）：
   - `python>=3.9`（可注入版本，便于测试）；
   - 8 个必需模块文件存在（`hehun` 标为可选，缺失只 WARN 不失败）；
   - 每个模块能被**从 base_dir 真实加载**（用 `importlib.util.spec_from_file_location` 独立命名，避免 `sys.modules` 缓存把别处的副本当成通过）；
   - `calendar_core` 功能抽查：`solar_to_lunar(1990,5,15)` 必须是 `1990/4/21`，`ganzhi_day` 必须是「庚辰」——只调用现有 API，不改历法逻辑；
   - 零第三方：AST 扫描 base_dir 下全部 `*.py`。
3. `failures[]` 每项写 `{check, detail}`；`ok=false` 时 exit 2，并逐条打印。
4. 保留 `--json` 信封与现有字段（`modules/third_party_imports/python_ok/has_calendar_core`），新增 `failures` 与 `checks`，**不破坏下游解析**。

## 2. P0-2 `evals/lint_reading.py`

**根因三条**：
- `_section_lines` 取行后，S8 里 `if line.lstrip().startswith(("|", ">", "#")): continue` —— 表格被判语直接跳过；
- `CITATION_STATE_RE` 把 `据《`、`云：「` 也算「有状态」，于是模糊引文通过；
- S8 用行级匹配，一行里只要出现一次 basis 就整行放过。

**方案**
1. **显式规则表**：`ERROR_CODES = {S1,S2,S3,S4,S7,S9,S8}`、`WARN_CODES = {S5,S6,S10}`，并在模块 docstring 与 `RULES` 常量里写明「哪些会导致不合格」。S8 从 WARN 升为 ERROR（v1.1 契约本来就写「没有 basis 的判断句 = 违规」，之前是文件没跟上）。
2. **S2 重写**：拆成两个正则——`BOOK_RE`（`《…》`）与 `STATUS_RE`（只认 `（verified）/（pub）/（school）/（undated）` 或「原文核对/通行出处/流派口径/无确证」）。带引号书名且全文无任何 `STATUS_RE` → **S2 ERROR**；某一行有书名但该行没有状态、而全文有过 → WARN（指出具体行）。
3. **S8 逐句判定**：先把表格行去掉首尾 `|` 并拆单元格，再把行按 `[。；;！？!?]` 切句；**每个含判断词的句子**必须自带 basis。表头/分隔行（`|---|`）跳过。这样「一行两句、一句有 basis」不再放行。
4. 新增 `lint(text) -> (errors, warns, stats)`（stats 按 code 计数），CLI 依次打印；保持 `lint()` 原签名兼容（返回 `(errors, warns)` 的两元组）会破坏测试——**改为三元组并在测试里固定**，同时 `main` 只用前两项。
5. 正反测试（`scripts/tests/test_lint_reading.py`）：表格行缺 basis → ERROR；表格行带 basis → 干净；模糊出处 → ERROR；显式状态 → 干净；一句有 basis 一句没有 → 恰好 1 条 ERROR；WARN/ERROR 集合与 `RULES` 表一致。

## 3. P0-3 `evals/run_evals.py`

**根因**：`if expect_exit != 0: return cid, True, ""` —— 非零退出即判过；不解析信封、不校验 `error.code`；「预期失败」和「意外失败」在输出里无法区分；汇总只有 passed/failed。

**方案**
1. `run_case()` 返回结构化结果：`{id, kind: pass|fail|error, reasons[], duration}`。
   - `error` = 超时 / 找不到脚本 / stdout 不是 JSON / 未预期异常 → 单独计数，提示这是**基础设施问题**而不是「用例不符」。
2. 负向用例必须同时满足：退出码 == `expect_exit`、stdout 是 JSON、`ok == false`、`error.code` == `expect_error_code`（若给了）、`error.message` 含 `expect_error_contains`（若给了）。缺一项即 fail，并说明缺哪项。
3. 新增 `forbid_warnings`（断言某些 warning 不出现），补上「正向断言无法表达否定」的缺口。
4. 汇总分三行：`passed / failed / errors`，并按 `status` 分组；`--json` 输出机读汇总。
5. cases.jsonl 给负向用例补 `expect_error_code` / `expect_error_contains`；新增 `xuan-unknown-cmd` 负向用例。
6. 测试（`scripts/tests/test_run_evals.py`）：真跑 `calendar --date 1990-02-30` 验证「错误码对 → pass / 错误码错 → fail / 期望 0 却非零 → error」。

## 4. P0-4 `install.sh`

**根因**：`doctor || true` 吞失败；无目标合法性校验；卸载对任意目录 `rm -rf`；复制前先删目标同名目录（若目标是 skills 根目录会波及用户其它 skill）。

**方案**
1. **目标守卫** `validate_target()`：拒绝 `/`、`$HOME`、`$HOME/.dsh/skills`、`$HOME/.claude/skills`、`$HOME/.codex/skills`、源目录及其父目录；目标必须是「不存在 / 空目录 / 已有我们 marker 的目录」之一。
2. **marker**：`SKILL.md` 里必须有 `name: qintianjian`。已有目录但 marker 不符 → 拒绝并提示 `--force`（复制到 `.bak` 后再装？不，简单拒绝更安全）。
3. **卸载保护**：只有 marker 校验通过才删；否则拒绝，除非 `--force`；删除前打印将删除的绝对路径并确认路径在白名单父目录内。
4. **原子安装**：先复制到 `$TARGET.installing.$$`，`doctor` 通过后才 `mv` 到目标；失败清理临时目录并 exit 1。**不再用 `|| true`**；另提供 `--no-verify` 显式跳过（默认不跳过）。
5. 复制清单不变；但删目标子目录前确认目标是我们的目录（marker 或不存在）。
6. 测试（`scripts/tests/test_install_sh.py`，用临时 HOME 与临时目标，绝不碰真实目录）：
   - 正常安装 → exit 0、目标有 SKILL.md、doctor 通过；
   - 源头坏掉（temp 副本里破坏一个模块）→ 安装失败、exit≠0、目标不存在或未被替换；
   - 目标 = skills 根目录 → 拒绝，且目录内容不变；
   - 卸载非我们目录 → 拒绝；
   - `--uninstall` 我们自己的目录 → 只删它。

## 5. 不改的东西（避免越界）

- 不碰 `calendar_core.py`、`bazi.py`、`ziwei.py`、`qimen.py`、`liuyao.py`、`tarot.py`、`fengshui.py`、`hehun.py` 的任何计算逻辑。
- 不删任何现有测试、不降低断言；只新增与收紧。
- 不动 `cases.jsonl` 里既有期望值（除补错误码字段）。

## 6. 交付核对清单

- [x] `python3 -m unittest discover -s scripts/tests -q` 全绿（**260 tests OK**）
- [x] `python3 evals/run_evals.py` 全绿（**34 passed, 0 failed, 0 errors**；负向用例校验错误码与文案）
- [x] `python3 evals/lint_reading.py evals/samples/good.md` 通过（0 ERROR / 0 WARN）；`bad.md` 报错（12 ERROR，exit 1）
- [x] `bash -n install.sh` 通过；安装/守卫/卸载/坏源四类行为在临时 HOME 下验证（见 `test_install_sh.py`）
- [x] CI 新增 `bash -n install.sh` + 安装冒烟步骤
- [x] 报告：见交付说明（文件清单 / 根因 / 行为差异 / 新增用例 / 实测输出 / 未解决项 / 是否发版）

## 7. 结果（2026-11-18 实测）

| 检查 | 修复前 | 修复后 |
|---|---|---|
| 模块缺失时的 doctor | `ok:true` / exit 0 | `ok:false` / exit 2，`failures` 指明 `module:tarot` |
| 历法算错时的 doctor | 只查文件存在，不报 | 抽查 1990-05-15，答案不符即失败 |
| 表格里的断语缺 basis | 0 ERROR（跳过表格） | S8 ERROR |
| 「据《滴天髓》」无状态 | 0 WARN/ERROR（模糊引文算状态） | S2 ERROR |
| 一行两句一句有 basis | 整行通过 | 逐句判定，缺的那句报 S8 |
| 负向用例错误码写错 | 仍判 PASS（只看退出码） | 判 FAIL，指出 `error.code` 不符 |
| 期望成功却退出 2 | 与普通失败混在一起 | 单独计为 `error`（基础设施问题） |
| 安装后自检失败 | `|| true` 吞掉，exit 0 | 安装中止、exit 1、目标未被改动 |
| 装到 skills 根目录 | 允许（会破坏其它 skill） | 拒绝，其它 skill 文件完好 |
| 卸载任意目录 | `rm -rf` | 无标记即拒绝 |

