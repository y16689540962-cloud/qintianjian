#!/usr/bin/env python3
"""钦天监 · 双人合婚关系计算。

职责：跑两份八字排盘，按传统关系表算出「日干 / 日支 / 年支」三层的合冲刑害，
      以及各自夫妻星的有无。**只算关系，不下吉凶判决**——吉凶由 `references/marriage.md`
      的解读框架结合现实信息给。

用法：
    python3 scripts/hehun.py --a-solar 1990-05-15 --a-hour 12:00 --a-sex 男 \
                             --b-solar 1992-08-03 --b-hour 09:20 --b-sex 女
    python3 scripts/hehun.py --a-solar 1990-05-15 --a-hour 12:00 --a-sex 男 \
                             --b-lunar 1992-06-05 --b-hour 09:20 --b-sex 女 --json

输出：统一信封（CONTRACT §3），result 内 relations 列表 + 计数 + 三层小结。

口径来源：
    - 天干五合、地支六合三合六冲六害相刑：子平通行表（pub）
    - 年支生肖合冲：民俗层（undated，仅供参考，不作判据）
    - 夫妻星：男看财、女看官（pb，《渊海子平》）

已知局限：
    - 不计算用神互补（需要旺衰判断，属解读层，脚本不做）
    - 不排对方紫微盘（需调用 ziwei.py，由模型按 marriage.md Step 3 另跑）
    - 对方信息未给全时，只能降级为单方分析

零第三方依赖，Python 3.9+。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

STEM_HE = {
    ("甲", "己"): "土", ("己", "甲"): "土",
    ("乙", "庚"): "金", ("庚", "乙"): "金",
    ("丙", "辛"): "水", ("辛", "丙"): "水",
    ("丁", "壬"): "木", ("壬", "丁"): "木",
    ("戊", "癸"): "火", ("癸", "戊"): "火",
}
STEM_CHONG = {("甲", "庚"), ("庚", "甲"), ("乙", "辛"), ("辛", "乙"),
              ("丙", "壬"), ("壬", "丙"), ("丁", "癸"), ("癸", "丁")}
STEM_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
STEM_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
STEM_WUXING = dict(zip(STEMS, ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]))

BRANCH_LIUHE = {
    frozenset(["子", "丑"]): ("土", "合而化土"),
    frozenset(["寅", "亥"]): ("木", "合而化木"),
    frozenset(["卯", "戌"]): ("火", "合而化火"),
    frozenset(["辰", "酉"]): ("金", "合而化金"),
    frozenset(["巳", "申"]): ("水", "合而化水"),
    frozenset(["午", "未"]): ("土", "合而化土"),
}
SANHE = [
    (frozenset(["申", "子", "辰"]), "水"),
    (frozenset(["亥", "卯", "未"]), "木"),
    (frozenset(["寅", "午", "戌"]), "火"),
    (frozenset(["巳", "酉", "丑"]), "金"),
]
LIUHAI = {frozenset(p) for p in [
    ("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]}
XING_GROUPS = [
    frozenset(["子", "卯"]),
    frozenset(["寅", "巳", "申"]),
    frozenset(["丑", "戌", "未"]),
]
SELF_XING = set("辰午酉亥")

BRANCH_WUXING = dict(zip(BRANCHES, ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]))

MEANINGS = {
    "stem_he": "日干相合：本体吸引强，容易一见如故；合而化某五行，说明这层吸引会带出对应的现实主题",
    "stem_chong": "日干相冲：本体性情相逆，观点容易对立，吵架时难收场",
    "stem_sheng": "日干相生：一方天然愿意付出，注意长期单向付出会积怨",
    "stem_ke": "日干相克：一方压制另一方，需明确谁的领域谁做主",
    "branch_he": "日支（夫妻宫）相合：共同生活的场域顺，同居磨合成本低",
    "branch_sanhe": "日支三合：有共同目标或共同圈子，容易因同一件事走到一起",
    "branch_chong": "日支相冲：生活节奏与习惯冲突明显，长期需靠规则而非忍让",
    "branch_hai": "日支相害：不是明吵，是细节上的彼此消耗（觉得不被领情/被挑剔）",
    "branch_xing": "日支相刑：纠缠型摩擦，容易翻旧账、互相改造对方",
    "branch_same": "日支相同：性情相近，好处是懂彼此，坏处是同时犯同一个错",
    "year_chong": "年支相冲（生肖六冲）：民俗层说法，仅作参考，不作判据",
    "year_he": "年支相合（生肖六合）：民俗层说法，仅作参考，不作判据",
}


def _run_bazi(args_prefix, parser_args) -> dict:
    """调用 bazi.py --json，返回解析后的信封。"""
    if args_prefix.get("solar"):
        cmd = [sys.executable, os.path.join(HERE, "bazi.py"), "--solar", args_prefix["solar"]]
    elif args_prefix.get("lunar"):
        cmd = [sys.executable, os.path.join(HERE, "bazi.py"), "--lunar", args_prefix["lunar"]]
    else:
        raise ValueError("需要公历或农历生日")
    if parser_args.hour:
        cmd += ["--hour", parser_args.hour]
    elif getattr(parser_args, "shichen", None):
        cmd += ["--shichen", parser_args.shichen]
    if args_prefix.get("sex"):
        cmd += ["--sex", args_prefix["sex"]]
    if args_prefix.get("place"):
        cmd += ["--place", args_prefix["place"]]
    cmd.append("--json")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("bazi.py 失败（%d）：%s" % (proc.returncode, (proc.stderr or proc.stdout)[:400]))
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError("bazi.py 返回 ok=false：%s" % payload.get("error"))
    return payload


def _pillar_stem(payload, name):
    p = (payload.get("result") or {}).get("pillars", {}).get(name)
    return p if p else None


def _stem_relation(a, b):
    rel = []
    if frozenset([a, b]) in {frozenset(k) for k in STEM_HE}:
        hua = STEM_HE[(a, b)]
        rel.append(("stem_he", hua))
    if (a, b) in STEM_CHONG:
        rel.append(("stem_chong", None))
    wa, wb = STEM_WUXING[a], STEM_WUXING[b]
    if STEM_SHENG.get(wa) == wb or STEM_SHENG.get(wb) == wa:
        rel.append(("stem_sheng", None))
    if STEM_KE.get(wa) == wb or STEM_KE.get(wb) == wa:
        rel.append(("stem_ke", None))
    if wa == wb and not rel:
        rel.append(("stem_same", None))
    return rel


def _branch_relation(a, b):
    rel = []
    key = frozenset([a, b])
    if key in BRANCH_LIUHE:
        rel.append(("branch_he", BRANCH_LIUHE[key][0]))
    for group, wx in SANHE:
        if a in group and b in group and a != b:
            rel.append(("branch_sanhe", wx))
            break
    ia, ib = BRANCHES.index(a), BRANCHES.index(b)
    if (ia - ib) % 12 == 6:
        rel.append(("branch_chong", None))
    if key in LIUHAI:
        rel.append(("branch_hai", None))
    for g in XING_GROUPS:
        if a in g and b in g and a != b:
            rel.append(("branch_xing", None))
            break
    if a == b and a in SELF_XING:
        rel.append(("branch_self_xing", None))
    if a == b:
        rel.append(("branch_same", None))
    return rel


def _summary(payload, label):
    res = payload.get("result") or {}
    pillars = res.get("pillars") or {}
    dm = res.get("day_master") or {}
    shensha = [s.get("name") for s in (res.get("shensha") or []) if isinstance(s, dict)]
    hour = pillars.get("hour")
    return {
        "label": label,
        "solar": payload.get("input", {}).get("solar"),
        "lunar": res.get("lunar"),
        "year_pillar": (pillars.get("year") or {}).get("ganzhi"),
        "day_pillar": (pillars.get("day") or {}).get("ganzhi"),
        "hour_known": hour is not None,
        "day_master": dm,
        "spouse_star": _spouse_star(dm.get("stem"), res, payload),
        "shensha": shensha,
        "warnings": [w.get("code") for w in (payload.get("warnings") or []) if isinstance(w, dict)],
    }


def _spouse_star(day_stem, res, payload):
    """男看财、女看官：从十神统计里取出夫妻星。"""
    sex = (payload.get("input") or {}).get("sex") or ""
    counts = res.get("shishen_count") or {}
    if not day_stem:
        return None
    if sex == "男":
        keys = ["正财", "偏财"]
        label = "财星（妻）"
    elif sex == "女":
        keys = ["正官", "七杀"]
        label = "官星（夫）"
    else:
        return None
    detail = {k: counts.get(k, 0) for k in keys}
    total = sum(detail.values())
    return {"label": label, "counts": detail, "total": total,
            "note": "无夫妻星" if total == 0 else ""}


def compute(a_payload, b_payload) -> dict:
    a_day = _pillar_stem(a_payload, "day")
    b_day = _pillar_stem(b_payload, "day")
    a_year = _pillar_stem(a_payload, "year")
    b_year = _pillar_stem(b_payload, "year")

    relations, warnings = [], []
    for p in (a_day, b_day):
        if not p:
            raise RuntimeError("bazi 输出缺日柱，无法合婚")

    a_stem, a_branch = a_day["stem"], a_day["branch"]
    b_stem, b_branch = b_day["stem"], b_day["branch"]

    for kind, hua in _stem_relation(a_stem, b_stem):
        relations.append({
            "level": "day_stem", "type": kind, "hua": hua,
            "pair": "%s%s" % (a_stem, b_stem),
            "meaning": MEANINGS.get(kind, ""),
            "status": "pub",
        })
    for kind, hua in _branch_relation(a_branch, b_branch):
        relations.append({
            "level": "day_branch", "type": kind, "hua": hua,
            "pair": "%s%s" % (a_branch, b_branch),
            "meaning": MEANINGS.get(kind, ""),
            "status": "pub",
        })

    if a_year and b_year:
        ay, by = a_year["branch"], b_year["branch"]
        iy, jy = BRANCHES.index(ay), BRANCHES.index(by)
        if (iy - jy) % 12 == 6:
            relations.append({"level": "year_branch", "type": "year_chong",
                              "pair": "%s%s" % (ay, by), "meaning": MEANINGS["year_chong"],
                              "status": "undated"})
        elif frozenset([ay, by]) in BRANCH_LIUHE:
            relations.append({"level": "year_branch", "type": "year_he",
                              "pair": "%s%s" % (ay, by), "meaning": MEANINGS["year_he"],
                              "status": "undated"})

    # 缺时辰提示
    for label, payload in (("甲", a_payload), ("乙", b_payload)):
        codes = [w.get("code") for w in (payload.get("warnings") or []) if isinstance(w, dict)]
        if "SHICHEN_UNKNOWN" in codes:
            warnings.append({"code": "SHICHEN_UNKNOWN",
                             "message": "%s方无时辰，仅用年月日六字参与合婚" % label})

    tally = {}
    for r in relations:
        tally[r["type"]] = tally.get(r["type"], 0) + 1

    return {
        "a": _summary(a_payload, "甲"),
        "b": _summary(b_payload, "乙"),
        "relations": relations,
        "tally": tally,
        "note": "tally 只是关系出现次数，不是吉凶评分；吉凶与取舍见 references/marriage.md §3/§5",
        "warnings": warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hehun.py", description="双人合婚关系计算")
    for who in ("a", "b"):
        parser.add_argument("--%s-solar" % who, help="%s 方公历生日 YYYY-MM-DD" % who.upper())
        parser.add_argument("--%s-lunar" % who, help="%s 方农历生日 YYYY-MM-DD" % who.upper())
        parser.add_argument("--%s-hour" % who, help="%s 方出生时刻 HH:MM" % who.upper())
        parser.add_argument("--%s-shichen" % who, help="%s 方时辰地支" % who.upper())
        parser.add_argument("--%s-sex" % who, choices=["男", "女"], help="%s 方性别" % who.upper())
        parser.add_argument("--%s-leap" % who, action="store_true", help="%s 方农历闰月" % who.upper())
        parser.add_argument("--%s-place" % who, default=None, help="%s 方出生地" % who.upper())
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    as_json = args.json
    try:
        if not (args.a_solar or args.a_lunar) or not (args.b_solar or args.b_lunar):
            raise ValueError("双方生日都要给（--a-solar/--a-lunar 与 --b-solar/--b-lunar）")
        for who in ("a", "b"):
            if not getattr(args, "%s_sex" % who):
                raise ValueError("双方性别都要给（%s 方缺 --%s-sex）" % (who.upper(), who))
        a_args = {"solar": args.a_solar, "lunar": args.a_lunar, "sex": args.a_sex, "place": args.a_place}
        b_args = {"solar": args.b_solar, "lunar": args.b_lunar, "sex": args.b_sex, "place": args.b_place}

        class _Holder:  # 临时容器：把 a/b 的 hour/shichen 分开传
            def __init__(self, hour, shichen):
                self.hour = hour
                self.shichen = shichen

        a_payload = _run_bazi(a_args, _Holder(args.a_hour, args.a_shichen))
        b_payload = _run_bazi(b_args, _Holder(args.b_hour, args.b_shichen))
        result = compute(a_payload, b_payload)
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        payload = {"ok": False, "schema_version": SCHEMA_VERSION, "cmd": "hehun",
                   "engine": ENGINE, "error": {"code": "HEHUN_ERROR", "message": str(exc)}}
        if as_json:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stdout.write("错误：%s\n" % exc)
        return 2

    payload = {
        "ok": True, "schema_version": SCHEMA_VERSION, "cmd": "hehun", "engine": ENGINE,
        "input": {"a": {k: getattr(args, "a_" + k) for k in ("solar", "lunar", "hour", "sex")},
                  "b": {k: getattr(args, "b_" + k) for k in ("solar", "lunar", "hour", "sex")}},
        "result": result,
        "warnings": result["warnings"],
        "seed": None,
    }

    lines = []
    lines.append("甲：%s  日柱 %s  夫妻星 %s" % (
        result["a"]["solar"], result["a"]["day_pillar"],
        (result["a"]["spouse_star"] or {}).get("label", "—")))
    lines.append("乙：%s  日柱 %s  夫妻星 %s" % (
        result["b"]["solar"], result["b"]["day_pillar"],
        (result["b"]["spouse_star"] or {}).get("label", "—")))
    lines.append("")
    for r in result["relations"]:
        lines.append("· [%s] %s %s%s" % (r["level"], r["pair"], r["type"],
                                        ("（化%s）" % r["hua"]) if r.get("hua") else ""))
        if r.get("meaning"):
            lines.append("    %s（%s）" % (r["meaning"], r["status"]))
    lines.append("")
    lines.append("计数：%s（不是吉凶评分）" % json.dumps(result["tally"], ensure_ascii=False))
    if result["warnings"]:
        lines.append("警告：%s" % "；".join(w["message"] for w in result["warnings"]))
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n" if as_json
                     else "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
