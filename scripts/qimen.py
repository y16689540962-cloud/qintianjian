#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钦天监 · 时家奇门遁甲排盘引擎（qimen）。

职责
    由公历时刻 + 时辰，排时家奇门盘：节气 -> 三元 -> 局数（阴阳遁）、地盘三奇六仪、
    天盘九星（含天盘干）、八门、八神、值符值使、旬首旬空。支持转盘（默认）与飞盘。

输入
    --solar YYYY-MM-DD | --lunar YYYY-M-D [--leap]
    --hour HH:MM | --shichen 子..亥       （时家奇门必须有时辰）
    [--pan 转盘|飞盘]  [--ju N]（覆盖自动定局）  [--ask 事由]
    [--longitude 经度]（给了就换算真太阳时）  [--json]

输出
    契约 §3 信封 + §6 qimen 字段：
    time / jieqi / yuan / ju{dun,number} / zhifu_star / zhishi_gate / palaces[9] / warnings

口径来源
    * 定局：拆补法。节气按**精确交节时刻**取当前所在节气（交节前算前一节气）；
      三元按**日符头**——日干支往前找最近的甲/己日，符头地支属子午卯酉=上元、
      寅申巳亥=中元、辰戌丑未=下元；局数查二十四节气三元局数表。
      阳遁：冬至起至芒种；阴遁：夏至起至大雪。
    * 地盘三奇六仪：戊己庚辛壬癸丁丙乙，阳遁自局数宫顺布九宫，阴遁逆布。
    * 值符 = 旬首（甲子戊/甲戌己/甲申庚/甲午辛/甲辰壬/甲寅癸）所临九星；
      值使 = 旬首所临八门。旬首落中五宫时，值符取天禽、值使寄坤二死门。
    * 转盘：九星、八门、八神均按洛书八宫环（1坎-8艮-3震-4巽-9离-2坤-7兑-6乾）
      刚性转动；阳遁顺行、阴遁逆行；中五无星无门，寄坤二。
      天盘值符星落"时干所在地盘宫"（时干为甲则用旬首所遁之仪）；
      天盘干随星走，即各星带本宫地盘之干。
    * 飞盘：九星按九宫**宫序**飞泊（可入中五宫，中五有天禽），八门八神按宫序
      飞泊且不入中五。飞盘与转盘在"谁飞谁转"上各派分歧较大，此处只取一种并在
      warnings 里标 SCHOOL_VARIANT。
    * 八神次序：值符、螣蛇、太阴、六合、白虎、玄武、九地、九天（阳顺阴逆）。

已知局限
    1) 只有时家奇门（按时刻起局），不含日家/月家/年家奇门。
    2) 定元用拆补法；置闰法在"超神接气"的日子可能差一元，已在 warnings 标注。
    3) 不含格局判词（十干克应、门迫、击刑等），只排盘不判事。
    4) --ask 只回显，不改变排盘结果。
    5) 真太阳时按经度时差 + 均时差近似，秒级误差。
    6) **中五宫是设计如此**：中宫寄坤二宫，不列九星、八门、八神，故 rot盤 的
       gong=5 星/门/神三字段恒为 null（飞盘另有星与神、仍无门）。下游不要当成缺失。

零第三方依赖，Python 3.9+，无全局可变状态。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from calendar_core import (  # noqa: E402
    BRANCHES,
    STEMS,
    DateError,
    ganzhi_day,
    ganzhi_hour,
    lunar_to_solar,
    prev_jieqi,
    shichen_of,
    solar_terms,
    true_solar_time,
)

try:                                  # 夏令时还原：内核 v2 起提供
    from calendar_core import resolve_clock  # noqa: F401
except ImportError:                   # 兼容旧内核：不修正，也不伪造警告
    resolve_clock = None


def _fix_clock(dt):
    """夏令时（1986–1991）钟表时 -> 标准时。返回 (dt, warnings, meta)。"""
    if resolve_clock is None:
        return dt, [], None
    fixed, warns, meta = resolve_clock(dt, "fix")
    return fixed, list(warns or []), meta


ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
CMD = "qimen"

# ---------------------------------------------------------------------------
# 常量表
# ---------------------------------------------------------------------------

GONG_DIRECTION = {1: "北", 2: "西南", 3: "东", 4: "东南", 5: "中宫",
                  6: "西北", 7: "西", 8: "东北", 9: "南"}
GONG_NAME = {1: "坎一宫", 2: "坤二宫", 3: "震三宫", 4: "巽四宫", 5: "中五宫",
             6: "乾六宫", 7: "兑七宫", 8: "艮八宫", 9: "离九宫"}

STAR_HOME = {1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽",
             6: "天心", 7: "天柱", 8: "天任", 9: "天英"}
STAR_HOME_INV = {v: k for k, v in STAR_HOME.items()}
GATE_HOME = {1: "休门", 2: "死门", 3: "伤门", 4: "杜门",
             6: "开门", 7: "惊门", 8: "生门", 9: "景门"}

DEITY_ORDER = ("值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天")

# 三奇六仪布地盘次序（六仪在前、三奇在后，通行次序）
YIQI_ORDER = "戊己庚辛壬癸丁丙乙"
XUN_YI = {"甲子": "戊", "甲戌": "己", "甲申": "庚",
          "甲午": "辛", "甲辰": "壬", "甲寅": "癸"}

ZHISHI_RULE = ("值使门行八宫环（1坎-8艮-3震-4巽-9离-2坤-7兑-6乾），数到中五宫跳过不数"
               "（即跳过中宫，八门不入中）；"
               "偏移 = 该时辰在旬内的序数（0 起），阳遁顺行、阴遁逆行。"
               "另有「九宫含中宫」的传承，走九宫会在同一时辰差一到两宫（SCHOOL_VARIANT:zhishi=ring8）")
ZHIFU_RULE = ("值符星落时干所在地盘宫（时干为甲则用旬首所遁之仪，旬首落中五则寄坤二）；"
              "天盘干随星走，即各星带本宫地盘之干（SCHOOL_VARIANT:zhifu=hour_stem）")
YUAN_RULE = ("定局用拆补法：节气按精确交节时刻取当前节气；三元按日符头（日干支前推至最近的"
             "甲/己日，符头地支子午卯酉=上元、寅申巳亥=中元、辰戌丑未=下元）。"
             "**不做超神接气置闰**，故与置闰法可能在超神接气处差一元（SCHOOL_VARIANT:yuan=chaibu）")
CENTER_RULE = "中五宫寄坤二宫：转盘不列九星、八门、八神（天盘干为空），只留地盘干"
SCHOOL_NOTES = (YUAN_RULE, ZHISHI_RULE, ZHIFU_RULE,
                "八神次序：值符、螣蛇、太阴、六合、白虎、玄武、九地、九天，阳遁顺行、阴遁逆行",
                CENTER_RULE,
                "飞盘：九星按九宫宫序飞泊（可入中五宫），八门八神同样按宫序但不入中五（流派口径）")

RING8 = (1, 8, 3, 4, 9, 2, 7, 6)      # 洛书八宫环（顺行）
HOUSE9 = (1, 2, 3, 4, 5, 6, 7, 8, 9)  # 九宫宫序（飞盘用）
GATE_PALACES9 = (1, 2, 3, 4, 6, 7, 8, 9)  # 八门所居八宫（宫序，不入中五）

YUAN = ("上元", "中元", "下元")
YUAN_BY_BRANCH = {}
for _b in ("子", "午", "卯", "酉"):
    YUAN_BY_BRANCH[_b] = "上元"
for _b in ("寅", "申", "巳", "亥"):
    YUAN_BY_BRANCH[_b] = "中元"
for _b in ("辰", "戌", "丑", "未"):
    YUAN_BY_BRANCH[_b] = "下元"

# 二十四节气三元局数表：(阴阳遁, (上元, 中元, 下元))
JU_TABLE = {
    "冬至": ("阳遁", (1, 7, 4)), "小寒": ("阳遁", (2, 8, 5)),
    "大寒": ("阳遁", (3, 9, 6)), "立春": ("阳遁", (8, 5, 2)),
    "雨水": ("阳遁", (9, 6, 3)), "惊蛰": ("阳遁", (1, 7, 4)),
    "春分": ("阳遁", (3, 9, 6)), "清明": ("阳遁", (4, 1, 7)),
    "谷雨": ("阳遁", (5, 2, 8)), "立夏": ("阳遁", (4, 1, 7)),
    "小满": ("阳遁", (5, 2, 8)), "芒种": ("阳遁", (6, 3, 9)),
    "夏至": ("阴遁", (9, 3, 6)), "小暑": ("阴遁", (8, 2, 5)),
    "大暑": ("阴遁", (7, 1, 4)), "立秋": ("阴遁", (2, 5, 8)),
    "处暑": ("阴遁", (1, 4, 7)), "白露": ("阴遁", (9, 3, 6)),
    "秋分": ("阴遁", (7, 1, 4)), "寒露": ("阴遁", (6, 9, 3)),
    "霜降": ("阴遁", (5, 8, 2)), "立冬": ("阴遁", (6, 9, 3)),
    "小雪": ("阴遁", (5, 8, 2)), "大雪": ("阴遁", (4, 7, 1)),
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def gz60(stem, branch) -> int:
    """干支在六十甲子中的序号（0=甲子）。"""
    si, bi = STEMS.index(stem), BRANCHES.index(branch)
    for i in range(60):
        if i % 10 == si and i % 12 == bi:
            return i
    raise ValueError("不存在的干支：%s%s" % (stem, branch))


def _term_before(dt) -> dict:
    """当前所在节气（交节时刻前算前一节气）。"""
    raw = dt.strftime("%Y-%m-%d %H:%M")
    try:
        term = prev_jieqi(dt)
        if term and term.get("datetime", "")[:16] <= raw:
            return term
    except Exception:  # noqa: BLE001  日历内核异常时退回自算
        pass
    best = None
    for y in (dt.year - 1, dt.year, dt.year + 1):
        try:
            for t in solar_terms(y):
                if t["datetime"][:16] <= raw:
                    if best is None or t["datetime"] > best["datetime"]:
                        best = t
        except Exception:  # noqa: BLE001
            continue
    if best is None:
        raise DateError("找不到 %s 所在节气" % raw)
    return best


def yuan_of_day(day_gz: str):
    """日符头定三元：往前找最近的甲/己日，看其地支。"""
    idx = gz60(day_gz[0], day_gz[1])
    fu_idx = idx - (idx % 5)
    fu_tou = STEMS[fu_idx % 10] + BRANCHES[fu_idx % 12]
    return YUAN_BY_BRANCH[fu_tou[1]], fu_tou


def ju_of(term_name: str, yuan: str):
    dun, nums = JU_TABLE[term_name]
    return dun, nums[YUAN.index(yuan)]


def earth_stems(ju_num: int, dun: str) -> dict:
    """地盘三奇六仪：戊己庚辛壬癸丁丙乙，阳遁顺布、阴遁逆布。"""
    step = 1 if dun == "阳遁" else -1
    out = {}
    for k, stem in enumerate(YIQI_ORDER):
        gong = ((ju_num - 1 + step * k) % 9) + 1
        out[gong] = stem
    return out


def xun_of(hour_gz: str):
    """时干支 -> (旬首, 旬首地支序号, 旬首六十甲子序号)。"""
    idx = gz60(hour_gz[0], hour_gz[1])
    start = (idx // 10) * 10
    return "甲" + BRANCHES[start % 12], start % 12, start


def kongwang(start: int):
    return BRANCHES[(start + 10) % 12], BRANCHES[(start + 11) % 12]


def _gong_of_stem(estems: dict, stem: str) -> int:
    for gong, s in estems.items():
        if s == stem:
            return gong
    raise ValueError("地盘上找不到天干 %s" % stem)


# ---------------------------------------------------------------------------
# 排盘
# ---------------------------------------------------------------------------

def qimen_pan(dt, pan="转盘", ju_override=None, ask=None, longitude=None):
    """排奇门盘。dt 为 datetime（钟表时），返回 (result, warnings)。

    时钟口径：先按 calendar_core.resolve_clock(dt, "fix") 把 1986–1991 夏令时
    钟表时还原为标准时（并带出 CLOCK_CHANGE），再按经度（若给）换算真太阳时。
    """
    warnings = []
    if pan not in ("转盘", "飞盘"):
        raise ValueError("--pan 只能是 转盘 或 飞盘，收到：%s" % pan)

    input_solar = dt.strftime("%Y-%m-%d %H:%M")
    dt, clock_warns, clock_meta = _fix_clock(dt)
    warnings.extend(clock_warns)
    solar_shift = None
    if longitude is not None:
        dt, solar_shift = true_solar_time(dt, float(longitude))

    day_gz_pair = ganzhi_day(dt)
    day_gz = day_gz_pair[0] + day_gz_pair[1]
    hour_gz_pair = ganzhi_hour(day_gz_pair[0], dt.hour, dt.minute)
    hour_gz = hour_gz_pair[0] + hour_gz_pair[1]
    sc = shichen_of(dt.hour, dt.minute)

    if dt.hour == 23:
        warnings.append({
            "code": "LATE_ZI",
            "message": "23 点属夜子时：日干支已按子初换日；"
                       "另有「夜子时归前一日」的流派（SCHOOL_VARIANT:late_zi）",
        })

    # --- 节气 / 三元 / 局数 ------------------------------------------------
    term = _term_before(dt)
    term_name = term["name"]
    yuan, fu_tou = yuan_of_day(day_gz)
    if ju_override is not None:
        try:
            ju_num = int(ju_override)
        except (TypeError, ValueError):
            raise ValueError("--ju 应为 1-9 的整数，收到：%s" % ju_override)
        if not 1 <= ju_num <= 9:
            raise ValueError("--ju 应为 1-9 的整数，收到：%s" % ju_override)
        dun = JU_TABLE[term_name][0]
        warnings.append({
            "code": "JU_OVERRIDE",
            "message": "用户指定 %d 局，覆盖按%s%s自动定出的 %d 局"
                       % (ju_num, term_name, yuan, JU_TABLE[term_name][1][YUAN.index(yuan)]),
        })
    else:
        dun, ju_num = ju_of(term_name, yuan)
    warnings.append({
        "code": "SCHOOL_VARIANT",
        "message": "奇门口径（三处流派分歧，均已选定一种）："
                   "① 定局用符头定元、不做置闰（SCHOOL_VARIANT:yuan=chaibu）；"
                   "② 值使门行八宫环、跳过中宫，不是九宫含中宫（SCHOOL_VARIANT:zhishi=ring8）；"
                   "③ 盘式 %s（SCHOOL_VARIANT:pan=%s）"
                   % (pan, "zhuanpan" if pan == "转盘" else "feipan"),
    })

    estems = earth_stems(ju_num, dun)
    sign = 1 if dun == "阳遁" else -1

    # --- 旬首 / 值符 / 值使 ------------------------------------------------
    xun_name, xun_branch_idx, xun_start = xun_of(hour_gz)
    xun_yi = XUN_YI[xun_name]
    zhifu_home = _gong_of_stem(estems, xun_yi)
    if zhifu_home == 5:
        zhifu_star = "天禽"
        zhishi_gate = "死门"
        warnings.append({
            "code": "CENTER_JIGONG",
            "message": "旬首之仪（%s）落中五宫：值符取天禽星、值使寄坤二宫死门"
                       % xun_yi,
        })
    else:
        zhifu_star = STAR_HOME[zhifu_home]
        zhishi_gate = GATE_HOME[zhifu_home]

    # 值符落宫：时干所在地盘宫（时干为甲则用旬首之仪）
    hour_stem = hour_gz[0]
    target_stem = xun_yi if hour_stem == "甲" else hour_stem
    target_gong = _gong_of_stem(estems, target_stem)
    if pan == "转盘" and target_gong == 5:
        warnings.append({
            "code": "CENTER_JIGONG",
            "message": "天盘值符所加之时干（%s）落中五宫，转盘寄坤二宫" % target_stem,
        })
        target_gong = 2

    # --- 转盘 --------------------------------------------------------------
    sky = {}       # gong -> {"star","sky_stem","gate","deity"}
    if pan == "转盘":
        star_seq = [STAR_HOME[g] for g in RING8]
        # 值符为天禽时寄坤二（与天芮同宫）
        zhifu_key = "天芮" if zhifu_star == "天禽" else zhifu_star
        k0 = star_seq.index(zhifu_key)
        land = RING8.index(target_gong)
        for i in range(8):
            star = star_seq[(k0 + i) % 8]
            gong = RING8[(land + sign * i) % 8]
            home = STAR_HOME_INV[star]
            entry = {"star": star, "sky_stem": estems[home],
                     "gate": None, "deity": None}
            if star == "天芮":
                entry["star_extra"] = "天禽"
                entry["sky_stem_extra"] = estems[5]
            sky[gong] = entry

        gate_seq = [GATE_HOME[g] for g in RING8]
        steps = (sc["index"] - xun_branch_idx) % 12
        gh = RING8.index(zhifu_home if zhifu_home != 5 else 2)
        gate_land = (gh + sign * steps) % 8
        kg = gate_seq.index(zhishi_gate)
        for i in range(8):
            gate = gate_seq[(kg + i) % 8]
            gong = RING8[(gate_land + sign * i) % 8]
            sky[gong]["gate"] = gate

        land_pos = RING8.index(target_gong)
        for i, deity in enumerate(DEITY_ORDER):
            gong = RING8[(land_pos + sign * i) % 8]
            sky[gong]["deity"] = deity
        zhishi_landing = RING8[gate_land]

    # --- 飞盘 --------------------------------------------------------------
    else:
        star_seq = [STAR_HOME[g] for g in HOUSE9]
        k0 = star_seq.index(zhifu_star)
        land = HOUSE9.index(target_gong)
        for i in range(9):
            star = star_seq[(k0 + i) % 9]
            gong = HOUSE9[(land + sign * i) % 9]
            home = STAR_HOME_INV[star]
            sky[gong] = {"star": star, "sky_stem": estems[home],
                         "gate": None, "deity": None}

        gate_seq = [GATE_HOME[g] for g in GATE_PALACES9]
        steps = (sc["index"] - xun_branch_idx) % 12
        gh = GATE_PALACES9.index(zhifu_home if zhifu_home != 5 else 2)
        gate_land = (gh + sign * steps) % 8
        kg = gate_seq.index(zhishi_gate)
        for i in range(8):
            gate = gate_seq[(kg + i) % 8]
            gong = GATE_PALACES9[(gate_land + sign * i) % 8]
            sky[gong]["gate"] = gate

        land_pos = HOUSE9.index(target_gong)
        for i, deity in enumerate(DEITY_ORDER):
            gong = HOUSE9[(land_pos + sign * i) % 9]
            sky[gong]["deity"] = deity
        zhishi_landing = GATE_PALACES9[gate_land]

    # --- 九宫输出 ----------------------------------------------------------
    palaces = []
    for gong in HOUSE9:
        info = sky.get(gong, {})
        is_center = gong == 5
        palaces.append({
            "gong": gong,
            "name": GONG_NAME[gong],
            "direction": GONG_DIRECTION[gong],
            "earth_stem": estems[gong],
            "sky_stem": info.get("sky_stem"),
            "star": info.get("star"),
            "gate": info.get("gate"),
            "deity": info.get("deity"),
            "is_center": is_center,
            "note": ("中五宫：仅地盘干，转盘寄坤二宫" if is_center and pan == "转盘"
                     else ("中五宫：飞盘有星有神、无门" if is_center else None)),
        })
        if info.get("star_extra"):
            palaces[-1]["star_extra"] = info["star_extra"]
            palaces[-1]["sky_stem_extra"] = info.get("sky_stem_extra")

    kw = kongwang(xun_start)
    term_dt = term.get("datetime")
    result = {
        "time": {
            "solar": dt.strftime("%Y-%m-%d %H:%M"),
            "input_solar": input_solar,
            "clock_fix": clock_meta,
            "true_solar_shift_seconds": solar_shift,
            "shichen": sc["branch"],
            "shichen_range": sc["range"],
            "day_ganzhi": day_gz,
            "hour_ganzhi": hour_gz,
            "late_zi": dt.hour == 23,
        },
        "jieqi": {
            "name": term_name,
            "datetime": term_dt,
            "days_into_term": _days_into(dt, term_dt),
            "dun": dun,
        },
        "yuan": yuan,
        "yuan_detail": {
            "fu_tou": fu_tou,
            "rule": "符头地支子午卯酉=上元，寅申巳亥=中元，辰戌丑未=下元",
            "term_ju_table": {"上元": JU_TABLE[term_name][1][0],
                              "中元": JU_TABLE[term_name][1][1],
                              "下元": JU_TABLE[term_name][1][2]},
        },
        "ju": {"dun": dun, "number": ju_num},
        "pan": pan,
        "zhifu_star": zhifu_star,
        "zhishi_gate": zhishi_gate,
        "zhifu_home_gong": zhifu_home,
        "zhifu_landing_gong": target_gong,
        "zhishi_landing_gong": zhishi_landing,
        "zhishi_steps": (sc["index"] - xun_branch_idx) % 12,
        "zhishi_rule": ZHISHI_RULE,
        "zhifu_rule": ZHIFU_RULE,
        "school_notes": list(SCHOOL_NOTES),
        "xunshou": xun_name,
        "xun_yi": xun_yi,
        "kongwang": list(kw),
        "earth_stems": {str(k): v for k, v in sorted(estems.items())},
        "palaces": palaces,
        "ask": ask,
        "warnings": warnings,
    }
    return result, warnings


def _days_into(dt, term_dt):
    if not term_dt:
        return None
    try:
        import datetime as _dt
        start = _dt.datetime.strptime(term_dt[:16], "%Y-%m-%d %H:%M")
        return round((dt - start).total_seconds() / 86400.0, 2)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 人类可读输出
# ---------------------------------------------------------------------------

def render_text(result) -> str:
    t = result["time"]
    lines = ["奇门遁甲（%s）· %s %s时（%s）"
             % (result["pan"], t["solar"], t["shichen"], t["shichen_range"])]
    lines.append("四柱：%s日 %s时｜旬首：%s（%s）｜旬空：%s%s"
                 % (t["day_ganzhi"], t["hour_ganzhi"], result["xunshou"],
                    result["xun_yi"], result["kongwang"][0], result["kongwang"][1]))
    lines.append("节气：%s（%s 交节，已过 %s 天）｜%s｜%s｜%d 局"
                 % (result["jieqi"]["name"], result["jieqi"]["datetime"],
                    result["jieqi"]["days_into_term"], result["ju"]["dun"],
                    result["yuan"], result["ju"]["number"]))
    lines.append("值符：%s（原宫 %s → 落 %s）｜值使：%s（落 %s）"
                 % (result["zhifu_star"], GONG_NAME[result["zhifu_home_gong"]],
                    GONG_NAME[result["zhifu_landing_gong"]], result["zhishi_gate"],
                    GONG_NAME[result["zhishi_landing_gong"]]))
    lines.append("")
    lines.append("| 宫位 | 方位 | 地盘干 | 天盘干 | 九星 | 八门 | 八神 |")
    lines.append("|---|---|---|---|---|---|---|")
    for p in result["palaces"]:
        star = p["star"] or "—"
        if p.get("star_extra"):
            star = "%s/%s" % (p["star"], p["star_extra"])
        sky_stem = p["sky_stem"] or "—"
        if p.get("sky_stem_extra"):
            sky_stem = "%s/%s" % (p["sky_stem"], p["sky_stem_extra"])
        lines.append("| %s | %s | %s | %s | %s | %s | %s |"
                     % (p["name"], p["direction"], p["earth_stem"], sky_stem,
                        star, p["gate"] or "—", p["deity"] or "—"))
    if result.get("ask"):
        lines.append("")
        lines.append("所问：%s" % result["ask"])
    for w in result.get("warnings") or []:
        lines.append("· [%s] %s" % (w["code"], w["message"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _emit(payload, as_json, text=""):
    if as_json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(text + "\n")


def _error(code, message, as_json):
    _emit({"ok": False, "schema_version": SCHEMA_VERSION, "cmd": CMD,
           "engine": ENGINE, "error": {"code": code, "message": message}},
          as_json, text="错误 [%s] %s" % (code, message))
    return 2


def build_parser():
    p = argparse.ArgumentParser(prog="qimen.py", description="钦天监 · 时家奇门排盘")
    p.add_argument("--solar", help="公历日期 YYYY-MM-DD")
    p.add_argument("--lunar", help="农历日期 YYYY-M-D")
    p.add_argument("--leap", action="store_true", help="农历闰月")
    p.add_argument("--hour", help="时刻 HH:MM（时家奇门必填）")
    p.add_argument("--shichen", help="时辰（子丑寅…亥）")
    p.add_argument("--pan", default="转盘", help="转盘（默认）| 飞盘")
    p.add_argument("--ju", help="指定局数 1-9（覆盖自动定局）")
    p.add_argument("--ask", help="所问事由（只回显）")
    p.add_argument("--longitude", type=float, help="经度（给了就换算真太阳时）")
    p.add_argument("--json", action="store_true", help="输出 JSON 信封")
    return p


def _parse_hour_str(raw):
    parts = str(raw).replace("：", ":").split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        raise ValueError("--hour 格式应为 HH:MM，收到：%s" % raw)
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        raise ValueError("--hour 超出范围：%s" % raw)
    return hour, minute


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.hour and args.shichen:
        return _error("BAD_INPUT", "--hour 与 --shichen 互斥", as_json)
    if not args.hour and not args.shichen:
        return _error("BAD_INPUT", "时家奇门必须给 --hour 或 --shichen", as_json)
    if not args.solar and not args.lunar:
        return _error("BAD_INPUT", "需要 --solar 或 --lunar 之一", as_json)

    try:
        import datetime as _dt
        if args.solar:
            y, m, d = [int(x) for x in str(args.solar).replace("/", "-").split("-")]
        else:
            parts = [int(x) for x in str(args.lunar).replace("/", "-").split("-")]
            if len(parts) != 3:
                raise ValueError("--lunar 格式应为 YYYY-M-D，收到：%s" % args.lunar)
            y, m, d = lunar_to_solar(parts[0], parts[1], parts[2], args.leap)
        if args.hour:
            hour, minute = _parse_hour_str(args.hour)
        else:
            if args.shichen not in BRANCHES:
                raise ValueError("--shichen 应为十二支之一，收到：%s" % args.shichen)
            hour = (BRANCHES.index(args.shichen) * 2 - 1) % 24
            minute = 0
        dt = _dt.datetime(y, m, d, hour, minute)
    except DateError as exc:
        return _error("BAD_DATE", str(exc), as_json)
    except ValueError as exc:
        msg = str(exc)
        code = "BAD_DATE" if ("日期" in msg or "不存在" in msg) else "BAD_INPUT"
        return _error(code, msg, as_json)

    try:
        result, warnings = qimen_pan(dt, pan=args.pan, ju_override=args.ju,
                                     ask=args.ask, longitude=args.longitude)
    except DateError as exc:
        return _error("BAD_DATE", str(exc), as_json)
    except ValueError as exc:
        return _error("BAD_INPUT", str(exc), as_json)

    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": {
            "solar": args.solar,
            "lunar": args.lunar,
            "hour": args.hour,
            "shichen": args.shichen,
            "pan": args.pan,
            "ju": args.ju,
            "ask": args.ask,
            "longitude": args.longitude,
        },
        "result": result,
        "warnings": warnings,
        "seed": None,
    }
    _emit(payload, as_json, text=render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
