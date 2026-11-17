#!/usr/bin/env python3
"""钦天监 · 统一 CLI 入口。

职责：把各术数引擎收在同一个命令下，统一 JSON 信封，提供自检。

用法：
    python3 scripts/xuan.py <子命令> [参数...]

子命令：
    calendar   公历/农历/节气/干支换算
    bazi       四柱八字排盘
    ziwei      紫微斗数排盘
    qimen      时家奇门排盘
    liuyao     六爻起卦装卦
    tarot      塔罗抽牌
    fengshui   风水（feixing / mingua / bazhai / liunian / day / zeri）
    hehun      双人合婚比较（可选模块）
    doctor     自检：版本、模块、依赖、第三方 import 扫描

设计原则：
    1. 每个子命令都是一个独立脚本，可单独运行；本文件只做分发。
    2. 所有子命令共享 `.build/CONTRACT.md` 里冻结的 JSON 信封。
    3. 本文件不实现任何术数规则，只做转发，避免规则二处实现、口径漂移。

口径来源：项目内部契约（CONTRACT.md §3/§4）。本文件不含术数判断。
零第三方依赖，Python 3.9+。
"""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import os
import sys

ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 子命令 → 模块名。hehun 为可选模块（不存在时给提示，不影响其他命令）。
SUBCOMMANDS = {
    "calendar": None,          # 本文件内实现
    "bazi": "bazi",
    "ziwei": "ziwei",
    "qimen": "qimen",
    "liuyao": "liuyao",
    "tarot": "tarot",
    "fengshui": "fengshui",
    "hehun": "hehun",
}

# Python 3.9 没有 sys.stdlib_module_names，这里显式列出本项目可能用到的标准库。
STDLIB_WHITELIST = {
    "__future__", "abc", "argparse", "ast", "bisect", "calendar", "cmath",
    "collections", "copy", "csv", "dataclasses", "datetime", "decimal", "enum",
    "fractions", "functools", "glob", "hashlib", "heapq", "importlib", "inspect",
    "io", "itertools", "json", "locale", "math", "operator", "os", "pathlib",
    "pprint", "random", "re", "shutil", "sqlite3", "statistics", "string",
    "subprocess", "sys", "tempfile", "textwrap", "time", "traceback", "types",
    "typing", "unicodedata", "unittest", "warnings", "xml", "zoneinfo",
}
LOCAL_MODULES = set(SUBCOMMANDS.values()) | {"calendar_core", "render", "tests"}


def _emit(payload: dict, as_json: bool, text: str = "") -> None:
    if as_json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write((text or json.dumps(payload, ensure_ascii=False, indent=2)) + "\n")


def _error(cmd: str, code: str, message: str, as_json: bool) -> int:
    payload = {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "cmd": cmd,
        "engine": ENGINE,
        "error": {"code": code, "message": message},
    }
    _emit(payload, as_json, text="错误 [%s] %s" % (code, message))
    return 2


# --------------------------------------------------------------------------
# calendar：换算类命令，逻辑极薄，直接放在入口里
# --------------------------------------------------------------------------

def _calendar_result(date_str=None, lunar=None, leap=False, year=None) -> dict:
    import calendar_core as cc

    result = {}
    base_dt = None
    if date_str:
        try:
            y, m, d = [int(x) for x in date_str.replace("/", "-").split("-")]
        except ValueError:
            raise ValueError("日期格式应为 YYYY-MM-DD，收到：%s" % date_str)
        base_dt = cc.datetime(y, m, d, 12, 0)
        result["solar"] = "%04d-%02d-%02d" % (y, m, d)
        result["lunar"] = cc.solar_to_lunar(y, m, d)
    elif lunar:
        ly, lm, ld = lunar
        y, m, d = cc.lunar_to_solar(ly, lm, ld, leap)
        base_dt = cc.datetime(y, m, d, 12, 0)
        result["lunar"] = cc.solar_to_lunar(y, m, d)
        result["solar"] = "%04d-%02d-%02d" % (y, m, d)
    elif year is None:
        raise ValueError("需要 --date 或 --lunar 或 --year 之一")

    if base_dt is not None:
        gy = cc.ganzhi_year(base_dt)
        gm = cc.ganzhi_month(base_dt)
        gd = cc.ganzhi_day(base_dt)
        result["ganzhi"] = {
            "year": "".join(gy),
            "month": "".join(gm),
            "day": "".join(gd),
        }
        jq = cc.jieqi_of_day(base_dt)
        result["jieqi_today"] = jq
        result["prev_jieqi"] = cc.prev_jieqi(base_dt)
        result["next_jieqi"] = cc.next_jieqi(base_dt)
        result["weekday"] = "一二三四五六日"[base_dt.weekday()]

    if year is not None:
        result["year"] = year
        result["terms"] = cc.solar_terms(int(year))
    return result


def _cmd_calendar(argv) -> int:
    parser = argparse.ArgumentParser(prog="xuan.py calendar", description="公历/农历/节气/干支换算")
    parser.add_argument("--date", help="公历日期 YYYY-MM-DD")
    parser.add_argument("--lunar", nargs=3, type=int, metavar=("Y", "M", "D"), help="农历 年 月 日")
    parser.add_argument("--leap", action="store_true", help="农历闰月")
    parser.add_argument("--year", type=int, help="列出该公历年的 24 节气")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    try:
        result = _calendar_result(args.date, args.lunar, args.leap, args.year)
    except Exception as exc:  # noqa: BLE001 - 统一转成信封
        return _error("calendar", "BAD_DATE", str(exc), args.json)

    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": "calendar",
        "engine": ENGINE,
        "input": {"date": args.date, "lunar": args.lunar, "leap": args.leap, "year": args.year},
        "result": result,
        "warnings": [],
        "seed": None,
    }
    text_lines = []
    if "solar" in result:
        lun = result["lunar"]
        text_lines.append("公历 %s（周%s）" % (result["solar"], result["weekday"]))
        text_lines.append(
            "农历 %s%s年%s%s（%s）"
            % (lun.get("year_cn", lun["year"]), "闰" if lun.get("leap") else "",
               lun.get("month_cn", lun["month"]), lun.get("day_cn", lun["day"]),
               "大月" if lun.get("big_month") else "小月")
        )
        gz = result["ganzhi"]
        text_lines.append("干支 %s年 %s月 %s日" % (gz["year"], gz["month"], gz["day"]))
        if result.get("jieqi_today"):
            text_lines.append("今日交节：%s" % result["jieqi_today"]["name"])
        text_lines.append("前一节气 %s %s ｜ 后一节气 %s %s" % (
            result["prev_jieqi"]["name"], result["prev_jieqi"]["datetime"],
            result["next_jieqi"]["name"], result["next_jieqi"]["datetime"],
        ))
    if "terms" in result:
        for t in result["terms"]:
            text_lines.append("%s  %s" % (t["datetime"], t["name"]))
    _emit(payload, args.json, "\n".join(text_lines))
    return 0


# --------------------------------------------------------------------------
# doctor：自检
# --------------------------------------------------------------------------

def _scan_third_party(path: str) -> list:
    """用 AST 扫出一个脚本里 import 的第三方（非标准库、非本项目）模块。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError) as exc:
        return ["<parse-error: %s>" % exc]
    bad = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相对导入
                continue
            names = [(node.module or "").split(".")[0]]
        for name in names:
            if not name or name in STDLIB_WHITELIST or name in LOCAL_MODULES:
                continue
            bad.append(name)
    return sorted(set(bad))


def _doctor(as_json: bool) -> int:
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
    modules = {}
    for cmd, modname in SUBCOMMANDS.items():
        if not modname:
            continue
        path = os.path.join(HERE, modname + ".py")
        info = {"present": os.path.exists(path), "importable": False, "lines": 0, "third_party": []}
        if info["present"]:
            with open(path, "r", encoding="utf-8") as fh:
                info["lines"] = sum(1 for _ in fh)
            info["third_party"] = _scan_third_party(path)
            try:
                importlib.import_module(modname)
                info["importable"] = True
            except Exception as exc:  # noqa: BLE001
                info["error"] = "%s: %s" % (type(exc).__name__, exc)
        modules[cmd] = info

    third_party = {}
    for f in files:
        bad = _scan_third_party(os.path.join(HERE, f))
        if bad:
            third_party[f] = bad

    payload = {
        "ok": not third_party,
        "schema_version": SCHEMA_VERSION,
        "cmd": "doctor",
        "engine": ENGINE,
        "result": {
            "python": sys.version.split()[0],
            "python_ok": sys.version_info >= (3, 9),
            "skill_dir": HERE,
            "modules": modules,
            "third_party_imports": third_party,
            "has_calendar_core": os.path.exists(os.path.join(HERE, "calendar_core.py")),
        },
        "warnings": [],
        "seed": None,
    }

    lines = ["钦天监自检 · engine=%s · python=%s" % (ENGINE, sys.version.split()[0])]
    lines.append("目录：%s" % HERE)
    for cmd, info in modules.items():
        state = "OK" if info.get("importable") else ("缺失" if not info["present"] else "导入失败")
        lines.append("  %-9s %-4s %5d 行 %s" % (cmd, state, info.get("lines", 0),
                                               info.get("error", "")))
    if third_party:
        lines.append("第三方依赖（应为空）：%s" % json.dumps(third_party, ensure_ascii=False))
    else:
        lines.append("第三方依赖：无（零依赖 ✅）")
    _emit(payload, as_json, "\n".join(lines))
    return 0 if payload["ok"] else 2


# --------------------------------------------------------------------------
# 分发
# --------------------------------------------------------------------------

def _normalize_json_flag(rest: list) -> list:
    """`--json` 允许写在子命令前后的任意位置：统一挪到最前面。

    背景：带二级子命令的模块（如 fengshui 的 feixing/day/zeri）常把 --json 定义在
    各子解析器上，写在子命令之后会被 argparse 拒绝。入口统一搬一次，模型就不用记位置。
    """
    if "--json" in rest:
        return ["--json"] + [x for x in rest if x != "--json"]
    return rest


def _dispatch(cmd: str, rest: list) -> int:
    rest = _normalize_json_flag(rest)
    modname = SUBCOMMANDS[cmd]
    path = os.path.join(HERE, modname + ".py")
    if not os.path.exists(path):
        return _error(cmd, "MODULE_MISSING",
                      "模块 %s 尚未安装（缺 %s.py）。已就绪的命令可继续使用。" % (cmd, modname),
                      "--json" in rest)
    try:
        module = importlib.import_module(modname)
    except Exception as exc:  # noqa: BLE001
        return _error(cmd, "MODULE_IMPORT_FAILED", "%s: %s" % (type(exc).__name__, exc),
                      "--json" in rest)
    if not hasattr(module, "main"):
        return _error(cmd, "MODULE_NO_MAIN", "模块 %s 没有 main() 入口" % modname, "--json" in rest)

    params = inspect.signature(module.main).parameters
    if params:
        return int(module.main(rest) or 0)
    # 兼容未接收 argv 的实现
    old = sys.argv
    try:
        sys.argv = [path] + list(rest)
        return int(module.main() or 0)
    finally:
        sys.argv = old


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `--json` 允许出现在子命令前后的任意位置：先摘出来，再统一塞回 rest 最前面。
    json_flag = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(__doc__ or "")
        return 0

    cmd = argv[0]
    rest = argv[1:]
    if json_flag:
        rest.insert(0, "--json")

    if cmd == "doctor":
        return _doctor("--json" in rest)
    if cmd == "calendar":
        return _cmd_calendar(rest)
    if cmd not in SUBCOMMANDS:
        return _error(cmd, "UNKNOWN_COMMAND",
                      "未知子命令 %r。可用：%s" % (cmd, ", ".join(SUBCOMMANDS)),
                      "--json" in rest)
    return _dispatch(cmd, rest)


if __name__ == "__main__":
    sys.exit(main())
