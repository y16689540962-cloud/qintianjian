#!/usr/bin/env python3
"""钦天监 · 回归跑批。

读 evals/cases.jsonl，逐条跑命令、比对 JSON 字段，打印 PASS/FAIL 与汇总。

用法：
    python3 evals/run_evals.py                # 跑全部
    python3 evals/run_evals.py --filter bazi  # 只跑 id 含 bazi 的
    python3 evals/run_evals.py --verbose

案例格式（每行一个 JSON）：
    {
      "id": "bazi-1990-0515-1200",
      "cmd": ["bazi", "--solar", "1990-05-15", "--hour", "12:00", "--sex", "男", "--json"],
      "expect": {"result.pillars.day.ganzhi": "庚辰"},
      "expect_warnings": [],
      "expect_exit": 0,
      "status": "oracle-verified",   // oracle-verified | rule-verified | unverified
      "note": "与 lunar_python 交叉核对"
    }

设计原则：
    1. 只依赖标准库，和主 skill 一样零依赖。
    2. 不联网：所有期望值来自古籍、oracle 交叉核对或手工推算，写在 cases.jsonl 里。
    3. 失败时打印实际值，便于直接改期望或修实现。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

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
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                return ("__missing__", dotted)
            cur = cur[part]
        else:
            return ("__missing__", dotted)
    return cur


def run_case(case, verbose=False):
    cid = case.get("id", "?")
    expect_exit = case.get("expect_exit", 0)
    try:
        cmdline = resolve(case["cmd"])
    except Exception as exc:  # noqa: BLE001
        return cid, False, "命令解析失败：%s" % exc

    if verbose:
        print("  $ " + " ".join(cmdline))
    try:
        proc = subprocess.run(cmdline, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return cid, False, "超时（60s）"
    except FileNotFoundError as exc:
        return cid, False, "找不到脚本：%s" % exc

    if proc.returncode != expect_exit:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return cid, False, "退出码 %s ≠ %s；stderr/stdout 尾部：%s" % (
            proc.returncode, expect_exit, " | ".join(tail))

    if expect_exit != 0:
        return cid, True, ""

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return cid, False, "stdout 不是合法 JSON（前 120 字：%r）" % proc.stdout[:120]

    if not payload.get("ok", False):
        return cid, False, "信封 ok=false：%s" % json.dumps(payload.get("error"), ensure_ascii=False)

    problems = []
    for path, want in (case.get("expect") or {}).items():
        got = get_path(payload, path)
        if got == ("__missing__", path):
            problems.append("缺字段 %s" % path)
        elif got != want:
            problems.append("%s 期望 %r 实际 %r" % (path, want, got))

    for code in (case.get("expect_warnings") or []):
        codes = [w.get("code") for w in payload.get("warnings", []) if isinstance(w, dict)]
        if code not in codes:
            problems.append("缺 warning %s（实际：%s）" % (code, codes))

    for path in (case.get("expect_present") or []):
        got = get_path(payload, path)
        if got == ("__missing__", path):
            problems.append("缺字段 %s" % path)

    if problems:
        return cid, False, "；".join(problems)
    return cid, True, ""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    flt = None
    verbose = False
    for i, a in enumerate(argv):
        if a == "--filter" and i + 1 < len(argv):
            flt = argv[i + 1]
        if a in ("--verbose", "-v"):
            verbose = True

    if not os.path.exists(CASES):
        print("找不到 %s" % CASES)
        return 2

    cases = []
    with open(CASES, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print("cases.jsonl 第 %d 行不是合法 JSON：%s" % (lineno, exc))
                return 2

    if flt:
        cases = [c for c in cases if flt in c.get("id", "")]

    if not cases:
        print("没有匹配的用例")
        return 2

    passed = failed = 0
    fails = []
    print("跑批：%d 条用例（%s）\n" % (len(cases), CASES))
    for case in cases:
        cid, ok, detail = run_case(case, verbose=verbose)
        status = case.get("status", "unverified")
        if ok:
            passed += 1
            print("PASS  %-34s [%s]" % (cid, status))
        else:
            failed += 1
            fails.append((cid, detail))
            print("FAIL  %-34s [%s]  %s" % (cid, status, detail))

    print("\n=== 汇总：%d passed, %d failed ===" % (passed, failed))
    if fails:
        print("\n失败明细：")
        for cid, detail in fails:
            print("  - %s：%s" % (cid, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
