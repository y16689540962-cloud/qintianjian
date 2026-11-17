#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钦天监 · 紫微斗数排盘引擎（ziwei）。

职责
    由公历/农历生日 + 时辰 + 性别，排出紫微斗数本命盘：十二宫、命宫、身宫、
    五行局、十四主星、主要辅星与煞曜、生年四化、大限；给 `--liunian` 时再出流年盘。

输入
    --solar YYYY-MM-DD | --lunar YYYY-M-D [--leap]
    --hour HH:MM | --shichen 子..亥（二者互斥；都不给 -> 时柱未知，只出六字级信息）
    --sex 男|女（必填）
    [--place 地名] [--longitude 经度]  给了经度就换算真太阳时
    [--liunian N] [--dayun-n N] [--json]

输出
    契约 §3 信封 + §6 ziwei 字段：
    lunar / ming_gong / shen_gong / wuxing_ju / yin_yang / palaces[12] /
    daxian[] / liunian / sihua_year / warnings

口径来源
    * 命宫：寅起正月顺数至生月，再自该宫起子时逆数至生时；身宫同起点顺数。
    * 五行局：命宫干支纳音 -> 水二局/木三局/金四局/土五局/火六局（「纳音五行局」）。
    * 紫微星：以局数除日数取商、以借数奇逆偶顺定紫微（《紫微斗数全书》定紫微诀）。
    * 十四主星：紫微系逆行（机1/阳3/武4/同5/廉8），天府系顺行（阴1/贪2/巨3/相4/梁5/杀6/破10）。
    * 生年四化：取现代排盘通行本（见 SI_HUA）。逐干核对《紫微斗数全书》卷二四化诀：
      甲–辛、癸 与原文一致；**壬干为已知偏离**——原文作「天府化科」，本实现取现代通行的
      左辅化科（与 iztro 一致）。庚干化科/戊干化科另有异说。全部差异走
      warnings.SCHOOL_VARIANT 与 result.sihua_year.variant_note 显式写出，不静默。
    * 时钟：出生时刻若是 1986–1991 中国夏令时的钟表读数，按
      calendar_core.resolve_clock(dt, "fix") 先 −1 小时还原标准时，并必发 CLOCK_CHANGE
      （口径 = fix，准确性优先；否则同一人会被八字/紫微判成两个时辰）。
    * 年干支：以农历年（正月初一）为界，与八字的立春分界不同；这是紫微通行口径。
    * 闰月：初一至十五算本月，十六以后算次月（**折中口径**：《全书》卷二「閏月正月生者
      要在二月內起安身命」作整月按下月；本实现与 iztro fixLeap=true 一致）。

校验状态
    * 命宫/身宫/五行局/命主/身主/十二宫名/宫干/十四主星集合/庙旺/生年四化/主要辅星/
      大限区间：与 iztro 2.6.2（MIT）逐字段交叉核对，546 盘 0 差异（1900–2036、闰月、
      立春与春节前后、23 点夜子时；iztro 在 /tmp 临时 npm 跑，未 import、未进本仓）。
    * 流年宫位与流年四化：**无外部 oracle**，按规则实现（流年命宫 = 该年地支宫，
      流年四化 = 该年干四化），仅本仓测试覆盖。
    * 未实现：流月/流日/流时盘、飞星四化、小限、长生十二神。

已知局限
    1) 仅本命盘 + 流年宫位，不含流月/流日/流时盘，不含飞星四化、小限、长生十二神。
    2) 庙旺表为通行表（流派口径），辅星不给庙旺（brightness 恒为 null）。
    3) 时辰缺失时不给命宫/五行局/星曜（不猜），只回农历与四化表。
    4) 真太阳时只按经度时差 + 均时差（近似公式），未做海拔/大气折射修正。

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
    shichen_of,
    solar_to_lunar,
    true_solar_time,
)

try:                                  # 夏令时还原：内核 v2 起提供
    from calendar_core import resolve_clock  # noqa: F401
except ImportError:                   # 兼容旧内核：不修正，也不伪造警告
    resolve_clock = None


def _make_dt(y, m, d, h, mi):
    """构造 datetime；非法日期统一转成 DateError（供信封 BAD_DATE）。"""
    import datetime as _dt
    try:
        return _dt.datetime(y, m, d, h, mi)
    except ValueError as exc:
        raise DateError("%04d-%02d-%02d %02d:%02d 不存在：%s"
                        % (y, m, d, h, mi, exc))


def _fix_clock(dt):
    """夏令时（1986–1991）钟表时 -> 标准时。返回 (dt, warnings, meta)。"""
    if resolve_clock is None:
        return dt, [], None
    fixed, warns, meta = resolve_clock(dt, "fix")
    return fixed, list(warns or []), meta

ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
CMD = "ziwei"

# ---------------------------------------------------------------------------
# 常量表
# ---------------------------------------------------------------------------

PALACE_NAMES = ("命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                "迁移", "交友", "官禄", "田宅", "福德", "父母")

SHICHEN_NAMES = BRANCHES

# 五虎遁：年干 -> 寅宫天干
TIGER_STEM = {
    "甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
    "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲",
}

# 六十甲子纳音五行（每两个干支一组，共 30 组；下标 = 六十甲子序 // 2）
NAYIN_ELEMENT = (
    "金", "火", "木", "土", "金", "火", "水", "土", "金", "木",
    "水", "土", "火", "木", "水", "金", "火", "木", "土", "金",
    "火", "水", "土", "金", "木", "水", "土", "火", "木", "水",
)

# 纳音五行 -> 五行局
JU_BY_ELEMENT = {"水": ("水二局", 2), "木": ("木三局", 3), "金": ("金四局", 4),
                 "土": ("土五局", 5), "火": ("火六局", 6)}

# 生年四化：现代排盘通行本（与 iztro 2.6.2 一致）。
# 与《紫微斗数全书》卷二四化诀逐干核对：甲–辛、癸 均同原文；
# **壬干有已知偏离**——原文「壬梁紫府武」= 天府化科，本实现取现代通行的 左辅化科。
# 其余异说：庚干化科（本派太阴科/天同忌，另一说天同科/太阴忌）、戊干化科（本派右弼/另一说太阳）。
SI_HUA = {
    "甲": ("廉贞", "破军", "武曲", "太阳"),
    "乙": ("天机", "天梁", "紫微", "太阴"),
    "丙": ("天同", "天机", "文昌", "廉贞"),
    "丁": ("太阴", "天同", "天机", "巨门"),
    "戊": ("贪狼", "太阴", "右弼", "天机"),
    "己": ("武曲", "贪狼", "天梁", "文曲"),
    "庚": ("太阳", "武曲", "太阴", "天同"),
    "辛": ("巨门", "太阳", "文曲", "文昌"),
    "壬": ("天梁", "紫微", "左辅", "武曲"),
    "癸": ("破军", "巨门", "太阴", "贪狼"),
}
SI_HUA_KINDS = ("禄", "权", "科", "忌")

# 十四主星庙旺表：键为星名，值为 12 字串，按 子丑寅卯辰巳午未申酉戌亥 排列
BRIGHTNESS = {
    "紫微": "平庙旺旺得旺庙庙旺旺得旺",
    "天机": "庙陷得旺利平庙陷得旺利平",
    "太阳": "陷不旺庙旺旺旺得得平不陷",
    "武曲": "旺庙得利庙平旺庙得利庙平",
    "天同": "旺不利平平庙陷不旺平平庙",
    "廉贞": "平利庙平利陷平利庙平利陷",
    "天府": "庙庙庙得庙得旺庙得旺庙得",
    "太阴": "庙庙旺陷陷陷不不利旺旺庙",
    "贪狼": "旺庙平利庙陷旺庙平利庙陷",
    "巨门": "旺不庙庙陷旺旺不庙庙陷旺",
    "天相": "庙庙庙陷得得庙得庙陷得得",
    "天梁": "庙旺庙庙庙陷庙旺陷得庙陷",
    "七杀": "旺庙庙旺庙平旺庙庙旺庙平",
    "破军": "庙旺得陷旺平庙旺得陷旺平",
}

MAJOR_STARS = ("紫微", "天机", "太阳", "武曲", "天同", "廉贞",
               "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军")

# 紫微系（逆行偏移，相对紫微）
ZIWEI_SERIES = (("天机", -1), ("太阳", -3), ("武曲", -4), ("天同", -5), ("廉贞", -8))
# 天府系（顺行偏移，相对天府）
TIANFU_SERIES = (("太阴", 1), ("贪狼", 2), ("巨门", 3), ("天相", 4),
                 ("天梁", 5), ("七杀", 6), ("破军", 10))

# 禄存（年干 -> 宫位）
LUCUN_BY_STEM = {"甲": 2, "乙": 3, "丙": 5, "丁": 6, "戊": 5,
                 "己": 6, "庚": 8, "辛": 9, "壬": 11, "癸": 0}
# 天魁/天钺（年干 -> (魁, 钺)）
KUICHEN_BY_STEM = {"甲": (1, 7), "戊": (1, 7), "庚": (1, 7),
                   "乙": (0, 8), "己": (0, 8),
                   "丙": (11, 9), "丁": (11, 9),
                   "辛": (6, 2),
                   "壬": (3, 5), "癸": (3, 5)}

# 年支三分局：寅午戌 / 申子辰 / 巳酉丑 / 亥卯未
_GROUP = {}
for _b in (2, 6, 10):
    _GROUP[_b] = "寅午戌"
for _b in (8, 0, 4):
    _GROUP[_b] = "申子辰"
for _b in (5, 9, 1):
    _GROUP[_b] = "巳酉丑"
for _b in (11, 3, 7):
    _GROUP[_b] = "亥卯未"

HUOXING_START = {"寅午戌": 1, "申子辰": 2, "巳酉丑": 3, "亥卯未": 9}   # 丑/寅/卯/酉
LINGXING_START = {"寅午戌": 3, "申子辰": 10, "巳酉丑": 10, "亥卯未": 10}  # 卯/戌
TIANMA_BY_GROUP = {"寅午戌": 8, "申子辰": 2, "巳酉丑": 11, "亥卯未": 5}   # 申/寅/亥/巳

MING_ZHU = {0: "贪狼", 1: "巨门", 11: "巨门", 2: "禄存", 10: "禄存",
            3: "文曲", 9: "文曲", 4: "廉贞", 8: "廉贞", 5: "武曲",
            7: "武曲", 6: "破军"}
# 身主按年支（子午/丑未/寅申/卯酉/辰戌/巳亥 六冲为对）
SHEN_ZHU_BY_BRANCH = ("火星", "天相", "天梁", "天同", "文昌", "天机",
                      "火星", "天相", "天梁", "天同", "文昌", "天机")

STAR_TYPE = {}
for _n in MAJOR_STARS:
    STAR_TYPE[_n] = "主星"
for _n in ("左辅", "右弼", "文昌", "文曲", "天魁", "天钺", "禄存", "天马"):
    STAR_TYPE[_n] = "辅星"
for _n in ("擎羊", "陀罗", "火星", "铃星", "地空", "地劫"):
    STAR_TYPE[_n] = "煞星"
for _n in ("天刑", "天姚", "红鸾", "天喜"):
    STAR_TYPE[_n] = "杂曜"

YANG_STEMS = "甲丙戊庚壬"

SCHOOL_NOTES = (
    "时钟：1986–1991 中国夏令时的钟表读数按 resolve_clock(\"fix\") −1 小时还原标准时，"
    "并必发 CLOCK_CHANGE（口径 = fix，准确性优先）",
    "年干支以农历年（正月初一）为界，与八字的立春分界不同（SCHOOL_VARIANT:year_divide=lunar_new_year）",
    "生年四化取现代排盘通行本：甲–辛、癸 同《紫微斗数全书》卷二四化诀；"
    "壬干取左辅化科，原文作「壬梁紫府武」（天府化科），属已知偏离"
    "（SCHOOL_VARIANT:sihua=ren_zuofu_deviation）；庚干化科（太阴科/天同忌）、"
    "戊干化科（右弼）另有异说（SCHOOL_VARIANT:sihua=geng_wu）",
    "闰月：初一至十五算本月、十六以后算次月（折中口径；原文作整月按下月，"
    "SCHOOL_VARIANT:leap_month=split_15）",
    "夜子时（23:00-23:59）：子初换日，农历日期推进到次日再起盘"
    "（SCHOOL_VARIANT:late_zi=next_day）",
    "庙旺七级（庙/旺/得/利/平/不/陷）为通行表，流派口径；辅星不给庙旺（brightness=null）",
    "大限：五行局数起运，每宫十年，阳男阴女顺行、阴男阳女逆行",
)


# ---------------------------------------------------------------------------
# 基础换算
# ---------------------------------------------------------------------------

def _gz_index(stem: str, branch: str) -> int:
    """干支在六十甲子中的序号（0=甲子）。"""
    si = STEMS.index(stem)
    bi = BRANCHES.index(branch)
    for i in range(60):
        if i % 10 == si and i % 12 == bi:
            return i
    raise ValueError("不存在的干支：%s%s" % (stem, branch))


def ganzhi_of_index(idx: int) -> str:
    idx %= 60
    return STEMS[idx % 10] + BRANCHES[idx % 12]


def nayin_element(stem: str, branch: str) -> str:
    return NAYIN_ELEMENT[_gz_index(stem, branch) // 2]


def year_ganzhi_of_lunar_year(lunar_year: int) -> str:
    """农历年 -> 年干支（以正月初一为界，紫微通行口径）。"""
    return STEMS[(lunar_year - 4) % 10] + BRANCHES[(lunar_year - 4) % 12]


def palace_stem(year_stem: str, branch_index: int) -> str:
    """五虎遁：年干定寅宫天干，再顺行布十二宫天干。"""
    tiger = STEMS.index(TIGER_STEM[year_stem])
    offset = (branch_index - 2) % 12          # 寅=0，顺行；子/丑 取模回到 10/11
    return STEMS[(tiger + offset) % 10]


def ming_gong_index(month: int, hour_index: int) -> int:
    """命宫：寅起正月顺数至生月，再自该宫起子时逆数至生时。"""
    month_palace = (2 + month - 1) % 12
    return (month_palace - hour_index) % 12


def shen_gong_index(month: int, hour_index: int) -> int:
    """身宫：起点同命宫，自子时顺数至生时。"""
    month_palace = (2 + month - 1) % 12
    return (month_palace + hour_index) % 12


def wuxing_ju(ming_gan: str, ming_zhi: str):
    """五行局：命宫干支纳音 -> (名, 数, 五行)。"""
    elem = nayin_element(ming_gan, ming_zhi)
    name, num = JU_BY_ELEMENT[elem]
    return name, num, elem


def ziwei_branch(ju_num: int, lunar_day: int) -> int:
    """紫微星定位：局数除日数取商，借数奇则逆退、偶则顺进。"""
    quotient = -(-lunar_day // ju_num)          # ceil(日 / 局)
    borrow = ju_num * quotient - lunar_day      # 借数
    pos = 2 + (quotient - 1)                    # 从寅宫起（寅=第 1 位）
    if borrow % 2 == 1:
        pos -= borrow
    else:
        pos += borrow
    return pos % 12


def _apply_sihua(stars, year_stem):
    mapping = {star: kind for kind, star in zip(SI_HUA_KINDS, SI_HUA[year_stem])}
    for star in stars:
        if star["name"] in mapping:
            star["sihua"] = mapping[star["name"]]
    return mapping


def _add(star_map, branch, name):
    star_map[branch].append({"name": name,
                             "type": STAR_TYPE.get(name, "杂曜"),
                             "brightness": None,
                             "sihua": None})


def build_star_map(year_stem, year_branch_idx, month, day, hour_index):
    """返回 {宫位地支序号: [星 dict, ...]}，含十四主星与主要辅星/煞曜。"""
    star_map = {i: [] for i in range(12)}
    ming = ming_gong_index(month, hour_index)
    ming_stem = palace_stem(year_stem, ming)
    _, ju_num, _elem = wuxing_ju(ming_stem, BRANCHES[ming])

    zw = ziwei_branch(ju_num, day)
    tf = (4 - zw) % 12          # 天府与紫微以寅申为轴对称
    _add(star_map, zw, "紫微")
    for name, off in ZIWEI_SERIES:
        _add(star_map, (zw + off) % 12, name)
    _add(star_map, tf, "天府")
    for name, off in TIANFU_SERIES:
        _add(star_map, (tf + off) % 12, name)

    # 月系
    _add(star_map, (4 + month - 1) % 12, "左辅")
    _add(star_map, (10 - (month - 1)) % 12, "右弼")
    _add(star_map, (9 + month - 1) % 12, "天刑")
    _add(star_map, (1 + month - 1) % 12, "天姚")
    # 时系
    _add(star_map, (10 - hour_index) % 12, "文昌")
    _add(star_map, (4 + hour_index) % 12, "文曲")
    _add(star_map, (11 + hour_index) % 12, "地劫")
    _add(star_map, (11 - hour_index) % 12, "地空")
    # 年干系
    lucun = LUCUN_BY_STEM[year_stem]
    _add(star_map, lucun, "禄存")
    _add(star_map, (lucun + 1) % 12, "擎羊")
    _add(star_map, (lucun - 1) % 12, "陀罗")
    kui, yue = KUICHEN_BY_STEM[year_stem]
    _add(star_map, kui, "天魁")
    _add(star_map, yue, "天钺")
    # 年支系
    group = _GROUP[year_branch_idx]
    _add(star_map, (HUOXING_START[group] + hour_index) % 12, "火星")
    _add(star_map, (LINGXING_START[group] + hour_index) % 12, "铃星")
    _add(star_map, TIANMA_BY_GROUP[group], "天马")
    _add(star_map, (3 - year_branch_idx) % 12, "红鸾")
    _add(star_map, (3 - year_branch_idx + 6) % 12, "天喜")

    # 主星补庙旺；同宫内主星按固定次序排列（紫微系在前）
    order = {n: i for i, n in enumerate(MAJOR_STARS)}
    for b, lst in star_map.items():
        for star in lst:
            if star["type"] == "主星":
                star["brightness"] = BRIGHTNESS[star["name"]][b]
        lst.sort(key=lambda s: (0 if s["type"] == "主星" else 1,
                                order.get(s["name"], 99), s["name"]))
    _apply_sihua([s for lst in star_map.values() for s in lst], year_stem)
    return star_map, ju_num, ming


# ---------------------------------------------------------------------------
# 排盘主流程
# ---------------------------------------------------------------------------

def _parse_hour(hour_str=None, shichen=None):
    """-> (hour:int, minute:int, None) 或 (None, None, warning dict)。"""
    if hour_str:
        raw = str(hour_str).strip().replace("：", ":")
        parts = raw.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            raise ValueError("--hour 格式应为 HH:MM，收到：%s" % hour_str)
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ValueError("--hour 超出范围：%s" % hour_str)
        return hour, minute, None
    if shichen:
        name = str(shichen).strip()
        if name not in BRANCHES:
            raise ValueError("--shichen 应为十二支之一，收到：%s" % shichen)
        idx = BRANCHES.index(name)
        hour = (idx * 2 - 1) % 24
        return hour, 0, None
    return None, None, {
        "code": "SHICHEN_UNKNOWN",
        "message": "未给 --hour/--shichen，紫微排盘缺时辰，只出农历与四化表",
    }


def ziwei_chart(solar=None, lunar=None, leap=False, hour=None, minute=0,
                shichen=None, sex="男", longitude=None, place=None,
                liunian=None, dayun_n=None, true_solar=False):
    """排出紫微斗数本命盘（可含流年），返回 (result, warnings)。"""
    warnings = []
    time_resolution = {}

    # --- 1. 日期换算（先定公历日，晚子时再按子初换日） ---------------------
    if solar:
        try:
            y, m, d = [int(x) for x in str(solar).replace("/", "-").split("-")]
        except ValueError:
            raise ValueError("--solar 格式应为 YYYY-MM-DD，收到：%s" % solar)
        lunar_given = False
    elif lunar:
        try:
            parts = [int(x) for x in str(lunar).replace("/", "-").split("-")]
        except ValueError:
            raise ValueError("--lunar 格式应为 YYYY-M-D，收到：%s" % lunar)
        if len(parts) != 3:
            raise ValueError("--lunar 格式应为 YYYY-M-D，收到：%s" % lunar)
        ly, lm, ld = parts
        from calendar_core import lunar_to_solar
        y, m, d = lunar_to_solar(ly, lm, ld, leap)
        lunar_given = True
    else:
        raise ValueError("需要 --solar 或 --lunar 之一")

    # --- 2. 时辰 ----------------------------------------------------------
    hour_index = None
    shichen_info = None
    late_zi = False
    if hour is not None or shichen is not None:
        h, mi, warn = _parse_hour(
            "%02d:%02d" % (hour, minute) if hour is not None else None, shichen)
        if warn:
            warnings.append(warn)
        else:
            import datetime as _dt
            # 夏令时还原（口径：fix —— 出生证钟表时在 1986–1991 夏令时区间要 −1h）
            clock_dt, clock_warns, clock_meta = _fix_clock(_make_dt(y, m, d, h, mi))
            warnings.extend(clock_warns)
            y, m, d, h, mi = (clock_dt.year, clock_dt.month, clock_dt.day,
                              clock_dt.hour, clock_dt.minute)
            if clock_meta:
                time_resolution["clock_fix"] = clock_meta
            if longitude is not None:
                naive = _make_dt(y, m, d, h, mi)
                fixed, delta = true_solar_time(naive, float(longitude))
                if fixed.date() != naive.date():
                    warnings.append({
                        "code": "TRUE_SOLAR_SHIFT",
                        "message": "真太阳时修正 %+d 秒后跨日：%s -> %s"
                                   % (delta, naive.strftime("%Y-%m-%d %H:%M"),
                                      fixed.strftime("%Y-%m-%d %H:%M")),
                    })
                time_resolution["true_solar"] = {
                    "longitude": float(longitude), "shift_seconds": delta,
                    "from": naive.strftime("%Y-%m-%d %H:%M"),
                    "to": fixed.strftime("%Y-%m-%d %H:%M")}
                y, m, d, h, mi = fixed.year, fixed.month, fixed.day, fixed.hour, fixed.minute
            elif place:
                warnings.append({
                    "code": "LONGITUDE_ESTIMATED",
                    "message": "只给了地名 %s，未给经度，未做真太阳时修正" % place,
                })
            if h == 23:
                # 夜子时：子初换日，日序推进到次日（与日历内核的 23:00 换日一致）
                import datetime as _dt
                nxt = _dt.date(y, m, d) + _dt.timedelta(days=1)
                y, m, d = nxt.year, nxt.month, nxt.day
                late_zi = True
                warnings.append({
                    "code": "LATE_ZI",
                    "message": "23 点出生属夜子时：紫微按子初换日排盘（农历日期推进到次日），"
                               "与早子时显式区分（SCHOOL_VARIANT:late_zi=next_day）",
                })
            shichen_info = shichen_of(h, mi)
            hour_index = shichen_info["index"]
    else:
        warnings.append({
            "code": "SHICHEN_UNKNOWN",
            "message": "未给 --hour/--shichen，紫微缺时辰无法定命宫，"
                       "只输出农历与生年四化表",
        })

    solar_str = "%04d-%02d-%02d" % (y, m, d)
    lunar_info = solar_to_lunar(y, m, d)
    time_resolution["effective"] = ("%s %02d:%02d" % (solar_str, h, mi)
                                    if hour_index is not None else solar_str)
    time_resolution["late_zi_shift"] = bool(late_zi)

    # --- 3. 农历与年干支 --------------------------------------------------
    lunar_year = lunar_info["year"]
    lunar_month = lunar_info["month"]
    lunar_day = lunar_info["day"]
    lunar_leap = bool(lunar_info.get("leap")) or (lunar_given and leap)

    if lunar_leap:
        warnings.append({
            "code": "LEAP_MONTH",
            "message": "闰月生人：初一至十五算本月，十六以后算次月"
                       "（SCHOOL_VARIANT:leap_month=split_15）",
        })
        if lunar_day >= 16:
            month_for_palace = lunar_month + 1
            if month_for_palace > 12:
                month_for_palace = 1
        else:
            month_for_palace = lunar_month
    else:
        month_for_palace = lunar_month

    year_gz = year_ganzhi_of_lunar_year(lunar_year)
    year_stem, year_branch = year_gz[0], year_gz[1]
    year_branch_idx = BRANCHES.index(year_branch)

    warnings.append({
        "code": "SCHOOL_VARIANT",
        "message": "紫微口径：年干支以农历正月初一为界（非立春，"
                   "SCHOOL_VARIANT:year_divide=lunar_new_year）；"
                   "生年四化甲–辛癸同《全书》卷二，壬干取左辅化科、"
                   "原文作天府化科属已知偏离（SCHOOL_VARIANT:sihua=ren_zuofu_deviation）；"
                   "闰月半月分界为折中口径（SCHOOL_VARIANT:leap_month=split_15）",
    })

    if sex not in ("男", "女"):
        raise ValueError("--sex 只能是 男 或 女，收到：%s" % sex)

    result = {
        "input": {
            "solar": solar_str,
            "late_zi": late_zi,
            "hour": ("%02d:%02d" % (hour, minute)) if hour is not None else None,
            "shichen": shichen,
            "sex": sex,
            "place": place,
            "longitude": longitude,
            "liunian": liunian,
        },
        "lunar": {
            "year": lunar_year,
            "month": lunar_month,
            "day": lunar_day,
            "leap": lunar_leap,
            "year_cn": lunar_info.get("year_cn"),
            "month_cn": lunar_info.get("month_cn"),
            "day_cn": lunar_info.get("day_cn"),
            "year_ganzhi": year_gz,
            "month_index_used": month_for_palace,
            "shichen": shichen_info["branch"] if shichen_info else None,
            "shichen_index": hour_index,
            "shichen_range": shichen_info["range"] if shichen_info else None,
        },
        "ming_gong": None,
        "shen_gong": None,
        "wuxing_ju": None,
        "yin_yang": {
            "year_stem": year_stem,
            "stem_yinyang": "阳" if year_stem in YANG_STEMS else "阴",
            "sex": sex,
            "combo": ("阳" if year_stem in YANG_STEMS else "阴") + sex,
            "daxian_direction": "顺行" if ((year_stem in YANG_STEMS) == (sex == "男")) else "逆行",
        },
        "ming_zhu": None,
        "shen_zhu": None,
        "palaces": [],
        "daxian": [],
        "sihua_year": None,
        "liunian": None,
        "time_resolution": time_resolution,
        "school_notes": list(SCHOOL_NOTES),
        "warnings": warnings,
    }

    # 生年四化表（不依赖时辰，总是给）
    lu, quan, ke, ji = SI_HUA[year_stem]
    result["sihua_year"] = {
        "year_stem": year_stem,
        "year_ganzhi": year_gz,
        "lu": lu, "quan": quan, "ke": ke, "ji": ji,
        "school": "现代排盘通行本（甲–辛癸同《全书》卷二；壬干左辅科为现代通行）",
        "variant_note": "壬干：《全书》卷二原文「壬梁紫府武」作天府化科，本实现取左辅化科"
                        "（与现代排盘一致）；庚干化科/戊干化科另有异说",
    }

    if hour_index is None:
        result["ming_zhu"] = None
        result["shen_zhu"] = SHEN_ZHU_BY_BRANCH[year_branch_idx]
        result["warnings"] = warnings
        return result, warnings

    # --- 4. 命宫/身宫/五行局 ----------------------------------------------
    ming = ming_gong_index(month_for_palace, hour_index)
    shen = shen_gong_index(month_for_palace, hour_index)
    ming_stem = palace_stem(year_stem, ming)
    ming_gz = ming_stem + BRANCHES[ming]
    ju_name, ju_num, ju_elem = wuxing_ju(ming_stem, BRANCHES[ming])

    result["ming_gong"] = {"branch": BRANCHES[ming], "stem": ming_stem,
                           "ganzhi": ming_gz, "index": ming}
    result["shen_gong"] = {
        "branch": BRANCHES[shen], "stem": palace_stem(year_stem, shen),
        "ganzhi": palace_stem(year_stem, shen) + BRANCHES[shen], "index": shen,
        "palace_name": PALACE_NAMES[(ming - shen) % 12],
    }
    result["wuxing_ju"] = {"name": ju_name, "number": ju_num, "element": ju_elem,
                           "nayin_of": ming_gz}
    result["ming_zhu"] = MING_ZHU[ming]
    result["shen_zhu"] = SHEN_ZHU_BY_BRANCH[year_branch_idx]

    # --- 5. 星曜 ----------------------------------------------------------
    star_map, _ju_num, _ming = build_star_map(year_stem, year_branch_idx,
                                              month_for_palace, lunar_day, hour_index)

    # 四化落宫（生年）
    sihua_pos = {}
    for branch_idx, lst in star_map.items():
        for star in lst:
            if star["sihua"]:
                sihua_pos[star["name"]] = {
                    "hua": star["sihua"], "branch": BRANCHES[branch_idx],
                    "palace": PALACE_NAMES[(ming - branch_idx) % 12],
                }
    result["sihua_year"]["positions"] = sihua_pos

    # --- 6. 大限 ----------------------------------------------------------
    forward = ((year_stem in YANG_STEMS) == (sex == "男"))
    step = 1 if forward else -1
    start_age = ju_num
    daxian = []
    for k in range(12):
        branch_idx = (ming + step * k) % 12
        age_from = start_age + 10 * k
        daxian.append({
            "index": k + 1,
            "palace": PALACE_NAMES[k],
            "branch": BRANCHES[branch_idx],
            "ganzhi": palace_stem(year_stem, branch_idx) + BRANCHES[branch_idx],
            "start_age": age_from,
            "end_age": age_from + 9,
            "direction": "顺行" if forward else "逆行",
        })
    result["daxian"] = daxian

    # --- 7. 十二宫 --------------------------------------------------------
    palaces = []
    for branch_idx in range(12):
        name = PALACE_NAMES[(ming - branch_idx) % 12]
        dx = next(x for x in daxian if BRANCHES.index(x["branch"]) == branch_idx)
        palaces.append({
            "index": branch_idx,
            "name": name,
            "branch": BRANCHES[branch_idx],
            "stem": palace_stem(year_stem, branch_idx),
            "ganzhi": palace_stem(year_stem, branch_idx) + BRANCHES[branch_idx],
            "is_ming": branch_idx == ming,
            "is_shen": branch_idx == shen,
            "daxian": {"index": dx["index"], "start_age": dx["start_age"],
                       "end_age": dx["end_age"]},
            "stars": star_map[branch_idx],
        })
    result["palaces"] = palaces

    if dayun_n:
        try:
            idx = int(dayun_n) - 1
            if idx < 0 or idx > 11:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("--dayun-n 应为 1-12 的整数")
        result["daxian_focus"] = daxian[idx]

    # --- 8. 流年 ----------------------------------------------------------
    if liunian:
        ly = int(liunian)
        ln_gz = year_ganzhi_of_lunar_year(ly)
        ln_stem = ln_gz[0]
        ln_branch_idx = BRANCHES.index(ln_gz[1])
        ln_ages = ly - lunar_year + 1        # 虚岁
        cur = next((x for x in daxian if x["start_age"] <= ln_ages <= x["end_age"]), None)
        ln_palaces = []
        for branch_idx in range(12):
            ln_palaces.append({
                "index": branch_idx,
                "name": PALACE_NAMES[(ln_branch_idx - branch_idx) % 12],
                "branch": BRANCHES[branch_idx],
                "natal_palace": PALACE_NAMES[(ming - branch_idx) % 12],
                "stars": star_map[branch_idx],
            })
        ln_lu, ln_quan, ln_ke, ln_ji = SI_HUA[ln_stem]
        result["liunian"] = {
            "year": ly,
            "ganzhi": ln_gz,
            "nominal_age": ln_ages,
            "ming_gong_branch": BRANCHES[ln_branch_idx],
            "sihua": {"year_stem": ln_stem, "lu": ln_lu, "quan": ln_quan,
                      "ke": ln_ke, "ji": ln_ji,
                      "school": result["sihua_year"]["school"],
                      "variant_note": result["sihua_year"]["variant_note"]},
            "daxian": cur,
            "palaces": ln_palaces,
        }

    result["warnings"] = warnings
    return result, warnings


# ---------------------------------------------------------------------------
# 人类可读输出
# ---------------------------------------------------------------------------

def render_text(result) -> str:
    lunar = result["lunar"]
    yin = result["yin_yang"]
    lines = []
    lines.append("紫微斗数 · %s %s %s" % (result["input"]["solar"],
                                       result["input"]["hour"] or "时辰未知",
                                       result["input"]["sex"]))
    lines.append("农历：%s年%s%s %s" % (lunar["year_cn"], lunar["month_cn"],
                                     lunar["day_cn"],
                                     ("[闰]" if lunar["leap"] else "")))
    if result["ming_gong"]:
        lines.append("年干支：%s（%s）｜命宫：%s%s｜身宫：%s%s｜五行局：%s（%d）"
                     % (lunar["year_ganzhi"], yin["combo"],
                        result["ming_gong"]["branch"], result["ming_gong"]["ganzhi"],
                        result["shen_gong"]["branch"], result["shen_gong"]["ganzhi"],
                        result["wuxing_ju"]["name"], result["wuxing_ju"]["number"]))
        lines.append("命主：%s｜身主：%s｜大限：%s"
                     % (result["ming_zhu"], result["shen_zhu"],
                        yin["daxian_direction"]))
        lines.append("")
        lines.append("| 宫位 | 宫干支 | 主星 | 辅星/煞曜 | 大限 |")
        lines.append("|---|---|---|---|---|")
        for p in result["palaces"]:
            majors = "、".join(
                "%s(%s%s)" % (s["name"], s["brightness"],
                              ("·" + s["sihua"]) if s["sihua"] else "")
                for s in p["stars"] if s["type"] == "主星") or "—"
            rest = "、".join(
                "%s%s" % (s["name"], ("·" + s["sihua"]) if s["sihua"] else "")
                for s in p["stars"] if s["type"] != "主星") or "—"
            mark = "◎" if p["is_ming"] else ("▲" if p["is_shen"] else "")
            lines.append("| %s%s | %s | %s | %s | %d-%d |"
                         % (p["name"], mark, p["ganzhi"], majors, rest,
                            p["daxian"]["start_age"], p["daxian"]["end_age"]))
    else:
        lines.append("年干支：%s" % lunar["year_ganzhi"])
    sh = result.get("sihua_year")
    if sh:
        lines.append("")
        lines.append("生年四化（%s年·%s）：禄=%s 权=%s 科=%s 忌=%s"
                     % (sh["year_ganzhi"], sh["school"], sh["lu"], sh["quan"],
                        sh["ke"], sh["ji"]))
    ln = result.get("liunian")
    if ln:
        lines.append("")
        lines.append("流年 %d（%s）｜流年命宫：%s｜虚岁 %d｜四化：禄=%s 权=%s 科=%s 忌=%s"
                     % (ln["year"], ln["ganzhi"], ln["ming_gong_branch"],
                        ln["nominal_age"], ln["sihua"]["lu"], ln["sihua"]["quan"],
                        ln["sihua"]["ke"], ln["sihua"]["ji"]))
        if ln["daxian"]:
            lines.append("所在大限：%s宫 %d-%d 岁"
                         % (ln["daxian"]["palace"], ln["daxian"]["start_age"],
                            ln["daxian"]["end_age"]))
    if result.get("warnings"):
        lines.append("")
        for w in result["warnings"]:
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
    p = argparse.ArgumentParser(
        prog="ziwei.py", description="钦天监 · 紫微斗数排盘")
    p.add_argument("--solar", help="公历生日 YYYY-MM-DD")
    p.add_argument("--lunar", help="农历生日 YYYY-M-D")
    p.add_argument("--leap", action="store_true", help="农历闰月")
    p.add_argument("--hour", help="出生时刻 HH:MM")
    p.add_argument("--shichen", help="出生时辰（子丑寅…亥）")
    p.add_argument("--sex", default=None, help="男|女")
    p.add_argument("--place", help="出生地名（仅提示，不参与换算）")
    p.add_argument("--longitude", type=float, help="出生地经度（东经为正）")
    p.add_argument("--true-solar", action="store_true", help="按经度换算真太阳时")
    p.add_argument("--liunian", help="流年（公历年，如 2026）")
    p.add_argument("--dayun-n", dest="dayun_n", help="选中第 N 个大限（1-12）")
    p.add_argument("--deceased-year", dest="deceased_year",
                   help="（bazi 专用参数，紫微不使用，接受以保持 CLI 一致）")
    p.add_argument("--json", action="store_true", help="输出 JSON 信封")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    as_json = "--json" in argv
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.hour and args.shichen:
        return _error("BAD_INPUT", "--hour 与 --shichen 互斥", as_json)
    if not args.sex:
        return _error("BAD_INPUT", "紫微排盘必须给 --sex 男|女", as_json)

    try:
        result, warnings = ziwei_chart(
            solar=args.solar, lunar=args.lunar, leap=args.leap,
            hour=(int(args.hour.replace("：", ":").split(":")[0])
                  if args.hour else None),
            minute=(int(args.hour.replace("：", ":").split(":")[1])
                    if args.hour and ":" in args.hour else 0),
            shichen=args.shichen, sex=args.sex, longitude=args.longitude,
            place=args.place, liunian=args.liunian, dayun_n=args.dayun_n,
            true_solar=args.true_solar or args.longitude is not None,
        )
    except DateError as exc:
        return _error("BAD_DATE", str(exc), as_json)
    except ValueError as exc:
        msg = str(exc)
        code = "BAD_INPUT"
        if "日期" in msg or "不存在" in msg:
            code = "BAD_DATE"
        return _error(code, msg, as_json)

    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": result["input"],
        "result": result,
        "warnings": warnings,
        "seed": None,
    }
    _emit(payload, as_json, text=render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
