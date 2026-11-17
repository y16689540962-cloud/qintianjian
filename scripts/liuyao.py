#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻纳甲（京房纳甲 / 火珠林体系）——起卦、装卦、断卦要素。

职责
    给定起卦方式（三枚铜钱 / 大衍蓍草 / 手输六爻）与时间，输出本卦、变卦、
    纳甲、世应、六亲、六神、伏神、月建日辰、旬空、月破。

输入
    --coins / --yarrow / --lines 101011（自下而上，1 阳 0 阴，配 --moving 3,5 指定动爻）
    [--date YYYY-MM-DD] [--hour HH:MM] [--seed N] [--ask 事由] [--json]

输出
    §3 统一信封；result 见 CONTRACT §6「liuyao」最小集：method / date /
    day_ganzhi / month_ganzhi / ben_gua / bian_gua / lines[6] / shi / ying /
    fushen[] / warnings[]，另加 xunkong / year_ganzhi / shichen / school_notes。

口径来源（对应 references/liuyao.md）
    · 八宫卦序、世应、纳甲、六亲、六神：京房纳甲，《火珠林》《卜筮正宗》通行法  pub
    · 伏神取本宫首卦同位之爻：通行法  pub
    · 旬空以日干支旬首定：通行法  pub
    · 变爻六亲以本卦宫论 vs 以变卦宫论：两派并存，本脚本同时给出  school

已知局限
    · 不做旺衰量化评分（月建/日辰生克只给「月破」「旬空」两种硬事实，不下吉凶断语）
    · 六神起例按日干，夜子时（23:00 后）是否换日按 calendar_core 口径（子初换日）
    · 蓍草法按经典「分二、挂一、揲四、归奇」流程，随机分策服从均匀分布，
      结果分布近似经典 9:8:7:6 = 3:7:5:1/16，未做精确配比（真实蓍草亦为近似）
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- 同目录导入历法内核（契约 §5 冻结签名） ---------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    import calendar_core as cc
except ImportError as _exc:  # pragma: no cover - 环境缺文件时给出可读错误
    raise SystemExit("缺少 scripts/calendar_core.py（契约 §5）：%s" % _exc)

ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
CMD = "liuyao"

STEMS = cc.STEMS
BRANCHES = cc.BRANCHES

# ===========================================================================
# 一、基础表
# ===========================================================================

#: 八卦三爻，自下而上（初、二、三），1 阳 0 阴
TRIGRAMS: Dict[str, Tuple[int, int, int]] = {
    "乾": (1, 1, 1),
    "兑": (1, 1, 0),
    "离": (1, 0, 1),
    "震": (1, 0, 0),
    "巽": (0, 1, 1),
    "坎": (0, 1, 0),
    "艮": (0, 0, 1),
    "坤": (0, 0, 0),
}
TRIGRAM_BY_BITS: Dict[Tuple[int, int, int], str] = {v: k for k, v in TRIGRAMS.items()}

#: 六十四卦名（上卦, 下卦）→ 卦名；通行卦序表  pub
GUA_NAMES: Dict[Tuple[str, str], str] = {
    ("乾", "乾"): "乾为天", ("乾", "兑"): "天泽履", ("乾", "离"): "天火同人",
    ("乾", "震"): "天雷无妄", ("乾", "巽"): "天风姤", ("乾", "坎"): "天水讼",
    ("乾", "艮"): "天山遁", ("乾", "坤"): "天地否",
    ("兑", "乾"): "泽天夬", ("兑", "兑"): "兑为泽", ("兑", "离"): "泽火革",
    ("兑", "震"): "泽雷随", ("兑", "巽"): "泽风大过", ("兑", "坎"): "泽水困",
    ("兑", "艮"): "泽山咸", ("兑", "坤"): "泽地萃",
    ("离", "乾"): "火天大有", ("离", "兑"): "火泽睽", ("离", "离"): "离为火",
    ("离", "震"): "火雷噬嗑", ("离", "巽"): "火风鼎", ("离", "坎"): "火水未济",
    ("离", "艮"): "火山旅", ("离", "坤"): "火地晋",
    ("震", "乾"): "雷天大壮", ("震", "兑"): "雷泽归妹", ("震", "离"): "雷火丰",
    ("震", "震"): "震为雷", ("震", "巽"): "雷风恒", ("震", "坎"): "雷水解",
    ("震", "艮"): "雷山小过", ("震", "坤"): "雷地豫",
    ("巽", "乾"): "风天小畜", ("巽", "兑"): "风泽中孚", ("巽", "离"): "风火家人",
    ("巽", "震"): "风雷益", ("巽", "巽"): "巽为风", ("巽", "坎"): "风水涣",
    ("巽", "艮"): "风山渐", ("巽", "坤"): "风地观",
    ("坎", "乾"): "水天需", ("坎", "兑"): "水泽节", ("坎", "离"): "水火既济",
    ("坎", "震"): "水雷屯", ("坎", "巽"): "水风井", ("坎", "坎"): "坎为水",
    ("坎", "艮"): "水山蹇", ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜", ("艮", "兑"): "山泽损", ("艮", "离"): "山火贲",
    ("艮", "震"): "山雷颐", ("艮", "巽"): "山风蛊", ("艮", "坎"): "山水蒙",
    ("艮", "艮"): "艮为山", ("艮", "坤"): "山地剥",
    ("坤", "乾"): "地天泰", ("坤", "兑"): "地泽临", ("坤", "离"): "地火明夷",
    ("坤", "震"): "地雷复", ("坤", "巽"): "地风升", ("坤", "坎"): "地水师",
    ("坤", "艮"): "地山谦", ("坤", "坤"): "坤为地",
}

#: 八宫（京房八宫卦序的宫主）→ 宫五行
PALACE_ELEMENT: Dict[str, str] = {
    "乾": "金", "兑": "金", "离": "火", "震": "木",
    "巽": "木", "坎": "水", "艮": "土", "坤": "土",
}

#: 世爻位置：本宫卦/一世…五世/游魂/归魂  pub
GENERATIONS: Tuple[str, ...] = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
SHI_POS_BY_GENERATION: Tuple[int, ...] = (6, 1, 2, 3, 4, 5, 4, 3)

#: 八宫纳甲：内卦（初二三）与外卦（四五上）各三爻，(天干, 地支)  pub
#: 《火珠林》纳甲：乾纳甲壬、坤纳乙癸、震纳庚、巽纳辛、坎纳戊、离纳己、艮纳丙、兑纳丁
NAJIA: Dict[str, Dict[str, Tuple[Tuple[str, str], ...]]] = {
    "乾": {"nei": (("甲", "子"), ("甲", "寅"), ("甲", "辰")),
           "wai": (("壬", "午"), ("壬", "申"), ("壬", "戌"))},
    "坎": {"nei": (("戊", "寅"), ("戊", "辰"), ("戊", "午")),
           "wai": (("戊", "申"), ("戊", "戌"), ("戊", "子"))},
    "艮": {"nei": (("丙", "辰"), ("丙", "午"), ("丙", "申")),
           "wai": (("丙", "戌"), ("丙", "子"), ("丙", "寅"))},
    "震": {"nei": (("庚", "子"), ("庚", "寅"), ("庚", "辰")),
           "wai": (("庚", "午"), ("庚", "申"), ("庚", "戌"))},
    "巽": {"nei": (("辛", "丑"), ("辛", "亥"), ("辛", "酉")),
           "wai": (("辛", "未"), ("辛", "巳"), ("辛", "卯"))},
    "离": {"nei": (("己", "卯"), ("己", "丑"), ("己", "亥")),
           "wai": (("己", "酉"), ("己", "未"), ("己", "巳"))},
    "坤": {"nei": (("乙", "未"), ("乙", "巳"), ("乙", "卯")),
           "wai": (("癸", "丑"), ("癸", "亥"), ("癸", "酉"))},
    "兑": {"nei": (("丁", "巳"), ("丁", "卯"), ("丁", "丑")),
           "wai": (("丁", "亥"), ("丁", "酉"), ("丁", "未"))},
}

#: 地支五行
BRANCH_ELEMENT: Dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

#: 五行生克：key 生 value
SHENG: Dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
#: key 克 value
KE: Dict[str, str] = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

#: 六神顺序（自初爻起，按日干定起点后顺排）  pub
LIUSHEN_ORDER: Tuple[str, ...] = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
#: 日干 → 初爻六神  pub
LIUSHEN_START: Dict[str, str] = {
    "甲": "青龙", "乙": "青龙", "丙": "朱雀", "丁": "朱雀",
    "戊": "勾陈", "己": "螣蛇", "庚": "白虎", "辛": "白虎",
    "壬": "玄武", "癸": "玄武",
}

#: 六亲四类
LIUQIN_NAMES: Tuple[str, ...] = ("父母", "兄弟", "子孙", "妻财", "官鬼")


# ===========================================================================
# 二、派生：八宫归属（京房法，可由变爻推出，不硬编码 64 条）
# ===========================================================================

HexBits = Tuple[int, int, int, int, int, int]


def _flip(bits: Sequence[int], idx: int) -> HexBits:
    out = list(bits)
    out[idx] = 1 - out[idx]
    return (out[0], out[1], out[2], out[3], out[4], out[5])


def palace_sequence(palace: str) -> List[HexBits]:
    """由卦宫推出该宫八卦的六爻位（自下而上，6 位），顺序＝本宫、一世…五世、游魂、归魂。

    京房法：一世变初爻，逐世递变至五世；游魂复变四爻；归魂再复变内卦三爻。
    """
    tri = TRIGRAMS[palace]
    base: HexBits = (tri[0], tri[1], tri[2], tri[0], tri[1], tri[2])  # 八纯卦：内外同卦
    seq: List[HexBits] = [base]
    cur = base
    for i in range(5):  # 一世..五世：依次变初、二、三、四、五爻
        cur = _flip(cur, i)
        seq.append(cur)
    you = _flip(seq[5], 3)  # 游魂：五世卦再变四爻
    seq.append(you)
    gui = you
    for i in range(3):  # 归魂：游魂卦内卦三爻全变
        gui = _flip(gui, i)
    seq.append(gui)
    return seq


def _build_palace_index() -> Dict[Tuple[int, int, int], Tuple[str, int]]:
    index: Dict[Tuple[int, int, int], Tuple[str, int]] = {}
    for palace in TRIGRAMS:
        for gen, bits in enumerate(palace_sequence(palace)):
            if bits in index:
                raise AssertionError("八宫卦序重复：%s" % (bits,))
            index[bits] = (palace, gen)
    if len(index) != 64:
        raise AssertionError("八宫卦序未覆盖 64 卦：%d" % len(index))
    return index


PALACE_INDEX: Dict[Tuple[int, int, int], Tuple[str, int]] = _build_palace_index()


def bits_to_lines(bits: Sequence[int]) -> List[int]:
    """六位（初…上）→ [初,二,三,四,五,上]"""
    return [int(b) for b in bits]


def split_trigrams(lines: Sequence[int]) -> Tuple[str, str]:
    """六爻位（自下而上）→ (上卦名, 下卦名)"""
    lower = (lines[0], lines[1], lines[2])
    upper = (lines[3], lines[4], lines[5])
    return TRIGRAM_BY_BITS[upper], TRIGRAM_BY_BITS[lower]


def gua_name(lines: Sequence[int]) -> str:
    upper, lower = split_trigrams(lines)
    return GUA_NAMES[(upper, lower)]


def liuqin_of(me: str, other: str) -> str:
    """以「我」（卦宫五行）论六亲。"""
    if other == me:
        return "兄弟"
    if SHENG[other] == me:
        return "父母"      # 生我者父母
    if SHENG[me] == other:
        return "子孙"      # 我生者子孙
    if KE[other] == me:
        return "官鬼"      # 克我者官鬼
    return "妻财"          # 我克者妻财


def najia_of(lines: Sequence[int]) -> List[Dict[str, str]]:
    """纳甲：按上下卦取内外卦干支，返回 6 条（初→上）。"""
    upper, lower = split_trigrams(lines)
    out: List[Dict[str, str]] = []
    for stem, branch in NAJIA[lower]["nei"]:
        out.append({"stem": stem, "branch": branch})
    for stem, branch in NAJIA[upper]["wai"]:
        out.append({"stem": stem, "branch": branch})
    return out


def shi_ying_of(gen: int) -> Tuple[int, int]:
    shi = SHI_POS_BY_GENERATION[gen]
    ying = shi + 3 if shi <= 3 else shi - 3
    return shi, ying


def zhuang_gua(lines: Sequence[int], day_stem: str) -> List[Dict[str, Any]]:
    """装卦主体：纳甲 + 六亲 + 六神 + 世应标记。"""
    palace, gen = PALACE_INDEX[tuple(lines)]
    me = PALACE_ELEMENT[palace]
    shi, ying = shi_ying_of(gen)
    najia = najia_of(lines)
    start = LIUSHEN_ORDER.index(LIUSHEN_START[day_stem])
    rows: List[Dict[str, Any]] = []
    for i in range(6):
        branch = najia[i]["branch"]
        elem = BRANCH_ELEMENT[branch]
        rows.append({
            "pos": i + 1,
            "yinyang": "阳" if lines[i] else "阴",
            "najia": {"stem": najia[i]["stem"], "branch": branch},
            "wuxing": elem,
            "liuqin": liuqin_of(me, elem),
            "liushen": LIUSHEN_ORDER[(start + i) % 6],
            "shi": (i + 1) == shi,
            "ying": (i + 1) == ying,
        })
    return rows


def fushen_of(lines: Sequence[int]) -> List[Dict[str, Any]]:
    """伏神：本宫首卦（八纯卦）有而本卦全缺的六亲，取其同位之爻伏于本卦该爻下。"""
    palace, _gen = PALACE_INDEX[tuple(lines)]
    me = PALACE_ELEMENT[palace]
    present = set()
    rows = zhuang_gua(lines, "甲")
    for row in rows:
        present.add(row["liuqin"])
    first = palace_sequence(palace)[0]  # 本宫首卦（八纯卦）
    first_rows = zhuang_gua(first, "甲")
    missing = [q for q in LIUQIN_NAMES if q not in present]
    out: List[Dict[str, Any]] = []
    for i in range(6):
        fq = first_rows[i]["liuqin"]
        if fq in missing:
            out.append({
                "pos": i + 1,
                "liuqin": fq,
                "najia": first_rows[i]["najia"],
                "wuxing": first_rows[i]["wuxing"],
                "feishen_liuqin": rows[i]["liuqin"],
                "feishen_najia": rows[i]["najia"],
                "note": "本卦无%s，取%s宫首卦%s同位之爻为伏神" % (fq, palace, gua_name(first)),
            })
    _ = me
    return out


def xunkong_of(day_ganzhi: Tuple[str, str]) -> List[str]:
    """旬空：日干支所在旬的两个空亡支。"""
    idx = _ganzhi_index(day_ganzhi)
    base = (idx // 10) * 10
    return [BRANCHES[(base + 10) % 12], BRANCHES[(base + 11) % 12]]


def _ganzhi_index(gz: Tuple[str, str]) -> int:
    stem, branch = gz
    si = STEMS.index(stem)
    bi = BRANCHES.index(branch)
    for i in range(60):
        if i % 10 == si and i % 12 == bi:
            return i
    raise ValueError("非法干支 %s%s" % (stem, branch))


def chong_branch(branch: str) -> str:
    """六冲：相距六位的地支。"""
    return BRANCHES[(BRANCHES.index(branch) + 6) % 12]


# ===========================================================================
# 三、起卦
# ===========================================================================

#: 铜钱：背（无字面）记 3 为阳，字面记 2 为阴；三枚之和 6/7/8/9  pub
COIN_BACK = 3
COIN_FACE = 2


def toss_coins(rng: random.Random) -> Tuple[int, List[int]]:
    """三枚铜钱掷一次 → (爻值 6/7/8/9, 三枚铜钱各自数值)。"""
    coins = [COIN_BACK if rng.randint(0, 1) else COIN_FACE for _ in range(3)]
    return sum(coins), coins


def yarrow_change(rng: random.Random, count: int) -> int:
    """大衍一变：分二、挂一、揲四、归奇，返回剩余策数。"""
    left = rng.randint(1, count - 2)
    right = count - left - 1  # 挂一，取于右策
    rem_left = left % 4 or 4
    rem_right = right % 4 or 4
    return count - (1 + rem_left + rem_right)


def toss_yarrow(rng: random.Random) -> int:
    """大衍三变成一爻 → 爻值 6/7/8/9。"""
    count = 49
    for _ in range(3):
        count = yarrow_change(rng, count)
    return count // 4


def lines_from_values(values: Sequence[int]) -> Tuple[List[int], List[bool]]:
    """爻值序列 → (六爻位, 是否动爻)。老阳 9 / 老阴 6 为动。"""
    bits: List[int] = []
    moving: List[bool] = []
    for v in values:
        if v == 6:
            bits.append(0)
            moving.append(True)
        elif v == 7:
            bits.append(1)
            moving.append(False)
        elif v == 8:
            bits.append(0)
            moving.append(False)
        elif v == 9:
            bits.append(1)
            moving.append(True)
        else:
            raise ValueError("爻值只能是 6/7/8/9，收到 %r" % (v,))
    if len(bits) != 6:
        raise ValueError("必须六爻，收到 %d 爻" % len(bits))
    return bits, moving


def cast(method: str, rng: Optional[random.Random], lines_arg: Optional[str],
         moving_arg: Optional[str]) -> Tuple[List[int], List[bool], List[Dict[str, Any]], List[Dict[str, str]]]:
    """起卦统一入口。

    返回 (六爻位, 动爻, 每爻掷卦明细, warnings)。
    """
    warnings: List[Dict[str, str]] = []
    details: List[Dict[str, Any]] = []
    if method in ("coins", "yarrow"):
        if rng is None:
            raise ValueError("随机起卦必须给出 Random 实例")
        values: List[int] = []
        for i in range(6):
            if method == "coins":
                value, coins = toss_coins(rng)
                details.append({"pos": i + 1, "value": value, "coins": coins})
            else:
                value = toss_yarrow(rng)
                details.append({"pos": i + 1, "value": value})
            values.append(value)
    elif method == "manual":
        if not lines_arg:
            raise ValueError("手输六爻需要 --lines（如 101011，自下而上）")
        raw = lines_arg.strip()
        if len(raw) != 6 or any(ch not in "01" for ch in raw):
            raise ValueError("--lines 必须是 6 位 0/1 字符串（自下而上），收到 %r" % lines_arg)
        bits = [int(ch) for ch in raw]
        values: List[int] = [0] * 6  # 下面按动爻逐位填 6/7/8/9
        moving_idx: List[int] = []
        if moving_arg:
            for token in moving_arg.replace("，", ",").split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    pos = int(token)
                except ValueError:
                    raise ValueError("--moving 需为 1-6 的爻位，收到 %r" % token)
                if not 1 <= pos <= 6:
                    raise ValueError("--moving 爻位越界：%d" % pos)
                moving_idx.append(pos)
        for i, bit in enumerate(bits):
            is_moving = (i + 1) in moving_idx
            if is_moving:
                value = 9 if bit else 6
            else:
                value = 7 if bit else 8
            values[i] = value
            details.append({"pos": i + 1, "value": value})
        if not moving_idx:
            warnings.append({
                "code": "STATIC_GUA",
                "message": "手输无动爻（未给 --moving），按静卦处理，不给变卦",
            })
    else:
        raise ValueError("未知起卦方式：%r" % (method,))

    bits, moving = lines_from_values(values)
    if all(moving):
        warnings.append({
            "code": "SCHOOL_VARIANT",
            "message": "六爻皆动（六冲之极），各派取变卦法不一，本脚本按惯例给变卦并提示",
        })
    return bits, moving, details, warnings


# ===========================================================================
# 四、组装
# ===========================================================================

def _gua_block(lines: Sequence[int]) -> Dict[str, Any]:
    upper, lower = split_trigrams(lines)
    palace, gen = PALACE_INDEX[tuple(lines)]
    shi, ying = shi_ying_of(gen)
    return {
        "name": gua_name(lines),
        "trigrams": {"upper": upper, "lower": lower},
        "palace": palace,
        "palace_wuxing": PALACE_ELEMENT[palace],
        "generation": GENERATIONS[gen],
        "shi": shi,
        "ying": ying,
        "lines_bits": "".join(str(b) for b in lines),
    }


def analyze(method: str, date_str: str, hour: Optional[str], seed: Optional[int],
            lines_arg: Optional[str], moving_arg: Optional[str], ask: Optional[str],
            warnings_in: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """核心：返回 §3 信封（不含 ok/cmd/engine 外壳，由 main 组装）。"""
    warnings: List[Dict[str, str]] = list(warnings_in or [])

    # --- 时间 ---
    dt_probe = cc.now_tz()
    if hour:
        try:
            hh_s, mm_s = hour.split(":")
            hh, mm = int(hh_s), int(mm_s)
        except ValueError:
            raise ValueError("--hour 需为 HH:MM，收到 %r" % hour)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("--hour 越界：%r" % hour)
    else:
        hh, mm = 12, 0
    if date_str:
        try:
            y, mo, d = [int(x) for x in date_str.split("-")]
            import datetime as _dt
            _dt.date(y, mo, d)
        except Exception:
            raise ValueError("--date 需为 YYYY-MM-DD，收到 %r" % date_str)
    else:
        y, mo, d = dt_probe.year, dt_probe.month, dt_probe.day
        warnings.append({
            "code": "DATE_DEFAULTED",
            "message": "未给 --date，取当前北京时间 %04d-%02d-%02d" % (y, mo, d),
        })

    import datetime as _dt
    dt = _dt.datetime(y, mo, d, hh, mm)
    day_ganzhi = cc.ganzhi_day(dt)
    month_ganzhi = cc.ganzhi_month(dt)
    year_ganzhi = cc.ganzhi_year(dt)
    shichen = cc.shichen_of(hh, mm)

    if hour and hh == 23:
        warnings.append({
            "code": "LATE_ZI",
            "message": "夜子时（23:00 后）按子初换日，日辰取次日",
        })
    jq = None
    try:
        jq = cc.jieqi_of_day(dt)
    except Exception:
        jq = None
    if jq:
        warnings.append({
            "code": "JIEQI_BOUNDARY",
            "message": "当日在%s交节（%s），月建以交节时刻为界，请核对起卦时刻" % (jq["name"], jq["datetime"]),
        })

    # --- seed 与随机 ---
    if method in ("coins", "yarrow"):
        if seed is None:
            seed = random.SystemRandom().randrange(1, 10 ** 9)
            warnings.append({
                "code": "SEED_GENERATED",
                "message": "未给 --seed，已随机生成 %d 并写入信封，可用于回放" % seed,
            })
        rng: Optional[random.Random] = random.Random(seed)
    else:
        rng = None

    if method != "manual" and moving_arg:
        warnings.append({
            "code": "MOVING_IGNORED",
            "message": "--moving 只配合 --lines 手输使用，本次%s起卦的动爻由爻值决定，已忽略 --moving" % method,
        })
    bits, moving, details, cast_warnings = cast(method, rng, lines_arg, moving_arg)
    warnings.extend(cast_warnings)

    # --- 装卦 ---
    rows = zhuang_gua(bits, day_ganzhi[0])
    kong = xunkong_of(day_ganzhi)
    month_branch = month_ganzhi[1]
    for row in rows:
        row["moving"] = bool(moving[row["pos"] - 1])
        row["kong"] = row["najia"]["branch"] in kong
        row["yuepo"] = chong_branch(row["najia"]["branch"]) == month_branch
        row["chong_ri"] = chong_branch(row["najia"]["branch"]) == day_ganzhi[1]

    bian_lines: Optional[List[int]] = None
    if any(moving):
        bian_lines = list(bits)
        for i, mv in enumerate(moving):
            if mv:
                bian_lines[i] = 1 - bian_lines[i]

    # 变爻：两派六亲同时给出（school）
    if bian_lines is not None:
        bian_rows = zhuang_gua(bian_lines, day_ganzhi[0])
        bian_palace = PALACE_INDEX[tuple(bian_lines)][0]
        bian_me = PALACE_ELEMENT[bian_palace]
        for row in rows:
            if not row["moving"]:
                continue
            bi = row["pos"] - 1
            src_elem = BRANCH_ELEMENT[najia_of(bian_lines)[bi]["branch"]]
            row["bian"] = {
                "yinyang": "阳" if bian_lines[bi] else "阴",
                "najia": bian_rows[bi]["najia"],
                "wuxing": bian_rows[bi]["wuxing"],
                "liuqin_by_ben_gong": liuqin_of(PALACE_ELEMENT[PALACE_INDEX[tuple(bits)][0]], src_elem),
                "liuqin_by_bian_gong": liuqin_of(bian_me, src_elem),
            }
            if row["bian"]["liuqin_by_ben_gong"] != row["bian"]["liuqin_by_bian_gong"]:
                warnings.append({
                    "code": "SCHOOL_VARIANT",
                    "message": "第%d爻变出六亲两派不同：本卦宫论%s、变卦宫论%s" % (
                        row["pos"], row["bian"]["liuqin_by_ben_gong"], row["bian"]["liuqin_by_bian_gong"]),
                })

    ben = _gua_block(bits)
    bian = _gua_block(bian_lines) if bian_lines is not None else None
    fushen = fushen_of(bits)

    result: Dict[str, Any] = {
        "method": method,
        "date": "%04d-%02d-%02d" % (y, mo, d),
        "hour": ("%02d:%02d" % (hh, mm)) if hour else None,
        "shichen": shichen if hour else None,
        "ask": ask,
        "year_ganzhi": year_ganzhi[0] + year_ganzhi[1],
        "month_ganzhi": month_ganzhi[0] + month_ganzhi[1],
        "day_ganzhi": day_ganzhi[0] + day_ganzhi[1],
        "xunkong": kong,
        "ben_gua": ben,
        "bian_gua": bian,
        "lines": rows,
        "shi": ben["shi"],
        "ying": ben["ying"],
        "fushen": fushen,
        "cast": details,
        "warnings": warnings,
        "school_notes": [
            "变爻六亲：本卦宫论（火珠林通例）与变卦宫论（部分流派）并列，字段 liuqin_by_ben_gong / liuqin_by_bian_gong",
            "铜钱取背为阳（3）、字为阴（2），一背二字少阳、二背一字少阴、三背老阳、三字老阴",
            "蓍草按大衍之数五十其用四十有九，三变成爻，十八变成卦",
        ],
    }
    return {"result": result, "warnings": warnings, "seed": seed}


# ===========================================================================
# 五、人类可读输出
# ===========================================================================

def _fmt_gua(gua: Optional[Dict[str, Any]]) -> str:
    if not gua:
        return "（无变卦）"
    return "%s（%s宫%s，世%d应%d）" % (
        gua["name"], gua["palace"], gua["generation"], gua["shi"], gua["ying"])


def render_text(result: Dict[str, Any]) -> str:
    out: List[str] = []
    out.append("六爻纳甲 · %s" % {"coins": "三枚铜钱", "yarrow": "大衍蓍草", "manual": "手输六爻"}.get(
        result["method"], result["method"]))
    out.append("")
    when = result["date"] + (" " + result["hour"] if result["hour"] else "")
    out.append("起卦时间：%s（%s时）" % (when, result["shichen"]["branch"] if result["shichen"] else "未知"))
    out.append("四柱纪年：%s年 %s月 %s日" % (result["year_ganzhi"], result["month_ganzhi"], result["day_ganzhi"]))
    out.append("旬空：%s" % " ".join(result["xunkong"]))
    if result.get("ask"):
        out.append("所问：%s" % result["ask"])
    out.append("")
    out.append("本卦：%s" % _fmt_gua(result["ben_gua"]))
    out.append("变卦：%s" % _fmt_gua(result["bian_gua"]))
    out.append("")

    fushen_at: Dict[int, List[Dict[str, Any]]] = {}
    for f in result["fushen"]:
        fushen_at.setdefault(f["pos"], []).append(f)

    header = ("| 六神 | 六亲 | 伏神 | 本卦纳甲 | 世应 | 动 | 变爻纳甲 | 变爻六亲(本宫/变宫) |")
    out.append(header)
    out.append("|---|---|---|---|---|---|---|---|")
    for row in reversed(result["lines"]):
        bar = "▅▅▅▅▅" if row["yinyang"] == "阳" else "▅▅ ▅▅"
        sy = "世" if row["shi"] else ("应" if row["ying"] else "")
        flags = []
        if row["moving"]:
            flags.append("动")
        if row["kong"]:
            flags.append("旬空")
        if row["yuepo"]:
            flags.append("月破")
        if row["chong_ri"]:
            flags.append("日冲")
        fs = "、".join("%s%s%s" % (f["liuqin"], f["najia"]["stem"], f["najia"]["branch"])
                      for f in fushen_at.get(row["pos"], []))
        bian_najia = ""
        bian_qin = ""
        if "bian" in row:
            bian_najia = "%s%s%s" % (row["bian"]["najia"]["stem"], row["bian"]["najia"]["branch"],
                                     row["bian"]["wuxing"])
            bian_qin = "%s / %s" % (row["bian"]["liuqin_by_ben_gong"], row["bian"]["liuqin_by_bian_gong"])
        out.append("| %s | %s | %s | %s %s%s %s | %s | %s | %s | %s |" % (
            row["liushen"], row["liuqin"], fs or "-", bar,
            row["najia"]["stem"], row["najia"]["branch"], row["wuxing"],
            sy, "、".join(flags) or "-", bian_najia or "-", bian_qin or "-"))
    out.append("")
    out.append("（爻序自上而下为上六→初九，表内已倒序；本卦纳甲地支后附五行）")

    if result["fushen"]:
        out.append("")
        out.append("伏神：")
        for f in result["fushen"]:
            out.append("- 第%d爻 %s %s%s（%s）伏于 %s %s%s 之下" % (
                f["pos"], f["liuqin"], f["najia"]["stem"], f["najia"]["branch"], f["wuxing"],
                f["feishen_liuqin"], f["feishen_najia"]["stem"], f["feishen_najia"]["branch"]))
    if result["warnings"]:
        out.append("")
        out.append("提示：")
        for w in result["warnings"]:
            out.append("- [%s] %s" % (w["code"], w["message"]))
    return "\n".join(out)


# ===========================================================================
# 六、CLI
# ===========================================================================

def _envelope_ok(result: Dict[str, Any], warnings: List[Dict[str, str]],
                 payload_input: Dict[str, Any], seed: Optional[int]) -> Dict[str, Any]:
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": payload_input,
        "result": result,
        "warnings": warnings,
        "seed": seed,
    }


def _envelope_err(code: str, message: str, payload_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": payload_input or {},
        "error": {"code": code, "message": message},
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="liuyao.py",
        description="六爻纳甲：三枚铜钱 / 大衍蓍草 / 手输六爻起卦，纳甲装卦、世应六亲六神伏神、月建日辰旬空")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--coins", action="store_true", help="三枚铜钱起卦")
    mode.add_argument("--yarrow", action="store_true", help="大衍蓍草起卦")
    mode.add_argument("--lines", metavar="101011", help="手输六爻，自下而上，1 阳 0 阴")
    p.add_argument("--moving", metavar="3,5", help="配合 --lines 指定动爻爻位（自下而上 1-6，逗号分隔）")
    p.add_argument("--date", metavar="YYYY-MM-DD", help="起卦日期，缺省取当前北京时间")
    p.add_argument("--hour", metavar="HH:MM", help="起卦时刻，缺省不取时")
    p.add_argument("--seed", type=int, help="随机种子，便于回放")
    p.add_argument("--ask", help="所问事由")
    p.add_argument("--json", action="store_true", help="输出 JSON（默认人类可读）")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    method = "coins" if args.coins else ("yarrow" if args.yarrow else "manual")
    payload_input = {
        "method": method,
        "lines": args.lines,
        "moving": args.moving,
        "date": args.date,
        "hour": args.hour,
        "ask": args.ask,
    }
    try:
        out = analyze(
            method=method,
            date_str=args.date,
            hour=args.hour,
            seed=args.seed,
            lines_arg=args.lines,
            moving_arg=args.moving,
            ask=args.ask,
        )
    except Exception as exc:  # 统一转信封 error + exit 2（契约 §9）
        code = "BAD_INPUT"
        msg = str(exc)
        if isinstance(exc, cc.DateError) or "日期" in msg or "hour" in msg:
            code = "BAD_DATE"
        if args.json:
            sys.stdout.write(json.dumps(_envelope_err(code, msg, payload_input), ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stderr.write("错误：%s\n" % msg)
        return 2

    envelope = _envelope_ok(out["result"], out["warnings"], payload_input, out["seed"])
    if args.json:
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_text(out["result"]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
