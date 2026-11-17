#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历法交叉核对：本仓 calendar_core vs lunar_python（**外部 oracle，不属本 skill 依赖**）。

为什么单独放一个文件
    `scripts/` 下的引擎是零第三方依赖的（`scripts/xuan.py doctor` 会扫 import 并报错）。
    这个脚本反过来：它必须借助外部实现当 oracle，才能证明我们的历法内核不是自说自话。
    所以它放在 `evals/evidence/`，只在"想复核的人"手里跑，不参与运行、不被 doctor 扫。

怎么重跑（联网装一次 oracle，之后离线可跑）
    python3 -m venv /tmp/oracle-venv
    /tmp/oracle-venv/bin/pip install lunar_python==1.4.9
    /tmp/oracle-venv/bin/python evals/evidence/calendar_cmp.py
    # 只跑一段： --start 1900-01-01 --end 1900-12-31

判定口径
    · 逐日比较「农历年/月/日 + 是否闰月」四元组，采样点为当日 12:00（北京时），
      避开子夜换日争议：月首争议单独看 `--verbose` 出来的差异清单。
    · 连续不一致的日期会被归并成"段"打印，一段通常就是一个争议月首（差一天）。
    · 已知历史结论：7 个月首与 lunar_python 差一天，全部经 JPL Horizons / USNO 月相
      API 双源仲裁，判定本实现正确——细节见 `calendar-vs-lunarpython.md`。

本脚本只读：不写文件、不联网、不修改仓库。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import calendar_core as cc  # noqa: E402  本项目引擎（零依赖）


def load_oracle():
    """取 lunar_python。缺了就明确报错，不做任何自动安装。"""
    try:
        from lunar_python import Solar  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "缺 oracle：lunar_python。\n"
            "本脚本需要一个外部实现做对照，请另建虚拟环境安装（不要装进本仓库）：\n"
            "  python3 -m venv /tmp/oracle-venv\n"
            "  /tmp/oracle-venv/bin/pip install lunar_python==1.4.9\n"
            "  /tmp/oracle-venv/bin/python evals/evidence/calendar_cmp.py\n"
            "注意：lunar_python 是本脚本的 oracle，**不是** qintianjian 的依赖。\n")
        raise SystemExit(2)
    return Solar


def merge_segments(dates):
    """把不连续日期合并成段：[(起, 止, 天数)]。"""
    if not dates:
        return []
    out = [[dates[0], dates[0]]]
    for x in dates[1:]:
        if (x - out[-1][1]).days <= 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [(a, b, (b - a).days + 1) for a, b in out]


def main(argv=None):
    p = argparse.ArgumentParser(description="calendar_core vs lunar_python 逐日农历比对")
    p.add_argument("--start", default="1850-01-01")
    p.add_argument("--end", default="2100-12-31")
    p.add_argument("--verbose", action="store_true", help="逐条打印前 40 条差异")
    args = p.parse_args(argv)

    Solar = load_oracle()
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("--end 早于 --start")

    bad = []          # [(date, oracle_tuple, ours_tuple)] 或 [(date, "ERR", msg)]
    checked = 0
    d = start
    while d <= end:
        solar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0)
        lunar = solar.getLunar()
        m = lunar.getMonth()
        oracle = (lunar.getYear(), abs(m), lunar.getDay(), bool(m < 0))
        try:
            ours_d = cc.solar_to_lunar(d.year, d.month, d.day)
            ours = (ours_d["year"], ours_d["month"], ours_d["day"], bool(ours_d["leap"]))
        except Exception as exc:  # 内核拒绝的日期（超区间）单独记
            bad.append((d, "ERR", str(exc)))
            d += dt.timedelta(days=1)
            continue
        if ours != oracle:
            bad.append((d, oracle, ours))
        checked += 1
        d += dt.timedelta(days=1)

    mismatch_days = [b[0] for b in bad if b[1] != "ERR"]
    err_days = [b for b in bad if b[1] == "ERR"]
    print("range: %s .. %s" % (start, end))
    print("checked: %d 天" % checked)
    print("mismatch: %d 天" % len(mismatch_days))
    print("kernel_error: %d 天" % len(err_days))
    for b in err_days[:10]:
        print("  ERR", b[0], b[2])
    if args.verbose:
        for b in bad[:40]:
            print("  ", b[0], "oracle=", b[1], "ours=", b[2])
    print("\n连续段（一段通常 = 一个有争议的月首）：")
    for a, b, n in merge_segments(mismatch_days):
        print("  %s ~ %s  共 %d 天" % (a, b, n))
    return 0 if not err_days else 1


if __name__ == "__main__":
    raise SystemExit(main())
