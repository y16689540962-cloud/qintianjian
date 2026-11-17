# -*- coding: utf-8 -*-
"""bazi.py —— 钦天监八字排盘引擎（零第三方依赖，Python 3.9+）。

职责
    把出生时刻排成四柱，并给出藏干、十神、纳音、五行统计、十神统计、大运（顺逆 +
    起运精确到年月日）、流年、神煞、空亡。所有历法数据来自 calendar_core，本文件不自行
    推算节气与朔望——**禁止心算，盘面一律以脚本输出为准**。

输入
    --solar YYYY-MM-DD 或 --lunar YYYY-MM-DD（配 --leap）
    --hour HH:MM / --shichen 子…亥（互斥；都不给则时柱未知）
    --sex 男|女（缺省时大运降级：direction=null，不给顺逆）
    --place 城市名 / --longitude 东经度数（给了就启用真太阳时）
    --deceased-year N（只截断流年推演/定位锚点）/ --dayun-n N（大运步数，默认 10）

输出
    人类可读 Markdown（默认）或 --json 契约 §3 信封（result 字段见契约 §6）。

口径（全部可追到 references/calendar.md）
    1. 年柱以**立春交节时刻**为界；月柱以十二「节」交节时刻为界（节气定界见 calendar_core）。
    2. 日柱以**子初 23:00** 换日：默认 late_zi="next_day"，23:00–23:59 用次日日柱，
       可用 --late-zi same_day 切换为「夜子时算当日」；两种口径都会发 LATE_ZI 警告。
    3. 时柱用五鼠遁（甲己日起甲子），时干由**已定口径的日干**推出。
    4. 中国 1986–1991 夏令时：区间内**自动 −1 小时**再排盘，并发 CLOCK_CHANGE；
       --no-dst 可关闭（关闭时仍发警告，只提示不修正）。
    5. 真太阳时 = 钟表时 + 经度时差 + 均时差，由 calendar_core.true_solar_time 给出；
       给了 --longitude/--place 才启用（默认启用），影响「时支」与「子初换日」两处。
    6. 大运：阳年男/阴年女顺排、阴年男/阳年女逆排；起运用「三日折一年」——
       顺行取出生→下一节、逆行取上一节→出生，按 days/3 折算年月日。

已知局限
    1. 节气时刻在子夜 ±1 分钟内时，月柱/年柱归属存在实现级分歧（不同天文级数差异），
       本实现按自算时刻判定，并在临界 2 小时内发 JIEQI_BOUNDARY 警告。
    2. 神煞取通行口诀，流派口径不一致者已在返回项 status 标注，不当作经典原文。
    3. 1850–2100 之外的范围由 calendar_core 拒绝。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import calendar_core as cal

ENGINE = cal.ENGINE
SCHEMA_VERSION = 1
STEMS = cal.STEMS
BRANCHES = cal.BRANCHES
SHENGXIAO = cal.SHENGXIAO
STEM_INDEX = {s: i for i, s in enumerate(STEMS)}
BRANCH_INDEX = {b: i for i, b in enumerate(BRANCHES)}

# ----------------------------------------------------------------------
# 基础对照表
# ----------------------------------------------------------------------
STEM_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
               "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
BRANCH_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
                 "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
STEM_YINYANG = {"甲": "阳", "乙": "阴", "丙": "阳", "丁": "阴", "戊": "阳",
                "己": "阴", "庚": "阳", "辛": "阴", "壬": "阳", "癸": "阴"}
BRANCH_YINYANG = {"子": "阳", "丑": "阴", "寅": "阳", "卯": "阴", "辰": "阳", "巳": "阴",
                  "午": "阳", "未": "阴", "申": "阳", "酉": "阴", "戌": "阳", "亥": "阴"}
WUXING_LIST = ("木", "火", "土", "金", "水")
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 六十甲子纳音（两两一组，index = 干支序 // 2）
NAYIN = (
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
    "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
    "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
    "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
    "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
)

# 地支藏干：(天干, 气位)，本气/中气/余气
CANGAN = {
    "子": (("癸", "本气"),),
    "丑": (("己", "本气"), ("癸", "中气"), ("辛", "余气")),
    "寅": (("甲", "本气"), ("丙", "中气"), ("戊", "余气")),
    "卯": (("乙", "本气"),),
    "辰": (("戊", "本气"), ("乙", "中气"), ("癸", "余气")),
    "巳": (("丙", "本气"), ("庚", "中气"), ("戊", "余气")),
    "午": (("丁", "本气"), ("己", "中气")),
    "未": (("己", "本气"), ("丁", "中气"), ("乙", "余气")),
    "申": (("庚", "本气"), ("壬", "中气"), ("戊", "余气")),
    "酉": (("辛", "本气"),),
    "戌": (("戊", "本气"), ("辛", "中气"), ("丁", "余气")),
    "亥": (("壬", "本气"), ("甲", "中气")),
}

# 地支六合 / 六冲 / 三合局（供神煞与提示用）
BRANCH_HE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
             "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}

SHISHEN_ORDER = ("比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印")


def ganzhi_index(gan, zhi):
    """干支 -> 六十甲子序（0 = 甲子）。"""
    gi = STEM_INDEX[gan]
    zi = BRANCH_INDEX[zhi]
    for i in range(60):
        if i % 10 == gi and i % 12 == zi:
            return i
    raise cal.DateError("干支组合非法：%s%s" % (gan, zhi))


def nayin_of(gan, zhi):
    return NAYIN[ganzhi_index(gan, zhi) // 2]


def shishen_of(day_stem, target_stem):
    """以日干为「我」，判 target 的十神。"""
    if day_stem not in STEM_INDEX or target_stem not in STEM_INDEX:
        raise cal.DateError("天干非法：%r / %r" % (day_stem, target_stem))
    de = STEM_WUXING[day_stem]
    te = STEM_WUXING[target_stem]
    same = STEM_YINYANG[day_stem] == STEM_YINYANG[target_stem]
    if de == te:
        return "比肩" if same else "劫财"
    if SHENG[de] == te:
        return "食神" if same else "伤官"
    if KE[de] == te:
        return "偏财" if same else "正财"
    if KE[te] == de:
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"


# ----------------------------------------------------------------------
# 神煞规则表（status: pub = 通行出处，school = 流派口径）
# ----------------------------------------------------------------------
TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "辛": "午寅", "壬": "卯巳", "癸": "卯巳"}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "戊": "申", "丁": "酉",
            "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
TAOHUA = {"申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯",
          "巳": "午", "酉": "午", "丑": "午", "亥": "子", "卯": "子", "未": "子"}
YIMA = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
        "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳", "卯": "巳", "未": "巳"}
HUAGAI = {"申": "辰", "子": "辰", "辰": "辰", "寅": "戌", "午": "戌", "戌": "戌",
          "巳": "丑", "酉": "丑", "丑": "丑", "亥": "未", "卯": "未", "未": "未"}
JIANGXING = {"申": "子", "子": "子", "辰": "子", "寅": "午", "午": "午", "戌": "午",
             "巳": "酉", "酉": "酉", "丑": "酉", "亥": "卯", "卯": "卯", "未": "卯"}
YANGREN = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
           "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
LUSHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
          "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YUEDE = {"寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬",
         "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚"}
KUIGANG = ("庚辰", "庚戌", "壬辰", "戊戌")

# 中国夏令时区间（含起止日；起始日 02:00 后、结束日 02:00 前为夏令时）
DST_WINDOWS = (
    (1986, 5, 4, 1986, 9, 14),
    (1987, 4, 12, 1987, 9, 13),
    (1988, 4, 10, 1988, 9, 11),
    (1989, 4, 16, 1989, 9, 17),
    (1990, 4, 15, 1990, 9, 16),
    (1991, 4, 14, 1991, 9, 15),
)

# 常用城市经度（东经为正）。只用于真太阳时的经度时差。
PLACE_LONGITUDE = {
    "北京": 116.41, "上海": 121.47, "天津": 117.20, "重庆": 106.55,
    "广州": 113.26, "深圳": 114.06, "杭州": 120.15, "南京": 118.78,
    "武汉": 114.30, "成都": 104.07, "西安": 108.94, "沈阳": 123.43,
    "哈尔滨": 126.63, "长春": 125.32, "大连": 121.62, "济南": 117.00,
    "青岛": 120.38, "郑州": 113.62, "长沙": 112.94, "福州": 119.30,
    "厦门": 118.10, "昆明": 102.71, "兰州": 103.83, "乌鲁木齐": 87.62,
    "拉萨": 91.11, "香港": 114.17, "澳门": 113.55, "台北": 121.52,
    "石家庄": 114.51, "太原": 112.55, "合肥": 117.27, "南昌": 115.89,
    "南宁": 108.32, "贵阳": 106.71, "海口": 110.35, "西宁": 101.78,
    "银川": 106.23, "呼和浩特": 111.75, "苏州": 120.60, "宁波": 121.55,
    "无锡": 120.30, "温州": 120.70, "东莞": 113.75, "佛山": 113.12,
}


# ----------------------------------------------------------------------
# 小工具
# ----------------------------------------------------------------------
def _add_ymd(dt, years=0, months=0, days=0):
    """给 datetime/date 加「年月日」（月按公历月推进，日越界则顺延）。"""
    base = dt if isinstance(dt, datetime) else datetime(dt.year, dt.month, dt.day)
    y = base.year + years
    m = base.month + months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    day = base.day
    while day > 1:
        try:
            out = base.replace(year=y, month=m, day=day)
            break
        except ValueError:
            day -= 1
    else:
        out = base.replace(year=y, month=m, day=1)
    return out + timedelta(days=days)


def _parse_hour(text):
    parts = str(text).strip().replace("：", ":").split(":")
    try:
        h = int(parts[0])
        mi = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        raise cal.DateError("时点格式应为 HH:MM，收到 %r" % (text,))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise cal.DateError("时点越界：%r" % (text,))
    return h, mi


def _jie_instants(center):
    """center 前后各 3 年的十二「节」时刻（datetime 升序）。"""
    items = []
    for y in range(center.year - 3, center.year + 4):
        for t in cal.solar_terms(y):
            if t["index"] % 2 == 0:
                items.append(datetime.strptime(t["ts"], "%Y-%m-%d %H:%M:%S"))
    items.sort()
    return items


def _nearest_jie(center):
    """(上一个节, 下一个节) 的 datetime。"""
    items = _jie_instants(center)
    prev_jie = None
    for t in items:
        if t <= center:
            prev_jie = t
        else:
            return prev_jie, t
    raise cal.DateError("无法定位 %s 前后的节" % center)


def _in_dst_window(dt):
    for (y0, m0, d0, y1, m1, d1) in DST_WINDOWS:
        start = datetime(y0, m0, d0, 2, 0)
        end = datetime(y1, m1, d1, 2, 0)
        if start <= dt < end:
            return True
    return False


def _resolve_longitude(place, longitude):
    """返回 (经度 or None, 来源说明)。"""
    if longitude is not None:
        if not (-180.0 <= float(longitude) <= 180.0):
            raise cal.DateError("经度越界：%r" % (longitude,))
        return float(longitude), "参数"
    if place:
        name = str(place).strip()
        if name in PLACE_LONGITUDE:
            return PLACE_LONGITUDE[name], "城市表"
        for key in PLACE_LONGITUDE:
            if key in name:
                return PLACE_LONGITUDE[key], "城市表(模糊)"
        raise cal.DateError(
            "城市表里没有 %r，请改用 --longitude 东经度数（如 --longitude 116.4）" % (place,))
    return None, None


def _pillar(gan, zhi, day_stem=None, is_day=False):
    """单柱信息。"""
    idx = ganzhi_index(gan, zhi)
    gan_element = STEM_WUXING[gan]
    zhi_element = BRANCH_WUXING[zhi]
    cang = []
    for (stem, level) in CANGAN[zhi]:
        item = {"stem": stem, "level": level, "wuxing": STEM_WUXING[stem]}
        if day_stem:
            item["shishen"] = shishen_of(day_stem, stem)
        cang.append(item)
    out = {
        "ganzhi": gan + zhi,
        "stem": gan,
        "branch": zhi,
        "shishen": "日主" if is_day else (shishen_of(day_stem, gan) if day_stem else None),
        "canggan": cang,
        "nayin": NAYIN[idx // 2],
        "wuxing": {"stem": gan_element, "branch": zhi_element},
        "yinyang": {"stem": STEM_YINYANG[gan], "branch": BRANCH_YINYANG[zhi]},
        "xun": "甲" + BRANCHES[(idx // 10) * 10 % 12] + "旬",
        "kong": [BRANCHES[((idx // 10) * 10 + 10) % 12], BRANCHES[((idx // 10) * 10 + 11) % 12]],
    }
    if is_day:
        out["shishen"] = "日主"
    return out


def _wuxing_tally(pillars):
    """五行统计：明干支各计 1；藏干按 本气1.0 / 中气0.5 / 余气0.2 加权。"""
    count = {w: 0 for w in WUXING_LIST}
    weighted = {w: 0.0 for w in WUXING_LIST}
    for p in pillars:
        if not p:
            continue
        count[STEM_WUXING[p["stem"]]] += 1
        weighted[STEM_WUXING[p["stem"]]] += 1.0
        count[BRANCH_WUXING[p["branch"]]] += 1
        weighted[BRANCH_WUXING[p["branch"]]] += 1.0
    weights = {"本气": 1.0, "中气": 0.5, "余气": 0.2}
    for p in pillars:
        if not p:
            continue
        for cg in p["canggan"]:
            weighted[cg["wuxing"]] += weights[cg["level"]]
    return count, {k: round(v, 2) for k, v in weighted.items()}


def _shishen_tally(pillars):
    """十神统计：年/月/时干 + 四支藏干各计 1，日干本身不计。"""
    count = {name: 0 for name in SHISHEN_ORDER}
    for p in pillars:
        if not p:
            continue
        if p["shishen"] not in (None, "日主"):
            count[p["shishen"]] += 1
        for cg in p["canggan"]:
            ss = cg.get("shishen")
            if ss:
                count[ss] += 1
    return count


def _shensha(pillars):
    """神煞命中表。basis 写明从哪个字起算，status: pub / school。"""
    labels = (("year", "年支"), ("month", "月支"), ("day", "日支"), ("hour", "时支"))
    stems = [(k, p["stem"], lbl.replace("支", "干")) for (k, lbl) in labels
             for p in [pillars.get(k)] if p]
    branches = [(k, p["branch"], lbl) for (k, lbl) in labels for p in [pillars.get(k)] if p]
    day = pillars.get("day")
    year = pillars.get("year")
    month = pillars.get("month")
    out = []

    def hit_by_branch(name, basis_label, targets, status, rule):
        hits = [lbl for (_k, b, lbl) in branches if b in targets]
        if hits:
            out.append({"name": name, "basis": basis_label, "target": targets,
                        "hits": hits, "status": status, "rule": rule})

    def hit_by_stem(name, basis_label, targets, status, rule):
        hits = [lbl for (_k, s, lbl) in stems if s in targets]
        if hits:
            out.append({"name": name, "basis": basis_label, "target": targets,
                        "hits": hits, "status": status, "rule": rule})

    if day:
        ds = day["stem"]
        hit_by_branch("天乙贵人", "日干" + ds, TIANYI[ds], "pub", "六辛逢马虎，甲戊庚牛羊")
        hit_by_branch("文昌贵人", "日干" + ds, WENCHANG[ds], "pub", "甲巳乙午丙戊申，丁己酉庚亥辛子壬寅癸卯")
        hit_by_branch("羊刃", "日干" + ds, YANGREN[ds], "school", "甲卯乙寅丙午丁巳戊午己巳庚酉辛申壬子癸亥")
        hit_by_branch("禄神", "日干" + ds, LUSHEN[ds], "pub", "甲禄在寅、乙禄在卯…")
        if day["ganzhi"] in KUIGANG:
            out.append({"name": "魁罡", "basis": "日柱" + day["ganzhi"], "target": day["ganzhi"],
                        "hits": ["日柱"], "status": "school", "rule": "庚辰庚戌壬辰戊戌为魁罡"})
    if year:
        ys = year["stem"]
        hit_by_branch("天乙贵人", "年干" + ys, TIANYI[ys], "pub", "六辛逢马虎，甲戊庚牛羊")
    for basis_pillar, basis_name in ((year, "年支"), (day, "日支")):
        if not basis_pillar:
            continue
        b = basis_pillar["branch"]
        hit_by_branch("桃花", basis_name + b, TAOHUA[b], "school", "申子辰在酉，寅午戌在卯，巳酉丑在午，亥卯未在子")
        hit_by_branch("驿马", basis_name + b, YIMA[b], "pub", "申子辰马在寅，寅午戌马在申")
        hit_by_branch("华盖", basis_name + b, HUAGAI[b], "pub", "申子辰见辰，寅午戌见戌")
        hit_by_branch("将星", basis_name + b, JIANGXING[b], "pub", "三合局中神")
    if month:
        hit_by_stem("月德贵人", "月支" + month["branch"], YUEDE[month["branch"]], "pub",
                    "寅午戌月见丙，申子辰月见壬，亥卯未月见甲，巳酉丑月见庚")
    return out


def _pillar(gan, zhi, day_stem=None, is_day=False):
    """单柱信息。"""
    idx = ganzhi_index(gan, zhi)
    gan_element = STEM_WUXING[gan]
    zhi_element = BRANCH_WUXING[zhi]
    cang = []
    for (stem, level) in CANGAN[zhi]:
        item = {"stem": stem, "level": level, "wuxing": STEM_WUXING[stem]}
        if day_stem:
            item["shishen"] = shishen_of(day_stem, stem)
        cang.append(item)
    out = {
        "ganzhi": gan + zhi,
        "stem": gan,
        "branch": zhi,
        "shishen": "日主" if is_day else (shishen_of(day_stem, gan) if day_stem else None),
        "canggan": cang,
        "nayin": NAYIN[idx // 2],
        "wuxing": {"stem": gan_element, "branch": zhi_element},
        "yinyang": {"stem": STEM_YINYANG[gan], "branch": BRANCH_YINYANG[zhi]},
        "xun": "甲" + BRANCHES[(idx // 10) * 10 % 12] + "旬",
        "kong": [BRANCHES[((idx // 10) * 10 + 10) % 12], BRANCHES[((idx // 10) * 10 + 11) % 12]],
    }
    if is_day:
        out["shishen"] = "日主"
    return out


def _wuxing_tally(pillars):
    """五行统计：明干支各计 1；藏干按 本气1.0 / 中气0.5 / 余气0.2 加权。"""
    count = {w: 0 for w in WUXING_LIST}
    weighted = {w: 0.0 for w in WUXING_LIST}
    for p in pillars:
        if not p:
            continue
        count[STEM_WUXING[p["stem"]]] += 1
        weighted[STEM_WUXING[p["stem"]]] += 1.0
        count[BRANCH_WUXING[p["branch"]]] += 1
        weighted[BRANCH_WUXING[p["branch"]]] += 1.0
    weights = {"本气": 1.0, "中气": 0.5, "余气": 0.2}
    for p in pillars:
        if not p:
            continue
        for cg in p["canggan"]:
            weighted[cg["wuxing"]] += weights[cg["level"]]
    return count, {k: round(v, 2) for k, v in weighted.items()}


def _shishen_tally(pillars):
    """十神统计：年/月/时干 + 四支藏干各计 1，日干本身不计。"""
    count = {name: 0 for name in SHISHEN_ORDER}
    for p in pillars:
        if not p:
            continue
        if p["shishen"] not in (None, "日主"):
            count[p["shishen"]] += 1
        for cg in p["canggan"]:
            ss = cg.get("shishen")
            if ss:
                count[ss] += 1
    return count


def _shensha(pillars):
    """神煞命中表。basis 写明从哪个字起算，status: pub / school。"""
    labels = (("year", "年支"), ("month", "月支"), ("day", "日支"), ("hour", "时支"))
    stems = [(k, p["stem"], lbl.replace("支", "干")) for (k, lbl) in labels
             for p in [pillars.get(k)] if p]
    branches = [(k, p["branch"], lbl) for (k, lbl) in labels for p in [pillars.get(k)] if p]
    day = pillars.get("day")
    year = pillars.get("year")
    month = pillars.get("month")
    out = []

    def hit_by_branch(name, basis_label, targets, status, rule):
        hits = [lbl for (_k, b, lbl) in branches if b in targets]
        if hits:
            out.append({"name": name, "basis": basis_label, "target": targets,
                        "hits": hits, "status": status, "rule": rule})

    def hit_by_stem(name, basis_label, targets, status, rule):
        hits = [lbl for (_k, s, lbl) in stems if s in targets]
        if hits:
            out.append({"name": name, "basis": basis_label, "target": targets,
                        "hits": hits, "status": status, "rule": rule})

    if day:
        ds = day["stem"]
        hit_by_branch("天乙贵人", "日干" + ds, TIANYI[ds], "pub", "六辛逢马虎，甲戊庚牛羊")
        hit_by_branch("文昌贵人", "日干" + ds, WENCHANG[ds], "pub", "甲巳乙午丙戊申，丁己酉庚亥辛子壬寅癸卯")
        hit_by_branch("羊刃", "日干" + ds, YANGREN[ds], "school", "甲卯乙寅丙午丁巳戊午己巳庚酉辛申壬子癸亥")
        hit_by_branch("禄神", "日干" + ds, LUSHEN[ds], "pub", "甲禄在寅、乙禄在卯…")
        if day["ganzhi"] in KUIGANG:
            out.append({"name": "魁罡", "basis": "日柱" + day["ganzhi"], "target": day["ganzhi"],
                        "hits": ["日柱"], "status": "school", "rule": "庚辰庚戌壬辰戊戌为魁罡"})
    if year:
        ys = year["stem"]
        hit_by_branch("天乙贵人", "年干" + ys, TIANYI[ys], "pub", "六辛逢马虎，甲戊庚牛羊")
    for basis_pillar, basis_name in ((year, "年支"), (day, "日支")):
        if not basis_pillar:
            continue
        b = basis_pillar["branch"]
        hit_by_branch("桃花", basis_name + b, TAOHUA[b], "school", "申子辰在酉，寅午戌在卯，巳酉丑在午，亥卯未在子")
        hit_by_branch("驿马", basis_name + b, YIMA[b], "pub", "申子辰马在寅，寅午戌马在申")
        hit_by_branch("华盖", basis_name + b, HUAGAI[b], "pub", "申子辰见辰，寅午戌见戌")
        hit_by_branch("将星", basis_name + b, JIANGXING[b], "pub", "三合局中神")
    if month:
        hit_by_stem("月德贵人", "月支" + month["branch"], YUEDE[month["branch"]], "pub",
                    "寅午戌月见丙，申子辰月见壬，亥卯未月见甲，巳酉丑月见庚")
    return out


def _kongwang(pillars):
    out = []
    for key, label in (("year", "年柱"), ("day", "日柱")):
        p = pillars.get(key)
        if not p:
            continue
        kong = p["kong"]
        hits = []
        for k in ("year", "month", "day", "hour"):
            q = pillars.get(k)
            if q and q["branch"] in kong:
                hits.append({"day" if k == "day" else k: q["branch"]})
        out.append({"pillar": label, "ganzhi": p["ganzhi"], "xun": p["xun"],
                    "kong": kong, "hits": hits})
    return out


def _kongwang(pillars):
    labels = {"year": "年支", "month": "月支", "day": "日支", "hour": "时支"}
    out = []
    for key, label in (("year", "年柱"), ("day", "日柱")):
        p = pillars.get(key)
        if not p:
            continue
        kong = p["kong"]
        hits = []
        for k in ("year", "month", "day", "hour"):
            q = pillars.get(k)
            if q and q["branch"] in kong:
                hits.append(labels[k] + q["branch"])
        out.append({"pillar": label, "ganzhi": p["ganzhi"], "xun": p["xun"],
                    "kong": kong, "hits": hits})
    return out


# ----------------------------------------------------------------------
# 排盘主流程
# ----------------------------------------------------------------------
def build_chart(solar_ymd, hour=None, minute=0, sex=None, place=None, longitude=None,
                meridian=None, late_zi="next_day", apply_tst=True, handle_dst=True,
                dayun_n=10, deceased_year=None, input_note=None, now=None):
    """排八字。solar_ymd 为 (年, 月, 日)；hour 为 None 表示时辰未知。

    返回 (result, warnings)。
    """
    warnings = []

    def warn(code, message):
        warnings.append({"code": code, "message": message})

    y, m, d = int(solar_ymd[0]), int(solar_ymd[1]), int(solar_ymd[2])
    cal.julian_day(y, m, d)                      # 合法性校验（不存在的日期直接报错）
    has_hour = hour is not None
    dt = datetime(y, m, d, int(hour) if has_hour else 12, int(minute) if has_hour else 0)
    clock_change = None

    # 1) 夏令时（共用一个 kernel 函数，避免与 ziwei/qimen 口径分叉）
    dt, clock_warnings, clock_change = cal.resolve_clock(dt, "fix" if handle_dst else "warn")
    for w in clock_warnings:
        warn(w["code"], w["message"])

    # 2) 真太阳时
    lon, lon_src = _resolve_longitude(place, longitude)
    eff = dt
    tst_info = None
    if lon is not None and apply_tst:
        eff, corr = cal.true_solar_time(dt, lon, meridian if meridian is not None else 120.0)
        tst_info = {"longitude": lon, "source": lon_src,
                    "correction_seconds": corr,
                    "clock": dt.strftime("%Y-%m-%d %H:%M"),
                    "true_solar": eff.strftime("%Y-%m-%d %H:%M:%S")}
        warn("TST_APPLIED",
             "真太阳时已生效（经度 %s°，来源%s）：钟表时 %s → 真太阳时 %s，修正 %+d 秒；"
             "影响时支判定与子初换日" % (lon, lon_src, dt.strftime("%H:%M"),
                                eff.strftime("%H:%M:%S"), corr))
    elif lon is None:
        warn("LONGITUDE_ESTIMATED",
             "未提供经度，按标准经线 120°E 的钟表时间排盘（不做真太阳时修正）；"
             "跨经度较大地区建议补 --longitude 或 --place")

    # 3) 四柱
    y_gz = cal.ganzhi_year(eff)
    m_gz = cal.ganzhi_month(eff)
    d_gz = cal.ganzhi_day(eff)
    late_zi_flag = has_hour and eff.hour == 23
    if late_zi_flag and late_zi == "same_day":
        d_gz = cal.ganzhi_day(eff.replace(hour=12, minute=0))
    day_stem = d_gz[0]
    h_gz = None
    if has_hour:
        h_gz = cal.ganzhi_hour(day_stem, eff.hour, eff.minute, late_zi)

    if not has_hour:
        warn("SHICHEN_UNKNOWN", "未给出生时辰，时柱未知；五行/十神统计按三柱，仅作六字分析")
        warn("LOW_CONFIDENCE", "缺时柱，无法判子女宫、时柱十神与部分神煞，结论置信度降低")
    if late_zi_flag:
        alt = "same_day" if late_zi == "next_day" else "next_day"
        alt_day = cal.ganzhi_day(eff) if alt == "next_day" else cal.ganzhi_day(eff.replace(hour=12))
        alt_hour = cal.ganzhi_hour(alt_day[0], eff.hour, eff.minute, alt)
        warn("LATE_ZI",
             "出生在 23:00–23:59（夜子时）。本次采用 late_zi=%s：日柱 %s、时柱 %s；"
             "另一口径 late_zi=%s 为日柱 %s、时柱 %s。两说并存，须向用户说明"
             % (late_zi, d_gz[0] + d_gz[1], (h_gz[0] + h_gz[1]) if h_gz else "未知",
                alt, alt_day[0] + alt_day[1], alt_hour[0] + alt_hour[1]))
        warn("SCHOOL_VARIANT",
             "早晚子时属流派口径分歧（夜子时算今日 / 算次日），本库默认算次日（late_zi=next_day）")

    # 4) 节气交界
    prev_jie, next_jie = _nearest_jie(eff)
    for jie_dt, direction in ((prev_jie, "已过"), (next_jie, "未到")):
        if jie_dt is None:
            continue
        gap = abs((eff - jie_dt).total_seconds()) / 60.0
        if gap <= 120.0:
            alt_dt = jie_dt + timedelta(minutes=1) if direction == "已过" else jie_dt - timedelta(minutes=1)
            alt_m = cal.ganzhi_month(alt_dt)
            msg = ("出生时刻距交节（%s %s）%s %.0f 分钟，月柱在临界点上："
                   "本盘按 %s 判为 %s，若交节时刻另有口径则为 %s"
                   % (jie_dt.strftime("%Y-%m-%d %H:%M"), "节气", direction, gap,
                      "已过" if direction == "已过" else "未到",
                      m_gz[0] + m_gz[1], alt_m[0] + alt_m[1]))
            alt_y = cal.ganzhi_year(alt_dt)
            if alt_y != y_gz:
                msg += "；年柱同样临界：本盘 %s，另一侧 %s" % (y_gz[0] + y_gz[1], alt_y[0] + alt_y[1])
            warn("JIEQI_BOUNDARY", msg)
            break

    # 5) 农历
    lunar = cal.solar_to_lunar(dt.year, dt.month, dt.day)
    if lunar["leap"]:
        warn("LEAP_MONTH", "出生日在农历闰%s月（月柱仍按节令，不以农历月定）" % lunar["month_cn"][1:])

    # 5b) 朔边界（月首可能因不同天文级数实现差一天）
    for month in _neighbour_months(dt.date(), lunar):
        off = _shuo_offset(month)
        if off is not None and abs(off) <= cal.SHUO_BOUNDARY_MINUTES:
            warn("SHUO_BOUNDARY",
                 "%s%02d-%02d 的朔时刻 %s 距子夜仅 %+.0f 分钟（月首 %s）；此月首在"
                 "天文级数实现不同时可差一天，若生日恰在该月首前后一天，农历月份可能有两说"
                 % ("" if not month["leap"] else "闰", month["month"], 1,
                    month["shuo"].strftime("%Y-%m-%d %H:%M:%S"), off,
                    month["start"].isoformat()))

    # 6) 四柱详表
    def mk(key, gz, is_day=False):
        return _pillar(gz[0], gz[1], day_stem=day_stem, is_day=is_day)

    pillars = {
        "year": mk("year", y_gz),
        "month": mk("month", m_gz),
        "day": mk("day", d_gz, is_day=True),
        "hour": mk("hour", h_gz) if h_gz else None,
    }
    ordered = [pillars["year"], pillars["month"], pillars["day"], pillars["hour"]]
    wuxing_count, wuxing_weighted = _wuxing_tally(ordered)
    shishen_count = _shishen_tally(ordered)

    # 7) 大运
    sex_norm = sex
    if sex_norm not in ("男", "女"):
        sex_norm = None
    dayun = {"direction": None, "qiyun": None, "list": [], "start_age": None,
             "rules": "阳年男/阴年女顺排，阴年男/阳年女逆排"}
    if sex_norm is None:
        warn("SEX_REQUIRED", "未提供性别（--sex 男|女），大运顺逆无法判定，本次不做大运推演")
    else:
        yang_year = STEM_YINYANG[y_gz[0]] == "阳"
        forward = (yang_year and sex_norm == "男") or ((not yang_year) and sex_norm == "女")
        direction = "顺行" if forward else "逆行"
        target_jie = next_jie if forward else prev_jie
        delta = (target_jie - eff) if forward else (eff - target_jie)
        total_days = delta.total_seconds() / 86400.0
        # 三日折一年 → 一日折四月 → 先按「总月数」四舍五入，再由残余折算日
        total_months = total_days / 3.0 * 12.0
        q_years = int(total_months // 12)
        q_months = int(rem_days_round(total_months - 12 * q_years))
        if q_months >= 12:
            q_years += 1
            q_months -= 12
        q_days = int(rem_days_round((total_months - 12 * q_years - q_months) * 30.0))
        if q_days >= 30:
            q_months += 1
            q_days -= 30
        if q_days < 0:
            q_days = 0
        start_dt = _add_ymd(dt, q_years, q_months, q_days)
        qiyun = {
            "years": q_years, "months": q_months, "days": q_days,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "reference_jie": target_jie.strftime("%Y-%m-%d %H:%M"),
            "days_from_jie": round(total_days, 3),
            "rule": "三日折一年（一日折四月，一时辰折十天）",
        }
        m_idx = ganzhi_index(m_gz[0], m_gz[1])
        sign = 1 if forward else -1
        lst = []
        for i in range(1, int(dayun_n) + 1):
            idx = (m_idx + sign * i) % 60
            g, z = STEMS[idx % 10], BRANCHES[idx % 12]
            sdt = _add_ymd(start_dt, (i - 1) * 10, 0, 0)
            edt = _add_ymd(start_dt, i * 10, 0, 0)
            item = _pillar(g, z, day_stem=day_stem)
            item.update({
                "index": i,
                "start_age": q_years + (i - 1) * 10,
                "start_date": sdt.strftime("%Y-%m-%d"),
                "end_date": (edt - timedelta(days=1)).strftime("%Y-%m-%d"),
                "start_year": sdt.year,
                "end_year": edt.year,
            })
            lst.append(item)
        dayun.update({"direction": direction, "qiyun": qiyun, "list": lst,
                      "start_age": q_years})
        if lst and (lst[-1]["end_year"] > cal.SUPPORTED_RANGE[1]
                    or lst[0]["start_year"] < cal.SUPPORTED_RANGE[0]):
            warn("DAYUN_OUT_OF_RANGE",
                 "大运区间 %d–%d 超出历法内核可靠区间 %d–%d，仅作年龄推算参考"
                 % (lst[0]["start_year"], lst[-1]["end_year"],
                    cal.SUPPORTED_RANGE[0], cal.SUPPORTED_RANGE[1]))

    # 8) 流年
    today = now or cal.now_tz()
    anchor = today.year
    if deceased_year:
        cap = int(deceased_year)
        if cap < anchor:
            warn("DECEASED_LIUNIAN_CAP",
                 "已给定 --deceased-year %d：流年只推到该年，命主标记为已故，"
                 "不再推演之后的大运/流年吉凶" % cap)
            anchor = cap
        else:
            warn("DECEASED_LIUNIAN_CAP",
                 "--deceased-year %d 不小于今年 %d，流年仍按今年锚定" % (cap, anchor))
    liunian = []
    birth_year = y
    for yr in range(anchor, anchor + 10):
        idx = (yr - 1984) % 60
        g, z = STEMS[idx % 10], BRANCHES[idx % 12]
        item = {
            "year": yr,
            "ganzhi": g + z,
            "stem": g,
            "branch": z,
            "shishen": shishen_of(day_stem, g),
            "age_xusui": yr - birth_year + 1,
            "age_shisui": yr - birth_year,
            "chong_day": _chong(z) == d_gz[1],
        }
        cur_dayun = None
        for d_item in dayun["list"]:
            if d_item["start_year"] <= yr < d_item["end_year"]:
                cur_dayun = d_item["index"]
                break
        item["dayun_index"] = cur_dayun
        if deceased_year and yr > int(deceased_year):
            break
        liunian.append(item)

    # 9) 汇总
    result = {
        "input": {
            "calendar": (input_note or {}).get("calendar", "solar"),
            "solar": dt.strftime("%Y-%m-%d"),
            "hour": ((input_note or {}).get("hour_text") if has_hour else None),
            "sex": sex_norm,
            "place": place,
            "longitude": lon,
            "late_zi": late_zi,
            "true_solar_time": bool(tst_info),
            "deceased_year": int(deceased_year) if deceased_year else None,
        },
        "birth": {
            "clock": dt.strftime("%Y-%m-%d %H:%M"),
            "clock_input": (input_note or {}).get("clock_input") or dt.strftime("%Y-%m-%d %H:%M"),
            "clock_change": clock_change,
            "effective": eff.strftime("%Y-%m-%d %H:%M:%S"),
            "true_solar_time": tst_info,
            "shichen": cal.shichen_of(eff.hour, eff.minute) if has_hour else None,
        },
        "lunar": lunar,
        "pillars": pillars,
        "day_master": {
            "stem": day_stem,
            "wuxing": STEM_WUXING[day_stem],
            "yinyang": STEM_YINYANG[day_stem],
        },
        "shengxiao": SHENGXIAO[BRANCH_INDEX[y_gz[1]]],
        "wuxing_count": wuxing_count,
        "wuxing_weighted": wuxing_weighted,
        "shishen_count": shishen_count,
        "dayun": dayun,
        "liunian": liunian,
        "shensha": _shensha(pillars),
        "kongwang": _kongwang(pillars),
        "jieqi": {
            "prev": prev_jie.strftime("%Y-%m-%d %H:%M"),
            "next": next_jie.strftime("%Y-%m-%d %H:%M"),
        },
        "warnings": warnings,
    }
    return result, warnings


def rem_days_round(x):
    """起运「日」取整：四舍五入（三日折一年后余数折算成日，取最近整日）。"""
    return math.floor(x + 0.5)


def _shuo_offset(month):
    """月首朔时刻距该日 0 点的分钟数（−720…+720）。"""
    shuo = month.get("shuo")
    if shuo is None:
        return None
    minutes = shuo.hour * 60 + shuo.minute + shuo.second / 60.0
    return minutes if minutes <= 720 else minutes - 1440.0


def _neighbour_months(d, lunar):
    """生日所在农历月及其后一个月（用于检查月首/下月首的朔边界）。"""
    out = []
    try:
        months = cal.lunar_year_months(lunar["year"])
    except cal.DateError:
        return out
    for i, m in enumerate(months):
        if m["start"] <= d < m["start"] + timedelta(days=m["days"]):
            out.append(m)
            if i + 1 < len(months):
                out.append(months[i + 1])
            break
    return out


def _chong(branch):
    """地支相冲。"""
    return BRANCHES[(BRANCH_INDEX[branch] + 6) % 12]


# ----------------------------------------------------------------------
# 命令行与人类可读输出
# ----------------------------------------------------------------------
SHICHEN_HOUR = {"子": 0, "丑": 2, "寅": 4, "卯": 6, "辰": 8, "巳": 10,
                "午": 12, "未": 14, "申": 16, "酉": 18, "戌": 20, "亥": 22}

PILLAR_LABELS = (("year", "年柱"), ("month", "月柱"), ("day", "日柱"), ("hour", "时柱"))


def _parse_ymd(text, what):
    raw = str(text).strip().replace("/", "-").replace(".", "-").replace(" ", "-")
    parts = [p for p in raw.split("-") if p != ""]
    if len(parts) != 3:
        raise cal.DateError("%s 格式应为 YYYY-MM-DD，收到 %r" % (what, text))
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise cal.DateError("%s 格式应为 YYYY-MM-DD，收到 %r" % (what, text))


def _render_text(result):
    """人类可读（Markdown）。数字与 JSON 完全一致。"""
    lines = []
    inp = result["input"]
    birth = result["birth"]
    lu = result["lunar"]
    lines.append("# 八字排盘")
    lines.append("")
    head = "公历 %s" % birth["clock"]
    if birth.get("clock_change"):
        head += "（输入钟表时 %s，夏令时还原 −1 小时）" % birth["clock_change"]["from"][:16]
    if inp["hour"] is None:
        head += "（时辰未知，按正午排三柱）"
    if inp["sex"]:
        head += "　命主：%s" % inp["sex"]
    lines.append(head)
    lines.append("")
    lines.append("农历 %s年%s%s（%s，%d 天）　生肖%s"
                 % (lu["year_cn"], lu["month_cn"], lu["day_cn"],
                    "大月" if lu["big_month"] else "小月", lu["days_in_month"], lu["shengxiao"]))
    if birth["true_solar_time"]:
        tst = birth["true_solar_time"]
        lines.append("真太阳时 %s（经度 %s°，修正 %+d 秒，来源%s）"
                     % (tst["true_solar"], tst["longitude"], tst["correction_seconds"], tst["source"]))
    dm = result["day_master"]
    lines.append("日主：%s（%s%s）" % (dm["stem"], dm["yinyang"], dm["wuxing"]))
    lines.append("")
    lines.append("| 柱 | 干支 | 天干十神 | 藏干 | 纳音 | 五行 | 空亡 |")
    lines.append("|---|---|---|---|---|---|---|")
    for key, label in PILLAR_LABELS:
        p = result["pillars"].get(key)
        if not p:
            lines.append("| %s | 未知 | — | — | — | — | — |" % label)
            continue
        cang = "、".join("%s(%s)" % (c["stem"], c["level"]) for c in p["canggan"])
        kong = "".join(p["kong"])
        lines.append("| %s | %s | %s | %s | %s | %s%s | %s |"
                     % (label, p["ganzhi"], p["shishen"] or "—", cang, p["nayin"],
                        p["wuxing"]["stem"], p["wuxing"]["branch"], kong))
    lines.append("")
    wc = result["wuxing_count"]
    ww = result["wuxing_weighted"]
    lines.append("五行（明字计数）：" + "　".join("%s%d" % (k, wc[k]) for k in wc))
    lines.append("五行（含藏干加权）：" + "　".join("%s%.2f" % (k, ww[k]) for k in ww))
    lines.append("")
    sc = result["shishen_count"]
    lines.append("十神（年/月/时干 + 藏干）：" + "　".join("%s%d" % (k, v) for k, v in sc.items() if v))
    lines.append("")
    dy = result["dayun"]
    if dy["qiyun"]:
        q = dy["qiyun"]
        lines.append("大运：%s　起运 %d 年 %d 个月 %d 天（%s 起运，参考交节 %s）"
                     % (dy["direction"], q["years"], q["months"], q["days"], q["start_date"],
                        q["reference_jie"]))
        lines.append("")
        lines.append("| 步 | 大运 | 十神 | 起始日 | 起运岁 | 年份 |")
        lines.append("|---|---|---|---|---|---|")
        for item in dy["list"]:
            lines.append("| %d | %s | %s | %s | %d | %d–%d |"
                         % (item["index"], item["ganzhi"], item["shishen"],
                            item["start_date"], item["start_age"],
                            item["start_year"], item["end_year"] - 1))
    else:
        lines.append("大运：未排（%s）" % ("缺 --sex" if not inp["sex"] else "信息不足"))
    lines.append("")
    lines.append("流年（锚定 %d 年）：" % (result["liunian"][0]["year"] if result["liunian"] else 0))
    lines.append("")
    lines.append("| 年份 | 干支 | 十神 | 虚岁 | 所属大运 |")
    lines.append("|---|---|---|---|---|")
    for item in result["liunian"]:
        lines.append("| %d | %s | %s | %d | %s |"
                     % (item["year"], item["ganzhi"], item["shishen"], item["age_xusui"],
                        ("第 %d 步" % item["dayun_index"]) if item["dayun_index"] else "未起运"))
    lines.append("")
    if result["shensha"]:
        lines.append("神煞：")
        for s in result["shensha"]:
            lines.append("- %s（%s，%s）：%s ／ %s"
                         % (s["name"], s["basis"], s["status"], "、".join(s["hits"]), s["rule"]))
    else:
        lines.append("神煞：常见神煞均未命中")
    lines.append("")
    for kw in result["kongwang"]:
        lines.append("空亡（%s %s，%s）：%s%s"
                     % (kw["pillar"], kw["ganzhi"], kw["xun"], "".join(kw["kong"]),
                        ("；命中 " + "、".join(kw["hits"])) if kw["hits"] else "；未命中四支"))
    if result["warnings"]:
        lines.append("")
        lines.append("警告：")
        for w in result["warnings"]:
            lines.append("- [%s] %s" % (w["code"], w["message"]))
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(
        prog="bazi.py",
        description="八字排盘（四柱/藏干/十神/纳音/五行/大运/流年/神煞/空亡），历法内核见 calendar_core")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--solar", help="公历生日 YYYY-MM-DD")
    g.add_argument("--lunar", help="农历生日 YYYY-MM-DD（闰月配 --leap）")
    p.add_argument("--leap", action="store_true", help="配合 --lunar 表示闰月")
    h = p.add_mutually_exclusive_group()
    h.add_argument("--hour", help="出生时点 HH:MM（北京时/当地标准时）")
    h.add_argument("--shichen", help="出生时辰：子丑寅卯辰巳午未申酉戌亥（取该时辰中点）")
    p.add_argument("--sex", help="男 或 女（缺省则不排大运并告警）")
    p.add_argument("--place", help="城市名（用于查经度，如 北京）")
    p.add_argument("--longitude", type=float, help="东经度数（给了就启用真太阳时）")
    p.add_argument("--meridian", type=float, default=120.0, help="标准经线，默认 120（中国）")
    p.add_argument("--deceased-year", type=int, help="已故年份：流年只推到这里")
    p.add_argument("--dayun-n", type=int, default=10, help="大运步数，默认 10")
    p.add_argument("--late-zi", choices=["next_day", "same_day"], default="next_day",
                   help="夜子时口径：next_day（默认，23:00 起用次日日柱）/ same_day")
    p.add_argument("--no-dst", action="store_true", help="关闭 1986–1991 夏令时自动修正")
    p.add_argument("--no-tst", action="store_true", help="关闭真太阳时（即使给了经度）")
    p.add_argument("--json", action="store_true", help="输出 JSON 信封")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.solar:
            y, m, d = _parse_ymd(args.solar, "--solar")
            note = {"calendar": "solar", "text": args.solar}
        else:
            ly, lm, ld = _parse_ymd(args.lunar, "--lunar")
            y, m, d = cal.lunar_to_solar(ly, lm, ld, args.leap)
            note = {"calendar": "lunar", "text": args.lunar, "leap": bool(args.leap)}
        hour = None
        minute = 0
        hour_text = None
        if args.hour is not None:
            hour, minute = _parse_hour(args.hour)
            hour_text = args.hour
        elif args.shichen is not None:
            name = str(args.shichen).strip()[:1]
            if name not in SHICHEN_HOUR:
                raise cal.DateError("时辰应为 子丑寅卯辰巳午未申酉戌亥 之一，收到 %r" % (args.shichen,))
            hour, minute = SHICHEN_HOUR[name], 0
            hour_text = "%s时" % name
        result, warnings = build_chart(
            (y, m, d), hour=hour, minute=minute, sex=args.sex, place=args.place,
            longitude=args.longitude, meridian=args.meridian, late_zi=args.late_zi,
            apply_tst=not args.no_tst, handle_dst=not args.no_dst,
            dayun_n=max(1, args.dayun_n), deceased_year=args.deceased_year,
            input_note=dict(note, hour_text=hour_text))
    except cal.DateError as exc:
        if args.json:
            print(json.dumps({"ok": False, "schema_version": SCHEMA_VERSION, "cmd": "bazi",
                              "engine": ENGINE,
                              "error": {"code": "BAD_DATE", "message": str(exc)}},
                             ensure_ascii=False))
        else:
            sys.stderr.write("错误：%s\n" % exc)
        return 2
    if args.json:
        payload = {
            "ok": True, "schema_version": SCHEMA_VERSION, "cmd": "bazi", "engine": ENGINE,
            "input": {
                "solar": result["input"]["solar"],
                "hour": result["input"]["hour"],
                "sex": result["input"]["sex"],
                "place": args.place or None,
                "longitude": args.longitude,
                "calendar": result["input"]["calendar"],
                "leap": bool(args.leap),
                "late_zi": args.late_zi,
                "true_solar_time": result["input"]["true_solar_time"],
                "deceased_year": args.deceased_year,
            },
            "result": result, "warnings": warnings, "seed": None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(_render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
