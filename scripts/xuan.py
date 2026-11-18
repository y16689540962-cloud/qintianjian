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
from importlib import util as importlib_util
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

# doctor 的判定素材：模块缺失、导入失败、历法内核失灵、第三方依赖、Python 版本，
# 任意一项失败都算不通过（v1.2 修：此前只有"第三方依赖"参与 ok）。
CALENDAR_PROBE = {"date": (1990, 5, 15), "lunar_month": 4, "lunar_day": 21, "day_ganzhi": "庚辰"}


def _check_python(python_version=None):
    """-> (ok, detail)。python_version 可注入，便于测试低版本行为。"""
    v = tuple(python_version or sys.version_info[:3])
    v = (v + (0, 0, 0))[:3]
    return v >= (3, 9), "Python %d.%d.%d（要求 ≥3.9）" % v


def _load_module(base_dir, modname):
    """从 base_dir 独立加载模块，不依赖 sys.modules 里可能存在的别处副本。

    返回 (module, error)。用唯一模块名加载，加载后清理，避免污染进程状态。
    """
    path = os.path.join(base_dir, modname + ".py")
    unique = "_qxd_%s_%d" % (modname, os.getpid())
    sys.path.insert(0, base_dir)
    try:
        spec = importlib_util.spec_from_file_location(unique, path)
        if spec is None or spec.loader is None:
            return None, "无法为 %s 建立加载器" % path
        module = importlib_util.module_from_spec(spec)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return module, None
    except Exception as exc:  # noqa: BLE001 - 自检要把任何异常变成一条可读原因
        return None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        sys.path.remove(base_dir)
        sys.modules.pop(unique, None)


def _check_calendar(base_dir):
    """历法内核不只是"文件存在"：真算一组已知答案。只调用现有 API，不改历法逻辑。"""
    module, err = _load_module(base_dir, "calendar_core")
    if err:
        return False, "calendar_core 无法加载：%s" % err
    try:
        import datetime as _dt
        lunar = module.solar_to_lunar(*CALENDAR_PROBE["date"])
        stem, branch = module.ganzhi_day(_dt.datetime(1990, 5, 15, 12, 0))
        got = {"month": lunar.get("month"), "day": lunar.get("day"), "ganzhi": stem + branch}
        want = {"month": CALENDAR_PROBE["lunar_month"], "day": CALENDAR_PROBE["lunar_day"],
                "ganzhi": CALENDAR_PROBE["day_ganzhi"]}
        if got != want:
            return False, "历法抽查不符：期望 %s，实际 %s" % (want, got)
        return True, "1990-05-15 → 农历%d月%d日 / %s" % (
            got["month"], got["day"], got["ganzhi"])
    except Exception as exc:  # noqa: BLE001
        return False, "历法抽查抛错：%s: %s" % (type(exc).__name__, exc)


def diagnose(base_dir=None, python_version=None):
    """自检的纯函数版本：不做 I/O 输出，返回结构化结果，便于测试与复用。

    ok 为 True 要求：Python 版本达标 + 全部必需模块存在且可加载 + 历法内核抽查通过 + 零第三方依赖。
    """
    base_dir = base_dir or HERE
    failures, checks, modules = [], {}, {}

    py_ok, py_detail = _check_python(python_version)
    checks["python"] = {"ok": py_ok, "detail": py_detail}
    if not py_ok:
        failures.append({"check": "python", "detail": py_detail})

    for cmd, modname in SUBCOMMANDS.items():
        if not modname:
            continue
        path = os.path.join(base_dir, modname + ".py")
        info = {"present": os.path.exists(path), "importable": False, "lines": 0}
        if info["present"]:
            with open(path, "r", encoding="utf-8") as fh:
                info["lines"] = sum(1 for _ in fh)
            _mod, err = _load_module(base_dir, modname)
            info["importable"] = err is None
            if err:
                info["error"] = err
                failures.append({"check": "module:%s" % modname, "detail": err})
        else:
            failures.append({"check": "module:%s" % modname,
                             "detail": "缺少 %s.py（目录：%s）" % (modname, base_dir)})
        modules[cmd] = info
    checks["modules"] = {"ok": not any(not i["present"] or not i["importable"]
                                       for i in modules.values()),
                         "detail": "%d 个模块" % len(modules)}

    cal_ok, cal_detail = _check_calendar(base_dir)
    checks["calendar"] = {"ok": cal_ok, "detail": cal_detail}
    if not cal_ok:
        failures.append({"check": "calendar", "detail": cal_detail})

    files = sorted(f for f in os.listdir(base_dir) if f.endswith(".py"))
    third_party = {}
    for f in files:
        bad = _scan_third_party(os.path.join(base_dir, f))
        if bad:
            third_party[f] = bad
    checks["third_party"] = {"ok": not third_party,
                             "detail": "无" if not third_party else json.dumps(third_party, ensure_ascii=False)}
    if third_party:
        failures.append({"check": "third_party",
                         "detail": "发现第三方依赖：%s" % json.dumps(third_party, ensure_ascii=False)})

    return {"ok": not failures, "failures": failures, "checks": checks,
            "modules": modules, "third_party_imports": third_party,
            "has_calendar_core": os.path.exists(os.path.join(base_dir, "calendar_core.py")),
            "python": sys.version.split()[0], "python_ok": py_ok, "base_dir": base_dir}



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
        try:
            base_dt = cc.datetime(y, m, d, 12, 0)
        except ValueError:
            raise ValueError("日期不存在：%04d-%02d-%02d" % (y, m, d))
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
    report = diagnose()
    payload = {
        "ok": report["ok"],
        "schema_version": SCHEMA_VERSION,
        "cmd": "doctor",
        "engine": ENGINE,
        "result": {
            "python": report["python"],
            "python_ok": report["python_ok"],
            "skill_dir": report["base_dir"],
            "checks": report["checks"],
            "modules": report["modules"],
            "third_party_imports": report["third_party_imports"],
            "has_calendar_core": report["has_calendar_core"],
            "failures": report["failures"],
        },
        "warnings": [],
        "seed": None,
    }

    lines = ["钦天监自检 · engine=%s · python=%s" % (ENGINE, report["python"])]
    lines.append("目录：%s" % report["base_dir"])
    for name, chk in report["checks"].items():
        lines.append("  [%s] %-12s %s" % ("OK" if chk["ok"] else "FAIL", name, chk["detail"]))
    for cmd, info in report["modules"].items():
        state = "OK" if info.get("importable") else ("缺失" if not info["present"] else "导入失败")
        lines.append("  %-9s %-4s %5d 行 %s" % (cmd, state, info.get("lines", 0),
                                               info.get("error", "")))
    if report["failures"]:
        lines.append("失败原因（%d 项）：" % len(report["failures"]))
        for f in report["failures"]:
            lines.append("  - %s：%s" % (f["check"], f["detail"]))
    else:
        lines.append("结论：全部检查通过，零第三方依赖。")
    _emit(payload, as_json, "\n".join(lines))
    return 0 if report["ok"] else 2


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
