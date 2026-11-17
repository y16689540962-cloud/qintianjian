#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""风水：玄空飞星 / 命卦 / 八宅 / 流年紫白 / 建除黄黑道 / 择日。

职责
    六个子命令，共用同一套罗盘方位与历法口径：
      feixing  玄空飞星（运盘 + 山星 + 向星、旺山旺向/上山下水/双星会向会坐、兼向提示）
      mingua   命卦（三元命卦、东西四命、八宅四吉四凶方）
      bazhai   八宅（宅卦游年七星八方、可叠加命卦）
      liunian  流年（紫白年星九宫、太岁/岁破、三煞、五黄落宫）
      day      单日课（干支、建除十二神、黄道黑道、冲煞、宜忌、神煞）
      zeri     择日（先排凶、再排序的候选日列表）

输入
    feixing --facing 187|午|朝南  (--yun N | --built-year Y)  [--annual Y]
    mingua  --birth YYYY-MM-DD --sex 男|女
    bazhai  --facing 187  [--birth YYYY-MM-DD --sex 男|女]
    liunian --year 2026
    day     --date 2026-11-18
    zeri    --event 嫁娶 --start 2026-12-01 --end 2026-12-31 [--birth-year 1990]

输出
    §3 统一信封；各子命令 result 见 CONTRACT §6「fengshui.*」。

口径来源（对应 references/fengshui.md）
    · 洛书九宫飞泊、二十四山、三元龙顺逆：玄空飞星通法  school
    · 八宅游年以三爻变卦法定九星（生气/天医/延年/伏位/绝命/五鬼/六煞/祸害）  school
    · 命卦（男：1999−年 mod 9；女：年−1905 mod 9；中五男寄坤、女寄艮）  school
    · 建除十二神以月建起建、日支顺推；黄道黑道取「除危定执成开为黄、建满平破收闭为黑」  pub
    · 三煞依年支三合局；太岁即年支方，岁破为对冲  pub
    · 宜忌条目为通行通书分类，非经典原文  school

已知局限
    · 兼向（每山左右各 3°）只提示、不出替卦盘；替卦需按玄空替卦表另算
    · 命卦在 1900–1999 之外存在世纪边界口径分歧，脚本按连续（年星）口径算并发 SCHOOL_VARIANT
    · 日课只给建除黄黑道与硬性凶煞（月破/四离四绝/岁破/冲命主），不做神煞加权打分的黑箱
    · 不判阴阳宅形峦吉凶、不看罗盘度数以外的东西
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    import calendar_core as cc
except ImportError as _exc:  # pragma: no cover
    raise SystemExit("缺少 scripts/calendar_core.py（契约 §5）：%s" % _exc)

ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
CMD = "fengshui"

STEMS = cc.STEMS
BRANCHES = cc.BRANCHES
SHENGXIAO = cc.SHENGXIAO

# ===========================================================================
# 一、罗盘与九宫基础
# ===========================================================================

#: 洛书九宫 → 后天八卦方位名
GONG_DIRECTION: Dict[int, str] = {
    1: "北", 2: "西南", 3: "东", 4: "东南", 5: "中",
    6: "西北", 7: "西", 8: "东北", 9: "南",
}
GONG_TRIGRAM: Dict[int, str] = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}
GONG_COLOR: Dict[int, str] = {1: "一白", 2: "二黑", 3: "三碧", 4: "四绿", 5: "五黄", 6: "六白", 7: "七赤", 8: "八白", 9: "九紫"}
#: 顺飞宫序：由中宫起 5→6→7→8→9→1→2→3→4
FLY_ORDER: Tuple[int, ...] = (5, 6, 7, 8, 9, 1, 2, 3, 4)

#: 二十四山，自子起顺时针，每山 15°，子山跨 352.5°–7.5°
SHAN_24: Tuple[str, ...] = (
    "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
    "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬",
)
GONG_OF_SHAN: Dict[str, int] = {
    "子": 1, "癸": 1, "壬": 1,
    "丑": 8, "艮": 8, "寅": 8,
    "甲": 3, "卯": 3, "乙": 3,
    "辰": 4, "巽": 4, "巳": 4,
    "丙": 9, "午": 9, "丁": 9,
    "未": 2, "坤": 2, "申": 2,
    "庚": 7, "酉": 7, "辛": 7,
    "戌": 6, "乾": 6, "亥": 6,
}
#: 三元龙归属：天元龙（每卦正向）、地元龙（左上）、人元龙（右下）
YUAN_LONG: Dict[str, str] = {
    "子": "天", "午": "天", "卯": "天", "酉": "天", "乾": "天", "坤": "天", "艮": "天", "巽": "天",
    "甲": "地", "庚": "地", "壬": "地", "丙": "地", "辰": "地", "戌": "地", "丑": "地", "未": "地",
    "寅": "人", "申": "人", "巳": "人", "亥": "人", "癸": "人", "丁": "人", "乙": "人", "辛": "人",
}
#: 三元龙阴阳：天元乾艮坤巽阳、子午卯酉阴；地元甲庚壬丙阳、辰戌丑未阴；人元寅申巳亥阳、癸丁乙辛阴
_YANG_SHAN = {"乾", "艮", "坤", "巽", "甲", "庚", "壬", "丙", "寅", "申", "巳", "亥"}

#: 八方位词 → 所属 24 山（只给方位词时按此取中心度数）
DIRECTION_SHAN: Dict[str, str] = {
    "北": "子", "东北": "艮", "东": "卯", "东南": "巽",
    "南": "午", "西南": "坤", "西": "酉", "西北": "乾",
}

#: 八宅游年：翻转爻位集合 → 九星（三爻变卦法）
#: 位序 1=初爻 2=二爻 3=上爻；{} 为伏位
YOUNIAN_BY_FLIP: Dict[frozenset, str] = {
    frozenset(): "伏位",
    frozenset({3}): "生气",
    frozenset({1, 2}): "天医",
    frozenset({1, 2, 3}): "延年",
    frozenset({2}): "绝命",
    frozenset({2, 3}): "五鬼",
    frozenset({1, 3}): "六煞",
    frozenset({1}): "祸害",
}
YOUNIAN_JIXIONG: Dict[str, str] = {
    "生气": "吉", "天医": "吉", "延年": "吉", "伏位": "吉",
    "绝命": "凶", "五鬼": "凶", "六煞": "凶", "祸害": "凶",
}
#: 八宅九星五行（生气贪狼木、天医巨门土、延年武曲金、伏位左辅木、绝命破军金、五鬼廉贞火、六煞文曲水、祸害禄存土）
YOUNIAN_ELEMENT: Dict[str, str] = {
    "生气": "木", "天医": "土", "延年": "金", "伏位": "木",
    "绝命": "金", "五鬼": "火", "六煞": "水", "祸害": "土",
}

TRIGRAM_BITS: Dict[str, Tuple[int, int, int]] = {
    "乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
    "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0),
}
BITS_TRIGRAM: Dict[Tuple[int, int, int], str] = {v: k for k, v in TRIGRAM_BITS.items()}
#: 归藏：卦名 → 九宫数
TRIGRAM_GONG: Dict[str, int] = {"坎": 1, "坤": 2, "震": 3, "巽": 4, "乾": 6, "兑": 7, "艮": 8, "离": 9}
GONG_OF_TRIGRAM: Dict[int, str] = {v: k for k, v in TRIGRAM_GONG.items()}
GONG_OF_TRIGRAM[5] = "中"


# ===========================================================================
# 二、方位工具
# ===========================================================================

def normalize_deg(deg: float) -> float:
    return float(deg) % 360.0


def shan_of_deg(deg: float) -> str:
    """度数 → 二十四山名（子山中心 0°）。"""
    idx = int(((normalize_deg(deg) + 7.5) % 360.0) // 15.0)
    return SHAN_24[idx % 24]


def shan_center_deg(shan: str) -> float:
    return normalize_deg(SHAN_24.index(shan) * 15.0)


def shan_offset_deg(deg: float, shan: str) -> float:
    """给定度数偏离该山中心的角度（0–7.5）。"""
    diff = (normalize_deg(deg) - shan_center_deg(shan) + 180.0) % 360.0 - 180.0
    return abs(diff)


def parse_facing(raw: str) -> Tuple[float, str, List[Dict[str, str]]]:
    """解析 --facing：优先度数，其次二十四山名，再次八方位词。

    返回 (度数, 山名, warnings)。仅给方位词时按 §4 要求发 LOW_CONFIDENCE。

    度数输入且贴近山界（距 15° 网格边线 < 2°）时另发 CROSS_SHAN_RISK：
    二十四山每山 15°、山界在 ±7.5°，而罗盘/手机量向误差常 >3°，
    近界度数很容易被判到隔壁山、进而整盘飞星全错。山名输入本来就是粗判，不发此警告。
    """
    warnings: List[Dict[str, str]] = []
    text = str(raw).strip().replace("度", "").replace("°", "")
    try:
        deg = normalize_deg(float(text))
        shan = shan_of_deg(deg)
        edge_dist = round(7.5 - shan_offset_deg(deg, shan), 1)
        if edge_dist < 2.0:
            warnings.append({
                "code": "CROSS_SHAN_RISK",
                "message": "向首 %.1f° 距山界仅 %.1f°；罗盘/手机量向误差常 >3°，"
                           "可能落错山。建议复测，或按兼向处理" % (deg, edge_dist),
            })
        return deg, shan, warnings
    except ValueError:
        pass
    name = text.lstrip("朝坐向")
    if name in SHAN_24:
        return shan_center_deg(name), name, warnings
    if name in DIRECTION_SHAN:
        shan = DIRECTION_SHAN[name]
        warnings.append({
            "code": "LOW_CONFIDENCE",
            "message": "只给了方位词「%s」，按%s山中心 %.1f° 处理；实际坐向请给度数或二十四山名" % (
                raw, shan, shan_center_deg(shan)),
        })
        return shan_center_deg(shan), shan, warnings
    raise ValueError("无法解析坐向 %r：请给度数（0–360）、二十四山名（如 午）或方位词（如 朝南）" % (raw,))


# ===========================================================================
# 三、飞星
# ===========================================================================

def fly_stars(base: int, forward: bool = True) -> Dict[int, int]:
    """飞星：base 入中宫，按洛书宫序布九宫。forward=True 顺飞，False 逆飞。"""
    step = 1 if forward else -1
    stars: Dict[int, int] = {}
    for k, gong in enumerate(FLY_ORDER):
        stars[gong] = (base - 1 + step * k) % 9 + 1
    return stars


def _same_yuan_long_star_yinyang(star: int, target_shan: str) -> Tuple[bool, str]:
    """山星/向星入中之星的顺逆。

    通法：取该星「本宫」中与坐/向**同元龙**之山，以其阴阳定顺逆（阳顺阴逆）。
    本宫 = 该星的洛书原位九宫，例：入中 4 星，本宫为巽，天元龙山为巽（阳）。

    五黄（star=5）本宫为中宫，二十四山不入中，无「同元龙之山」可取；
    通行的退化处理是取**该山自身的三元龙阴阳**（阳顺阴逆）。此口径经三张公开盘逐宫校验：
      · 九运子山午向：山星五黄逆飞（子为天元龙、阴）→ 坎宫得双九紫，成双星到坐
      · 九运壬山丙向：山星五黄顺飞（壬为地元龙、阳）→ 离宫得双九紫，成双星到向
      · 八运丑山未向 / 未山丑向：五黄逆飞（丑未为地元龙、阴）→ 成旺山旺向
    """
    if star == 5:
        is_yang = target_shan in _YANG_SHAN
        return is_yang, "五黄入中（本宫无山可依），取该山三元龙自身阴阳：%s为%s，%s飞" % (
            target_shan, "阳" if is_yang else "阴", "顺" if is_yang else "逆")
    long_name = YUAN_LONG[target_shan]
    candidates = [s for s in SHAN_24 if GONG_OF_SHAN[s] == star and YUAN_LONG[s] == long_name]
    if not candidates:
        raise AssertionError("星%d 无%s元龙之山" % (star, long_name))
    sibling = candidates[0]
    is_yang = sibling in _YANG_SHAN
    return is_yang, "%d星本宫%s，%s元龙为%s（%s），%s飞" % (
        star, GONG_TRIGRAM[star], long_name, sibling,
        "阳" if is_yang else "阴", "顺" if is_yang else "逆")


def yun_of_year(year: int) -> int:
    """三元九运：1864 起一运，每运二十年。"""
    return ((int(year) - 1864) // 20) % 9 + 1


def year_zi_bai(year: int) -> int:
    """流年紫白年星（1984 七赤、2017 一白、2024 三碧、2026 一白）。"""
    return (2017 - int(year)) % 9 + 1


def feixing(facing_raw: str, yun: Optional[int], built_year: Optional[int],
            annual: Optional[int]) -> Dict[str, Any]:
    warnings: List[Dict[str, str]] = []
    facing_deg, xiang_shan, w1 = parse_facing(facing_raw)
    warnings.extend(w1)
    sitting_deg = normalize_deg(facing_deg + 180.0)
    shan_shan = shan_of_deg(sitting_deg)

    if yun is None and built_year is None:
        raise ValueError("feixing 需要 --yun（运）或 --built-year（建成年）之一")
    if yun is None:
        yun = yun_of_year(int(built_year))
        warnings.append({
            "code": "YUN_FROM_YEAR",
            "message": "由建成 %d 年推得 %d 运（三元九运：1864 起一运，每运二十年）" % (int(built_year), yun),
        })
    if not 1 <= int(yun) <= 9:
        raise ValueError("--yun 必须 1–9，收到 %r" % yun)
    yun = int(yun)

    # 兼向：每山 15°，中间 9° 为正（下卦），左右各 3° 为兼（替卦）
    off_xiang = shan_offset_deg(facing_deg, xiang_shan)
    off_shan = shan_offset_deg(sitting_deg, shan_shan)
    jian_xiang = off_xiang > 4.5
    tigua_hint = None
    if jian_xiang:
        tigua_hint = ("需替卦：向首 %s 山内偏 %.1f°，已越过 4.5° 正向区间。"
                      "替星口诀与兼向阈值各派不一（3° / 4.5° / 视山而定），本脚本不出替卦盘，"
                      "请按 references/fengshui.md 的替卦表另核。" % (xiang_shan, off_xiang))
        warnings.append({
            "code": "JIAN_XIANG",
            "message": "向首 %s 山内偏 %.1f°（>4.5°）已入兼向区间，正法须用替卦；本脚本只出下卦盘" % (
                xiang_shan, off_xiang),
        })
        warnings.append({
            "code": "SCHOOL_VARIANT",
            "message": "兼向分界各家不同（3°/4.5°/按山定），本脚本取「每山 9° 正向、两旁各 3° 兼向」；替卦不在本脚本范围内",
        })

    gong_shan = GONG_OF_SHAN[shan_shan]
    gong_xiang = GONG_OF_SHAN[xiang_shan]

    yun_pan = fly_stars(yun, True)
    shan_in = yun_pan[gong_shan]
    xiang_in = yun_pan[gong_xiang]
    shan_forward, shan_reason = _same_yuan_long_star_yinyang(shan_in, shan_shan)
    xiang_forward, xiang_reason = _same_yuan_long_star_yinyang(xiang_in, xiang_shan)
    shan_pan = fly_stars(shan_in, shan_forward)
    xiang_pan = fly_stars(xiang_in, xiang_forward)

    palaces = []
    for gong in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        palaces.append({
            "gong": gong,
            "trigram": GONG_TRIGRAM[gong],
            "direction": GONG_DIRECTION[gong],
            "yun_star": yun_pan[gong],
            "shan_star": shan_pan[gong],
            "xiang_star": xiang_pan[gong],
            "is_sitting": gong == gong_shan,
            "is_facing": gong == gong_xiang,
        })

    # 格局判定：以当运之星为旺星
    wang = yun
    shan_at_shan = shan_pan[gong_shan]
    xiang_at_xiang = xiang_pan[gong_xiang]
    shan_at_xiang = shan_pan[gong_xiang]
    xiang_at_shan = xiang_pan[gong_shan]
    flags: List[str] = []
    if shan_at_shan == wang and xiang_at_xiang == wang:
        pattern = "旺山旺向"
    elif shan_at_xiang == wang and xiang_at_shan == wang:
        pattern = "上山下水"
    elif shan_at_xiang == wang and xiang_at_xiang == wang:
        pattern = "双星到向"
        flags.append("双星劫（旧称）：山向两旺星同落向首")
    elif shan_at_shan == wang and xiang_at_shan == wang:
        pattern = "双星到坐"
        flags.append("双星劫（旧称）：山向两旺星同落坐山")
    else:
        pattern = "其他"
    if shan_at_shan != wang:
        flags.append("坐山宫山星%s，非当旺星%d" % (GONG_COLOR[shan_at_shan], wang))
    if xiang_at_xiang != wang:
        flags.append("向首宫向星%s，非当旺星%d" % (GONG_COLOR[xiang_at_xiang], wang))

    result: Dict[str, Any] = {
        "facing_deg": round(facing_deg, 2),
        "sitting_deg": round(sitting_deg, 2),
        "shan": shan_shan,
        "xiang": xiang_shan,
        "shan_label": "坐山",
        "xiang_label": "向首",
        "shan_gong": gong_shan,
        "xiang_gong": gong_xiang,
        "jian_xiang": jian_xiang,
        "tigua_hint": tigua_hint,
        "shan_offset_deg": round(off_shan, 2),
        "xiang_offset_deg": round(off_xiang, 2),
        "yun": yun,
        "pan_type": "下卦" + ("（兼向未替卦）" if jian_xiang else ""),
        "yun_pan": {str(g): yun_pan[g] for g in sorted(yun_pan)},
        "shan_pan": {str(g): shan_pan[g] for g in sorted(shan_pan)},
        "xiang_pan": {str(g): xiang_pan[g] for g in sorted(xiang_pan)},
        "palaces": palaces,
        "pattern": pattern,
        "pattern_flags": flags,
        "wang_star": wang,
        "shan_ruzhong": shan_in,
        "xiang_ruzhong": xiang_in,
        "shan_direction": "顺飞" if shan_forward else "逆飞",
        "xiang_direction": "顺飞" if xiang_forward else "逆飞",
        "shan_rule": shan_reason,
        "xiang_rule": xiang_reason,
        "warnings": warnings,
        "school_notes": [
            "运盘恒顺飞；山星取运盘坐山宫之数入中，向星取运盘向首宫之数入中",
            "山/向星顺逆：取该入中之星「本宫」中与坐/向同元龙之山的阴阳，阳顺阴逆",
            "五黄入中（本宫无山）：取该山三元龙自身阴阳定顺逆；已对九运子午/壬丙、八运丑未三盘逐宫校验",
            "pattern 取值固定为 旺山旺向 / 上山下水 / 双星到向 / 双星到坐 / 其他，便于程序判断",
            "「双星劫」为双星到向/到坐的旧称，与「七星打劫」不是同一术语，勿混用",
        ],
    }
    if annual is not None:
        ystar = year_zi_bai(int(annual))
        ap = fly_stars(ystar, True)
        result["annual"] = {
            "year": int(annual),
            "year_star": ystar,
            "year_star_name": GONG_COLOR[ystar],
            "palaces": [{"gong": g, "direction": GONG_DIRECTION[g], "star": ap[g]} for g in (1, 2, 3, 4, 5, 6, 7, 8, 9)],
            "wu_huang_at": [g for g in ap if ap[g] == 5][0],
        }
    return result


# ===========================================================================
# 四、命卦
# ===========================================================================

GUA_NAME: Dict[int, str] = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}
DONG_SI = {"坎", "震", "巽", "离"}
XI_SI = {"坤", "兑", "乾", "艮"}


def mingua_number(year: int, sex: str) -> int:
    """三元命卦数：男 1999−年 mod 9；女 年−1905 mod 9；得 5 者男寄坤(2)、女寄艮(8)。"""
    if sex == "男":
        n = (1999 - int(year)) % 9 + 1
    elif sex == "女":
        n = (int(year) - 1905) % 9 + 1
    else:
        raise ValueError("--sex 只能是 男 或 女，收到 %r" % (sex,))
    if n == 5:
        n = 2 if sex == "男" else 8
    return n


def _flip_set(a: str, b: str) -> frozenset:
    ba, bb = TRIGRAM_BITS[a], TRIGRAM_BITS[b]
    return frozenset(i + 1 for i in range(3) if ba[i] != bb[i])


def younian_of(zhai_gua: str) -> Dict[str, Dict[str, Any]]:
    """八宅游年：以宅卦/命卦为伏位，推八方九星。"""
    if zhai_gua not in TRIGRAM_BITS:
        raise ValueError("未知卦名 %r" % (zhai_gua,))
    out: Dict[str, Dict[str, Any]] = {}
    for other in ("乾", "兑", "离", "震", "巽", "坎", "艮", "坤"):
        star = YOUNIAN_BY_FLIP[_flip_set(zhai_gua, other)]
        gong = TRIGRAM_GONG[other]
        out[star] = {
            "star": star,
            "gua": other,
            "gong": gong,
            "direction": GONG_DIRECTION[gong],
            "element": YOUNIAN_ELEMENT[star],
            "jixiong": YOUNIAN_JIXIONG[star],
        }
    return out


def mingua(birth: str, sex: str) -> Dict[str, Any]:
    warnings: List[Dict[str, str]] = []
    year = _parse_year(birth)
    n = mingua_number(year, sex)
    gua = GUA_NAME[n]
    group = "东四命" if gua in DONG_SI else "西四命"
    yy = younian_of(gua)
    four_good = [yy[k] for k in ("生气", "天医", "延年", "伏位")]
    four_bad = [yy[k] for k in ("绝命", "五鬼", "六煞", "祸害")]
    if not 1900 <= year <= 1999:
        warnings.append({
            "code": "SCHOOL_VARIANT",
            "message": "命卦在 1900–1999 之外存在世纪边界口径分歧（后两位法会差一位），本脚本按连续年星口径算得 %d%s" % (n, gua),
        })
    warnings.append({
        "code": "SCHOOL_VARIANT",
        "message": "命卦以立春为年界的流派与以农历正月初一为界者不同；本脚本按出生公历年直接计算，年初生人请按立春校正",
    })
    result = {
        "birth": birth,
        "sex": sex,
        "year": year,
        "gua_number": n,
        "gua": gua,
        "group": group,
        "four_good": [{"star": r["star"], "direction": r["direction"], "element": r["element"]} for r in four_good],
        "four_bad": [{"star": r["star"], "direction": r["direction"], "element": r["element"]} for r in four_bad],
        "you_nian": {k: {"direction": v["direction"], "element": v["element"], "jixiong": v["jixiong"]}
                     for k, v in yy.items()},
        "warnings": warnings,
        "school_notes": [
            "四吉方：生气、天医、延年、伏位；四凶方：绝命、五鬼、六煞、祸害",
            "东四命喜住东四宅（坎震巽离），西四命喜住西四宅（坤兑乾艮）",
        ],
    }
    return result


def _parse_year(birth: str) -> int:
    text = str(birth).strip()
    part = text.split("-")[0]
    try:
        year = int(part)
    except ValueError:
        raise ValueError("--birth 需为 YYYY-MM-DD 或 YYYY，收到 %r" % (birth,))
    if not 1900 <= year <= 2100:
        raise ValueError("年份超出 1900–2100：%d" % year)
    return year


# ===========================================================================
# 五、八宅
# ===========================================================================

def bazhai(facing_raw: str, birth: Optional[str], sex: Optional[str]) -> Dict[str, Any]:
    warnings: List[Dict[str, str]] = []
    facing_deg, xiang_shan, w1 = parse_facing(facing_raw)
    warnings.extend(w1)
    sitting_deg = normalize_deg(facing_deg + 180.0)
    shan_shan = shan_of_deg(sitting_deg)
    gong = GONG_OF_SHAN[shan_shan]
    zhai_gua = GONG_TRIGRAM[gong]
    if zhai_gua == "中":
        raise ValueError("坐山落入中宫，无法定宅卦")
    yy = younian_of(zhai_gua)
    order = ("伏位", "生气", "天医", "延年", "绝命", "五鬼", "六煞", "祸害")
    stars = [yy[k] for k in order]
    result: Dict[str, Any] = {
        "facing_deg": round(facing_deg, 2),
        "sitting_deg": round(sitting_deg, 2),
        "shan": shan_shan,
        "xiang": xiang_shan,
        "zhai_gua": zhai_gua,
        "zhai_name": "%s宅" % zhai_gua,
        "axis": "%s山%s向" % (shan_shan, xiang_shan),
        "group": "东四宅" if zhai_gua in DONG_SI else "西四宅",
        "you_nian": [
            {"star": s["star"], "jixiong": s["jixiong"], "direction": s["direction"],
             "gua": s["gua"], "element": s["element"]}
            for s in stars
        ],
        "ji_directions": [s["direction"] for s in stars if s["jixiong"] == "吉"],
        "xiong_directions": [s["direction"] for s in stars if s["jixiong"] == "凶"],
        "warnings": warnings,
        "school_notes": ["宅卦以坐山定（乾宅即坐乾向巽）；游年九星以三爻变卦法推"],
    }
    if birth:
        if not sex:
            raise ValueError("给 --birth 时必须同时给 --sex")
        m = mingua(birth, sex)
        result["mingua"] = {k: m[k] for k in ("gua", "gua_number", "group", "four_good", "four_bad")}
        warnings.extend(m["warnings"])
        zhai_ok = (m["gua"] in DONG_SI and zhai_gua in DONG_SI) or (m["gua"] in XI_SI and zhai_gua in XI_SI)
        result["ming_zhai_he"] = "命宅相合" if zhai_ok else "命宅不合"
        if not zhai_ok:
            warnings.append({
                "code": "SCHOOL_VARIANT",
                "message": "命卦%s（%s）与宅卦%s（%s）不同组，八宅家判为「命宅不合」，可取其四吉方布局化解" % (
                    m["gua"], m["group"], zhai_gua, result["group"]),
            })
    return result


# ===========================================================================
# 六、流年
# ===========================================================================

SAN_SHA_BY_GROUP: Dict[str, Tuple[str, str]] = {
    "申子辰": ("南", "巳午未"),
    "亥卯未": ("西", "申酉戌"),
    "寅午戌": ("北", "亥子丑"),
    "巳酉丑": ("东", "寅卯辰"),
}
BRANCH_DIRECTION: Dict[str, str] = {
    "子": "北", "丑": "东北", "寅": "东北", "卯": "东", "辰": "东南", "巳": "东南",
    "午": "南", "未": "西南", "申": "西南", "酉": "西", "戌": "西北", "亥": "西北",
}


def _san_he_group(branch: str) -> str:
    """地支 → 三合局名（"申子辰" 等）。注意 key 才是三合支，value 是三煞方位与所煞三支。"""
    for key in SAN_SHA_BY_GROUP:
        if branch in key:
            return key
    raise AssertionError("地支 %s 无三合局" % branch)


def liunian(year: int) -> Dict[str, Any]:
    import datetime as _dt
    dt = _dt.datetime(int(year), 6, 15, 12, 0)
    yganzhi = cc.ganzhi_year(dt)
    year_stem, year_branch = yganzhi
    zhi = year_zi_bai(int(year))
    pan = fly_stars(zhi, True)
    wu_huang = [g for g in pan if pan[g] == 5][0]
    group = _san_he_group(year_branch)
    sha_dir, sha_branches = SAN_SHA_BY_GROUP[group]
    chong = BRANCHES[(BRANCHES.index(year_branch) + 6) % 12]
    warnings: List[Dict[str, str]] = []
    result = {
        "year": int(year),
        "year_ganzhi": year_star_join(year_stem, year_branch),
        "zodiac": SHENGXIAO[BRANCHES.index(year_branch)],
        "tai_sui": {"branch": year_branch, "direction": BRANCH_DIRECTION[year_branch]},
        "sui_po": {"branch": chong, "direction": BRANCH_DIRECTION[chong]},
        "san_sha": {"group": group, "direction": sha_dir, "branches": sha_branches},
        "zi_bai": {
            "year_star": zhi,
            "year_star_name": GONG_COLOR[zhi],
            "palaces": [{"gong": g, "direction": GONG_DIRECTION[g], "star": pan[g]} for g in (1, 2, 3, 4, 5, 6, 7, 8, 9)],
            "wu_huang_gong": wu_huang,
            "wu_huang_direction": GONG_DIRECTION[wu_huang],
        },
        "warnings": warnings,
        "school_notes": [
            "流年紫白：年星入中顺飞九宫，年星按 2017 一白递降（1984 七赤、2024 三碧）",
            "三煞依年支三合局：申子辰煞南、亥卯未煞西、寅午戌煞北、巳酉丑煞东",
            "太岁为年支本方位，岁破为其对冲；五黄到方忌动土修造（流派通说）",
        ],
    }
    return result


def year_star_join(stem: str, branch: str) -> str:
    return "%s%s" % (stem, branch)


# ===========================================================================
# 七、日课（建除、黄黑道、冲煞、宜忌）
# ===========================================================================

JIANCHU: Tuple[str, ...] = ("建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭")
HUANG_DAO_JIANCHU = {"除", "危", "定", "执", "成", "开"}

JIANCHU_YI: Dict[str, List[str]] = {
    "建": ["出行", "上任", "会友", "祈福", "祭祀", "求嗣"],
    "除": ["沐浴", "扫舍", "理发", "求医", "解除", "出火"],
    "满": ["祭祀", "开市", "交易", "修造", "入宅", "补垣"],
    "平": ["修造", "平治道涂", "粉饰", "栽种"],
    "定": ["祭祀", "嫁娶", "进人口", "开市", "修造", "入宅"],
    "执": ["修造", "立券", "嫁娶", "建屋", "捕捉"],
    "破": ["破屋坏垣", "求医", "拆卸"],
    "危": ["安床", "祭祀", "祈福"],
    "成": ["嫁娶", "开市", "入学", "入宅", "安葬", "修造", "交易"],
    "收": ["纳财", "进人口", "纳畜", "收货", "入仓"],
    "开": ["祭祀", "祈福", "开市", "交易", "出行", "入学", "修造"],
    "闭": ["筑堤", "埋穴", "补垣", "塞穴"],
}
JIANCHU_JI: Dict[str, List[str]] = {
    "建": ["动土", "开仓", "掘井", "破土"],
    "除": ["嫁娶", "开市", "立券"],
    "满": ["服药", "栽种", "安葬"],
    "平": ["祈福", "开市", "安葬", "开渠"],
    "定": ["诉讼", "出行", "移徙"],
    "执": ["开市", "出行", "移徙"],
    "破": ["嫁娶", "开市", "动土", "入宅", "安葬", "立券"],
    "危": ["登高", "行船", "嫁娶", "出行"],
    "成": ["诉讼", "争执"],
    "收": ["开市", "出行", "安葬", "开仓"],
    "开": ["安葬", "破土"],
    "闭": ["开市", "出行", "求医", "开仓", "安葬"],
}

#: 四离（二分二至前一日）/ 四绝（四立前一日）
SI_LI_TERMS = {"春分": "四离", "秋分": "四离", "夏至": "四离", "冬至": "四离"}
SI_JUE_TERMS = {"立春": "四绝", "立夏": "四绝", "立秋": "四绝", "立冬": "四绝"}

#: 天赦日：春戊寅、夏甲午、秋戊申、冬甲子
TIAN_SHE: Dict[str, str] = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}
#: 月德：寅午戌月丙、申子辰月壬、亥卯未月甲、巳酉丑月庚
YUE_DE: Dict[str, str] = {
    "寅": "丙", "午": "丙", "戌": "丙",
    "申": "壬", "子": "壬", "辰": "壬",
    "亥": "甲", "卯": "甲", "未": "甲",
    "巳": "庚", "酉": "庚", "丑": "庚",
}


def _season_of_month_branch(branch: str) -> str:
    if branch in "寅卯辰":
        return "春"
    if branch in "巳午未":
        return "夏"
    if branch in "申酉戌":
        return "秋"
    return "冬"


def jianchu_of(day_branch: str, month_branch: str) -> str:
    """建除十二神：以月建为「建」，日支顺推。"""
    offset = (BRANCHES.index(day_branch) - BRANCHES.index(month_branch)) % 12
    return JIANCHU[offset]


def huangdao_of(jianchu: str) -> str:
    return "黄道" if jianchu in HUANG_DAO_JIANCHU else "黑道"


def sha_direction_of(branch: str) -> Tuple[str, str]:
    group = _san_he_group(branch)
    return SAN_SHA_BY_GROUP[group]


def chong_of(branch: str, stem: Optional[str] = None) -> Dict[str, Any]:
    """日冲：通书体例「冲猴(壬申)煞北」——生肖取对冲支，(干支) 取日干配对冲支。"""
    idx = BRANCHES.index(branch)
    target = BRANCHES[(idx + 6) % 12]
    zodiac = SHENGXIAO[(idx + 6) % 12]
    sha_dir = sha_direction_of(branch)[0]
    paired = ("%s%s" % (stem, target)) if stem else target
    return {
        "branch": target,
        "zodiac": zodiac,
        "ganzhi": paired,
        "sha": sha_dir,
        "direction": BRANCH_DIRECTION[target],
        "phrase": "冲%s(%s)煞%s" % (zodiac, paired, sha_dir),
        "detail": "%s日冲%s（%s），煞%s" % (branch, target, zodiac, sha_dir),
    }


def day_detail(date_str: str) -> Dict[str, Any]:
    import datetime as _dt
    y, mo, d = _parse_date(date_str)
    dt = _dt.datetime(y, mo, d, 12, 0)
    dgz = cc.ganzhi_day(dt)
    mgz = cc.ganzhi_month(dt)
    ygz = cc.ganzhi_year(dt)
    jc = jianchu_of(dgz[1], mgz[1])
    hd = huangdao_of(jc)
    chong = chong_of(dgz[1], dgz[0])
    shensha: List[Dict[str, str]] = []

    # 月破：日支冲月建（即建除为「破」）
    if jc == "破":
        shensha.append({"name": "月破", "type": "凶", "note": "日支冲月建，月内最忌大事"})
    # 岁破：日支冲年支
    if dgz[1] == BRANCHES[(BRANCHES.index(ygz[1]) + 6) % 12]:
        shensha.append({"name": "岁破", "type": "凶", "note": "日支冲流年太岁"})
    # 四离四绝：次日交二分二至/四立
    try:
        nxt = cc.next_jieqi(dt)
    except Exception:
        nxt = None
    if nxt and _is_next_day(dt, nxt):
        if nxt["name"] in SI_LI_TERMS:
            shensha.append({"name": "四离", "type": "凶", "term": nxt["name"],
                            "note": "次日交%s；四离日忌出行、嫁娶、动土" % nxt["name"]})
        elif nxt["name"] in SI_JUE_TERMS:
            shensha.append({"name": "四绝", "type": "凶", "term": nxt["name"],
                            "note": "次日交%s；四绝日忌出行、上任、嫁娶" % nxt["name"]})
    # 天赦
    season = _season_of_month_branch(mgz[1])
    if dgz[0] + dgz[1] == TIAN_SHE[season]:
        shensha.append({"name": "天赦", "type": "吉", "note": "%s季天赦日（%s），百事大吉" % (season, TIAN_SHE[season])})
    # 月德
    if dgz[0] == YUE_DE[mgz[1]]:
        shensha.append({"name": "月德", "type": "吉", "note": "%s月月德在%s干" % (mgz[1], YUE_DE[mgz[1]])})
    # 旬空日
    xun = _xun_kong(dgz)
    if dgz[1] in xun:
        shensha.append({"name": "旬空", "type": "凶", "note": "%s日空亡%s%s，忌签约开市" % (
            dgz[0] + dgz[1], xun[0], xun[1])})

    yi = list(JIANCHU_YI[jc])
    ji = list(JIANCHU_JI[jc])
    warnings: List[Dict[str, str]] = []
    jq = None
    try:
        jq = cc.jieqi_of_day(dt)
    except Exception:
        jq = None
    if jq:
        warnings.append({
            "code": "JIEQI_BOUNDARY",
            "message": "当日交%s（%s），月建按交节时刻切换，午前午后月建可能不同" % (jq["name"], jq["datetime"]),
        })
    result = {
        "date": date_str,
        "ganzhi": {"year": ygz[0] + ygz[1], "month": mgz[0] + mgz[1], "day": dgz[0] + dgz[1]},
        "jianchu": jc,
        "huangdao": hd,
        "chong": chong["phrase"],
        "chong_detail": chong,
        "sha": sha_direction_of(dgz[1])[0],
        "yi": yi,
        "ji": ji,
        "shensha": shensha,
        "xunkong": xun,
        "warnings": warnings,
        "school_notes": [
            "建除十二神以月建起「建」、日支顺推；黄道黑道取「除危定执成开为黄、建满平破收闭为黑」",
            "宜忌为通行通书分类（流派口径），不代替具体事项的十神/神煞细断",
        ],
    }
    return result


def _is_next_day(dt, term: Dict[str, Any]) -> bool:
    import datetime as _dt
    term_dt = _dt.datetime.strptime(term["datetime"], "%Y-%m-%d %H:%M")
    return (term_dt.date() - dt.date()).days == 1


def _xun_kong(gz: Tuple[str, str]) -> List[str]:
    si = STEMS.index(gz[0])
    bi = BRANCHES.index(gz[1])
    idx = 0
    for i in range(60):
        if i % 10 == si and i % 12 == bi:
            idx = i
            break
    base = (idx // 10) * 10
    return [BRANCHES[(base + 10) % 12], BRANCHES[(base + 11) % 12]]


def _parse_date(text: str) -> Tuple[int, int, int]:
    import datetime as _dt
    try:
        y, mo, d = [int(x) for x in str(text).split("-")]
        _dt.date(y, mo, d)
    except Exception:
        raise ValueError("日期需为 YYYY-MM-DD，收到 %r" % (text,))
    return y, mo, d


# ===========================================================================
# 八、择日
# ===========================================================================

EVENT_RULES: Dict[str, Dict[str, List[str]]] = {
    "嫁娶": {"good": ["定", "成", "满", "执"], "bad": ["破", "危", "闭", "平", "收"]},
    "开市": {"good": ["开", "成", "满", "定"], "bad": ["破", "收", "闭", "平"]},
    "出行": {"good": ["建", "开", "除", "成"], "bad": ["破", "收", "闭", "危"]},
    "入宅": {"good": ["成", "满", "定", "开"], "bad": ["破", "闭", "平", "收"]},
    "安葬": {"good": ["成", "定", "建"], "bad": ["破", "满", "收", "开", "闭"]},
    "动土": {"good": ["平", "定", "成"], "bad": ["建", "破", "闭"]},
    "祭祀": {"good": ["建", "满", "开", "成", "定"], "bad": ["破", "闭"]},
    "求医": {"good": ["除", "破"], "bad": []},
    "立券": {"good": ["执", "定", "成"], "bad": ["破", "收"]},
    "修造": {"good": ["定", "成", "开", "平", "执"], "bad": ["破", "闭"]},
}


def zeri(event: str, start: str, end: str, birth_years: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    import datetime as _dt
    if event not in EVENT_RULES:
        raise ValueError("未知事项 %r，可选：%s" % (event, " / ".join(sorted(EVENT_RULES))))
    y1, m1, d1 = _parse_date(start)
    y2, m2, d2 = _parse_date(end)
    begin = _dt.date(y1, m1, d1)
    finish = _dt.date(y2, m2, d2)
    if finish < begin:
        raise ValueError("--end 早于 --start")
    if (finish - begin).days > 366:
        raise ValueError("择日区间上限 366 天，收到 %d 天" % (finish - begin).days)

    warnings: List[Dict[str, str]] = []
    ming_list: List[Dict[str, Any]] = []
    seen_years = set()
    for by in list(birth_years or []):
        by = int(by)
        if not 1900 <= by <= 2100:
            raise ValueError("--birth-year 超出 1900–2100：%d" % by)
        if by in seen_years:
            continue
        seen_years.add(by)
        bdt = _dt.datetime(by, 6, 15, 12, 0)
        bgz = cc.ganzhi_year(bdt)
        ming_list.append({
            "year": by,
            "ganzhi": bgz[0] + bgz[1],
            "branch": bgz[1],
            "zodiac": SHENGXIAO[BRANCHES.index(bgz[1])],
        })
    if ming_list:
        warnings.append({
            "code": "LOW_CONFIDENCE",
            "message": "命主年支取出生年中位干支：%s；年初生人须按立春校正" % "、".join(
                "%d 年 %s（%s，年支%s）" % (m["year"], m["ganzhi"], m["zodiac"], m["branch"]) for m in ming_list),
        })

    candidates: List[Dict[str, Any]] = []
    cur = begin
    while cur <= finish:
        info = day_detail(cur.strftime("%Y-%m-%d"))
        jc = info["jianchu"]
        reasons: List[str] = []
        blockers: List[str] = []
        # 先排凶（硬性红线）：blockers 一律写成人话，可直接贴给用户
        month_branch = info["ganzhi"]["month"][1]
        day_branch = info["ganzhi"]["day"][1]
        for ss in info["shensha"]:
            if ss["name"] == "月破":
                blockers.append("月破（%s月%s日）" % (month_branch, day_branch))
            elif ss["name"] in ("四离", "四绝"):
                blockers.append("%s（次日交%s）" % (ss["name"], ss.get("term", "")))
            elif ss["name"] == "岁破":
                blockers.append("岁破（%s日冲太岁%s）" % (info["ganzhi"]["day"], info["ganzhi"]["year"][1]))
        for m in ming_list:
            mb = m["branch"]
            if day_branch == BRANCHES[(BRANCHES.index(mb) + 6) % 12]:
                blockers.append("冲命主（%d %s年%s，日支%s%s冲）" % (
                    m["year"], m["ganzhi"], m["zodiac"], m["branch"], day_branch))
            elif day_branch == mb:
                blockers.append("伏吟命主（%d %s年%s，日支%s值年支）" % (
                    m["year"], m["ganzhi"], m["zodiac"], day_branch))
        if jc in EVENT_RULES[event]["bad"]:
            blockers.append("建除「%s」于%s不宜" % (jc, event))

        score = 60
        if jc in EVENT_RULES[event]["good"]:
            score += 20
            reasons.append("建除「%s」于%s为吉" % (jc, event))
        if info["huangdao"] == "黄道":
            score += 10
            reasons.append("黄道日")
        else:
            score -= 5
            reasons.append("黑道日")
        for ss in info["shensha"]:
            if ss["type"] == "吉":
                score += 8
                reasons.append("%s（%s）" % (ss["name"], ss["note"]))
        if blockers:
            score -= 40 * len(blockers)
        score = max(0, min(100, score))
        candidates.append({
            "date": info["date"],
            "ganzhi": info["ganzhi"]["day"],
            "jianchu": jc,
            "huangdao": info["huangdao"],
            "score": score,
            "reasons": reasons,
            "blockers": blockers,
            "yi": info["yi"],
        })
        cur += _dt.timedelta(days=1)

    usable = [c for c in candidates if not c["blockers"]]
    usable.sort(key=lambda c: (-c["score"], c["date"]))
    blocked = [c for c in candidates if c["blockers"]]
    result = {
        "event": event,
        "start": start,
        "end": end,
        "birth_year": [m["year"] for m in ming_list] or None,
        "ming_list": ming_list,
        "ming_branch": ming_list[0]["branch"] if len(ming_list) == 1 else [m["branch"] for m in ming_list],
        "candidates": usable,
        "blocked": blocked,
        "summary": {
            "total_days": len(candidates),
            "usable_days": len(usable),
            "blocked_days": len(blocked),
            "best": usable[0]["date"] if usable else None,
        },
        "warnings": warnings,
        "school_notes": [
            "先排凶再排序：月破/四离四绝/岁破/冲命主 为一票否决（blockers），余下按分值排序",
            "分值构成为本脚本自定（建除宜忌 + 黄道 + 吉神，区间 0–100），只用于排序，不构成吉凶断言",
        ],
    }
    return result


# ===========================================================================
# 九、人类可读输出
# ===========================================================================

def _grid(palaces: List[Dict[str, Any]], mode: str) -> List[str]:
    """九宫排布（上南下北，左东右西，与传统罗盘同）。"""
    cell: Dict[int, str] = {}
    for p in palaces:
        g = p["gong"]
        if mode == "feixing":
            cell[g] = "%s/%s/%s" % (p["yun_star"], p["shan_star"], p["xiang_star"])
        elif mode == "yun":
            cell[g] = str(p["yun_star"])
    rows = [(4, 9, 2), (3, 5, 7), (8, 1, 6)]
    out = []
    names = {1: "坎北", 2: "坤西南", 3: "震东", 4: "巽东南", 5: "中", 6: "乾西北", 7: "兑西", 8: "艮东北", 9: "离南"}
    for row in rows:
        out.append(" | ".join("%s %s" % (names[g], cell.get(g, "-")) for g in row))
    return out


def render_text(cmd: str, result: Dict[str, Any]) -> str:
    out: List[str] = []
    if cmd == "feixing":
        out.append("玄空飞星 · %s山%s向（%d 运）" % (result["shan"], result["xiang"], result["yun"]))
        out.append("向首 %.2f° / 坐山 %.2f°；盘型：%s" % (result["facing_deg"], result["sitting_deg"], result["pan_type"]))
        out.append("格局：%s" % result["pattern"])
        for f in result["pattern_flags"]:
            out.append("- %s" % f)
        out.append("")
        out.append("入中：山星 %d（%s）、向星 %d（%s）" % (
            result["shan_ruzhong"], result["shan_direction"], result["xiang_ruzhong"], result["xiang_direction"]))
        out.append("顺逆依据：山 %s；向 %s" % (result["shan_rule"], result["xiang_rule"]))
        out.append("")
        out.append("九宫（运/山/向；上南下北）：")
        for line in _grid(result["palaces"], "feixing"):
            out.append("  " + line)
        if result.get("annual"):
            a = result["annual"]
            out.append("")
            out.append("流年 %d：%s入中，五黄到%s" % (a["year"], a["year_star_name"], GONG_DIRECTION[a["wu_huang_at"]]))
    elif cmd == "mingua":
        out.append("命卦 · %s（%s 年生）" % (result["gua"], result["birth"]))
        out.append("卦数 %d，%s" % (result["gua_number"], result["group"]))
        out.append("")
        out.append("四吉方：")
        for r in result["four_good"]:
            out.append("- %s（%s，%s）" % (r["direction"], r["star"], r["element"]))
        out.append("四凶方：")
        for r in result["four_bad"]:
            out.append("- %s（%s，%s）" % (r["direction"], r["star"], r["element"]))
    elif cmd == "bazhai":
        out.append("八宅 · %s（%s）" % (result["zhai_name"], result["axis"]))
        out.append("宅属%s" % result["group"])
        if "ming_zhai_he" in result:
            out.append("命宅：%s" % result["ming_zhai_he"])
        out.append("")
        out.append("| 九星 | 吉凶 | 方位 | 卦 | 五行 |")
        out.append("|---|---|---|---|---|")
        for r in result["you_nian"]:
            out.append("| %s | %s | %s | %s | %s |" % (r["star"], r["jixiong"], r["direction"], r["gua"], r["element"]))
    elif cmd == "liunian":
        out.append("流年 %d（%s %s年）" % (result["year"], result["year_ganzhi"], result["zodiac"]))
        out.append("太岁 %s（%s）；岁破 %s（%s）" % (
            result["tai_sui"]["branch"], result["tai_sui"]["direction"],
            result["sui_po"]["branch"], result["sui_po"]["direction"]))
        out.append("三煞 %s（%s–%s）" % (
            result["san_sha"]["direction"], result["san_sha"]["branches"][0], result["san_sha"]["branches"][2]))
        out.append("紫白：%s入中，五黄落%s" % (
            result["zi_bai"]["year_star_name"], result["zi_bai"]["wu_huang_direction"]))
        out.append("")
        out.append("| 宫 | 方位 | 年星 |")
        out.append("|---|---|---|")
        for p in result["zi_bai"]["palaces"]:
            out.append("| %d | %s | %s |" % (p["gong"], p["direction"], GONG_COLOR[p["star"]]))
    elif cmd == "day":
        out.append("日课 · %s（%s）" % (result["date"], result["ganzhi"]["day"]))
        out.append("年 %s / 月 %s / 日 %s" % (result["ganzhi"]["year"], result["ganzhi"]["month"], result["ganzhi"]["day"]))
        out.append("建除：%s　黄黑道：%s　冲煞：%s" % (result["jianchu"], result["huangdao"], result["chong"]))
        out.append("旬空：%s" % " ".join(result["xunkong"]))
        out.append("宜：%s" % "、".join(result["yi"]))
        out.append("忌：%s" % "、".join(result["ji"]))
        if result["shensha"]:
            out.append("神煞：")
            for ss in result["shensha"]:
                out.append("- %s（%s）：%s" % (ss["name"], ss["type"], ss["note"]))
    elif cmd == "zeri":
        s = result["summary"]
        out.append("择日 · %s　%s ～ %s" % (result["event"], result["start"], result["end"]))
        for m in result.get("ming_list") or []:
            out.append("命主：%d 年 %s（%s，年支%s）" % (m["year"], m["ganzhi"], m["zodiac"], m["branch"]))
        out.append("共 %d 日，可用 %d，凶阻 %d；首选 %s" % (
            s["total_days"], s["usable_days"], s["blocked_days"], s["best"] or "无"))
        out.append("")
        out.append("| 名次 | 日期 | 日干支 | 建除 | 黄黑 | 分 | 依据 |")
        out.append("|---|---|---|---|---|---|---|")
        if not result["candidates"]:
            out.append("| - | （区间内无可用的无凶日） | - | - | - | - | - |")
        for i, c in enumerate(result["candidates"][:15], 1):
            out.append("| %d | %s | %s | %s | %s | %d | %s |" % (
                i, c["date"], c["ganzhi"], c["jianchu"], c["huangdao"], c["score"], "；".join(c["reasons"]) or "-"))
        if result["blocked"]:
            out.append("")
            out.append("已排除（%d 日）：" % len(result["blocked"]))
            for c in result["blocked"][:10]:
                out.append("- %s %s：%s" % (c["date"], c["ganzhi"], "；".join(c["blockers"])))
    if result.get("warnings"):
        out.append("")
        out.append("提示：")
        for w in result["warnings"]:
            out.append("- [%s] %s" % (w["code"], w["message"]))
    return "\n".join(out)


# ===========================================================================
# 十、CLI
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fengshui.py",
        description="风水：feixing 玄空飞星 / mingua 命卦 / bazhai 八宅 / liunian 流年 / day 日课 / zeri 择日")
    sub = p.add_subparsers(dest="sub", required=True)

    f = sub.add_parser("feixing", help="玄空飞星运盘与山向飞星")
    f.add_argument("--facing", required=True, help="向首度数（0–360）、二十四山名或方位词")
    f.add_argument("--yun", type=int, help="运数 1–9")
    f.add_argument("--built-year", type=int, help="建成年份，用推运数")
    f.add_argument("--annual", type=int, help="附加流年紫白盘")

    m = sub.add_parser("mingua", help="命卦与东西四命")
    m.add_argument("--birth", required=True, help="出生日期 YYYY-MM-DD 或年份")
    m.add_argument("--sex", required=True, choices=["男", "女"], help="性别")

    b = sub.add_parser("bazhai", help="八宅游年七星")
    b.add_argument("--facing", required=True, help="向首度数、二十四山名或方位词")
    b.add_argument("--birth", help="出生日期 YYYY-MM-DD 或年份")
    b.add_argument("--sex", choices=["男", "女"], help="性别")

    l = sub.add_parser("liunian", help="流年紫白、太岁、岁破、三煞、五黄")
    l.add_argument("--year", type=int, required=True, help="公历年")

    d = sub.add_parser("day", help="单日日课：建除、黄黑道、冲煞、宜忌")
    d.add_argument("--date", required=True, help="YYYY-MM-DD")

    z = sub.add_parser("zeri", help="择日候选")
    z.add_argument("--event", required=True, help="事项：" + " / ".join(EVENT_RULES.keys()))
    z.add_argument("--start", required=True, help="起始日 YYYY-MM-DD")
    z.add_argument("--end", required=True, help="结束日 YYYY-MM-DD")
    z.add_argument("--birth-year", type=int, action="append",
                   help="命主出生年，可重复传入（合婚/入宅常需双方），如 --birth-year 1990 --birth-year 1992")

    p.add_argument("--json", action="store_true", help="输出 JSON（默认人类可读）")
    # 让 --json 写在子命令之后也生效（契约 §4 的调用示例是 feixing ... --json）；
    # 用 SUPPRESS 默认值，避免子parser把父级的 True 覆盖回 False
    for sp in (f, m, b, l, d, z):
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="输出 JSON（默认人类可读；写在本子命令前后皆可）")
    return p


def dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    if args.sub == "feixing":
        result = feixing(args.facing, args.yun, args.built_year, args.annual)
    elif args.sub == "mingua":
        result = mingua(args.birth, args.sex)
    elif args.sub == "bazhai":
        result = bazhai(args.facing, args.birth, args.sex)
    elif args.sub == "liunian":
        result = liunian(args.year)
    elif args.sub == "day":
        result = day_detail(args.date)
    elif args.sub == "zeri":
        result = zeri(args.event, args.start, args.end, args.birth_year)
    else:
        raise ValueError("未知子命令 %r" % (args.sub,))
    result["sub"] = args.sub
    return result


def _payload_input(args: argparse.Namespace) -> Dict[str, Any]:
    keys = ("sub", "facing", "yun", "built_year", "annual", "birth", "sex", "year", "date",
            "event", "start", "end", "birth_year")
    return {k: getattr(args, k, None) for k in keys if k != "sub"}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload_input = _payload_input(args)
    try:
        result = dispatch(args)
    except Exception as exc:  # 统一转信封 error + exit 2（契约 §9）
        code = "BAD_INPUT"
        if isinstance(exc, cc.DateError):
            code = "BAD_DATE"
        if args.json:
            sys.stdout.write(json.dumps({
                "ok": False, "schema_version": SCHEMA_VERSION, "cmd": CMD, "engine": ENGINE,
                "input": payload_input, "error": {"code": code, "message": str(exc)},
            }, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stderr.write("错误：%s\n" % exc)
        return 2
    envelope = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": payload_input,
        "result": result,
        "warnings": result.get("warnings", []),
        "seed": None,
    }
    if args.json:
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_text(args.sub, result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
