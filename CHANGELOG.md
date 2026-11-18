# CHANGELOG

## v1.2.0 · P0 质量加固（未发版，建议发）

只改「自检 / 评测 / 安装」三层，不动任何术数规则与历法计算。

### 修复
- `scripts/xuan.py doctor`：`ok` 不再只看第三方依赖。现在 Python 版本、必需模块存在、模块可导入、
  历法内核真算一组已知答案、零第三方依赖，任一项失败即 `ok:false` 且退出码 2；新增 `failures[]` 与 `checks{}`。
  模块加载改为按文件独立加载，不再被 `sys.modules` 缓存掩盖。
- `evals/lint_reading.py`：
  - 表格里的断语不再被跳过（旧版 `startswith("|")` 直接 continue）；
  - 「据《书》」「云：」不再算出处状态（模糊引文现在 ERROR）；
  - 断语 basis 改为逐句判定，一行里「一句有、一句没有」不再互相掩盖；
  - 显式规则表 `RULES`：S1/S2/S3/S4/S7/S8/S9 = ERROR，S5/S6/S10 = WARN；S8 由 WARN 升 ERROR。
- `evals/run_evals.py`：负向用例同时校验退出码 + `ok=false` + `error.code` + `error.message`；
  区分 `pass / fail / error`（跑不起来的用例单独计）；新增 `forbid_warnings`、`--json` 汇总。
- `install.sh`：去掉 `|| true`；自检失败即安装失败；目标与卸载均有守卫（拒绝 skills 根目录、
  拒绝非本 skill 目录、拒绝源目录内部）；先装到临时目录、自检通过才替换；新增 `--force` / `--no-verify`。
- `calendar --date` 非法日期的错误文案由 `day is out of range for month` 改为 `日期不存在：YYYY-MM-DD`
  （仅错误文案，历法逻辑未改）。

### 测试
- 新增 `test_doctor.py`（9）、`test_lint_reading.py`（14）、`test_run_evals.py`（11）、`test_install_sh.py`（9）。
- 总数 216 → 260；端到端 32 → 34（新增 `xuan-unknown-cmd`、`bazi-bad-date` 两条负向用例）。
- CI 增加 `bash -n install.sh` 与安装/守卫冒烟。

## v1.1.0 · 多号池评审后加固
见 README §11。
