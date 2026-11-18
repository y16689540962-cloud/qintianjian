#!/usr/bin/env python3
"""钦天监 · 回归跑批。

读 evals/cases.jsonl，逐条跑命令、比对输出，打印 PASS/FAIL/ERROR 与分类汇总。

用法：
    python3 evals/run_evals.py                # 跑全部
    python3 evals/run_evals.py --filter bazi  # 只跑 id 含 bazi 的
    python3 evals/run_evals.py --verbose
    python3 evals/run_evals.py --json         # 机读汇总（CI 用）

案例格式（每行一个 JSON）：
    {
      "id": "bazi-1990-0515-1200",
      "cmd": ["bazi", "--solar", "1990-05-15", "--hour", "12:00", "--sex", "男", "--json"],
      "expect": {"result.pillars.day.ganzhi": "庚辰"},   # 正向：字段等值
      "expect_present": ["result.dayun"],                # 正向：字段存在
      "expect_warnings": ["CLOCK_CHANGE"],               # 正向：必须出现的 warning
      "forbid_warnings": ["SHICHEN_UNKNOWN"],            # 正向：不许出现的 warning
      "expect_exit": 0,                                  # 期望退出码，默认 0
      "expect_error_code": "BAD_DATE",                   # 负向：error.code 必须是它
      "expect_error_contains": "不存在",                  # 负向：error.message 必须包含
      "status": "oracle-verified",   # oracle-verified | rule-verified | oracle-arbitrated | unverified
      "note": "与 lunar_python 交叉核对"
    }

判定分类（v1.2 起显式区分）：
    pass  —— 期望与实际一致
    fail  —— 期望与实际不符（用例写错或实现行为变了）
    error —— 跑不起来：超时、找不到脚本、stdout 不是 JSON、期望成功却崩溃

设计原则：
    1. 只依赖标准库，和主 skill 一样零依赖。
    2. 不联网：所有期望值来自古籍、oracle 交叉核对或手工推算，写在 cases.jsonl 里。
    3. 失败时打印实际值，便于直接改期望或修实现。
    4. 负向用例不只看退出码：同时校验信封 ok=false、error.code、error.message（v1.2 修）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
CASES = os.path.join(HERE, "cases.jsonl")


def resolve(cmd):
    """把 ['bazi', ...] 解析成真正的命令行。"""
    if not cmd:
        raise ValueError("空命令")
    head = cmd[0]
    if head.endswith(".py"):
        path = os.path.join(SCRIPTS, head)
        return [sys.executable, path] + list(cmd[1:])
    path = os.path.join(SCRIPTS, head + ".py")
    if os.path.exists(path) and head != "xuan":
        return [sys.executable, path] + list(cmd[1:])
    return [sys.executable, os.path.join(SCRIPTS, "xuan.py")] + list(cmd)


def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (IndexError, ValueError):
                return ("__missing__", dotted)
        elif isinstance(cur, dict):
            if part not in cur:
                return ("__missing__", dotted)
            cur = cur[part]
        else:
            return ("__missing__", dotted)
    return cur


def _tail(text, n=3):
    lines = (text or "").strip().splitlines()
    return " | ".join(lines[-n:]) if lines else "<空>"


def run_case(case, verbose=False):
    """执行一条用例，返回结构化结果：{id, verdict, reasons, seconds}。"""
    cid = case.get("id", "?")
    t0 = time.time()
    result = {"id": cid, "verdict": "fail", "reasons": [], "seconds": 0.0}

    def done(verdict, reason=None):
        result["verdict"] = verdict
        if reason:
            result["reasons"].append(reason)
        result["seconds"] = round(time.time() - t0, 2)
        return result

    expect_exit = case.get("expect_exit", 0)
    try:
        cmdline = resolve(case["cmd"])
    except Exception as exc:  # noqa: BLE001
        return done("error", "命令解析失败：%s" % exc)

    if verbose:
        print("  $ " + " ".join(cmdline))
    try:
        proc = subprocess.run(cmdline, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return done("error", "超时（60s）")
    except FileNotFoundError as exc:
        return done("error", "找不到可执行文件：%s" % exc)

    # ---- 退出码：区分「期望失败没发生」与「期望成功却崩了」 ----
    if proc.returncode != expect_exit:
        if expect_exit == 0:
            return done("error", "意外失败：期望退出 0，实际 %d；尾部：%s"
                        % (proc.returncode, _tail(proc.stderr or proc.stdout)))
        return done("fail", "期望退出 %d，实际 %d；尾部：%s"
                    % (expect_exit, proc.returncode, _tail(proc.stderr or proc.stdout)))

    # ---- 负向用例：必须校验错误码与文案，不能只看退出码 ----
    if expect_exit != 0:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return done("fail", "负向用例的 stdout 不是 JSON（前 120 字：%r）" % proc.stdout[:120])
        if payload.get("ok") is not False:
            return done("fail", "负向用例期望 ok=false，实际 ok=%r" % payload.get("ok"))
        err = payload.get("error") or {}
        want_code = case.get("expect_error_code")
        if want_code is not None and err.get("code") != want_code:
            return done("fail", "error.code 期望 %r，实际 %r" % (want_code, err.get("code")))
        want_msg = case.get("expect_error_contains")
        if want_msg is not None and want_msg not in (err.get("message") or ""):
            return done("fail", "error.message 期望包含 %r，实际 %r" % (want_msg, err.get("message")))
        return done("pass")

    # ---- 正向用例 ----
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return done("error", "stdout 不是合法 JSON（前 120 字：%r）" % proc.stdout[:120])

    if payload.get("ok") is not True:
        return done("fail", "信封 ok 期望 true，实际 %r（error=%s）"
                    % (payload.get("ok"), json.dumps(payload.get("error"), ensure_ascii=False)))

    problems = []
    for path, want in (case.get("expect") or {}).items():
        got = get_path(payload, path)
        if isinstance(got, tuple) and got and got[0] == "__missing__":
            problems.append("缺字段 %s" % path)
        elif got != want:
            problems.append("%s 期望 %r 实际 %r" % (path, want, got))

    for path in (case.get("expect_present") or []):
        got = get_path(payload, path)
        if isinstance(got, tuple) and got and got[0] == "__missing__":
            problems.append("缺字段 %s" % path)

    codes = [w.get("code") for w in payload.get("warnings", []) if isinstance(w, dict)]
    for code in (case.get("expect_warnings") or []):
        if code not in codes:
            problems.append("缺 warning %s（实际：%s）" % (code, codes))
    for code in (case.get("forbid_warnings") or []):
        if code in codes:
            problems.append("出现了不该有的 warning %s（实际：%s）" % (code, codes))

    if problems:
        return done("fail", "；".join(problems))
    return done("pass")


def load_cases(path=CASES):
    cases = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("cases.jsonl 第 %d 行不是合法 JSON：%s" % (lineno, exc))
    return cases


def summarize(results):
    counts = {"pass": 0, "fail": 0, "error": 0}
    for r in results:
        counts[r["verdict"]] += 1
    return {"total": len(results), "counts": counts,
            "ok": counts["fail"] == 0 and counts["error"] == 0,
            "results": results}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    flt = None
    verbose = False
    as_json = False
    for i, a in enumerate(argv):
        if a == "--filter" and i + 1 < len(argv):
            flt = argv[i + 1]
        if a in ("--verbose", "-v"):
            verbose = True
        if a == "--json":
            as_json = True

    if not os.path.exists(CASES):
        print("找不到 %s" % CASES)
        return 2

    try:
        cases = load_cases()
    except ValueError as exc:
        print(str(exc))
        return 2

    if flt:
        cases = [c for c in cases if flt in c.get("id", "")]
    if not cases:
        print("没有匹配的用例")
        return 2

    results = []
    if not as_json:
        print("跑批：%d 条用例（%s）\n" % (len(cases), CASES))
    for case in cases:
        r = run_case(case, verbose=verbose)
        results.append(r)
        if not as_json:
            status = case.get("status", "unverified")
            tag = {"pass": "PASS ", "fail": "FAIL ", "error": "ERROR"}[r["verdict"]]
            detail = ("  " + "；".join(r["reasons"])) if r["reasons"] else ""
            print("%s %-34s [%s] %5.2fs%s" % (tag, r["id"], status, r["seconds"], detail))

    summary = summarize(results)
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        counts = summary["counts"]
        print("\n=== 汇总：%d passed, %d failed, %d errors（共 %d 条）==="
              % (counts["pass"], counts["fail"], counts["error"], summary["total"]))
        if counts["fail"] or counts["error"]:
            print("\n明细（fail=期望不符；error=跑不起来）：")
            for r in results:
                if r["verdict"] != "pass":
                    print("  [%s] %s：%s" % (r["verdict"], r["id"], "；".join(r["reasons"])))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
