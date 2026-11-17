# -*- coding: utf-8 -*-
"""qimen 时家奇门（转盘/飞盘）引擎测试。

**没有外部 oracle**：六个上游仓库里奇门只有一家实现且无许可证，不可借；因此本文件的
期望值全部来自手算规则推演，推导写在每个用例的 docstring 里。可复核的锚点有三类：
  1) 二十四节气三元局数口诀（「冬至惊蛰一七四…/夏至白露九三六…」）与符头定元规则；
  2) 三奇六仪阳顺阴逆布地盘、九星八门八神按洛书八宫环转动、值符加时干、值使加时支；
  3) 伏吟盘（甲子时值符值使各归本宫）这类"结构性必然结果"。

跑：cd <repo> && python3 -m unittest discover -s scripts/tests -q
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import subprocess
import sys
import unittest

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import qimen as Q  # noqa: E402

SCRIPT = os.path.join(_SCRIPTS, "qimen.py")

RING8 = [1, 8, 3, 4, 9, 2, 7, 6]


def pan(y, mo, d, h, mi=0, **kw):
    res, warns = Q.qimen_pan(dt.datetime(y, mo, d, h, mi), **kw)
    return res, warns


def table(res, key):
    return {p["gong"]: p[key] for p in res["palaces"] if p[key] is not None}


def codes(warnings):
    return [w["code"] for w in warnings]


class KnownPans(unittest.TestCase):
    """已知标准答案：逐宫手算核对。"""

    def test_yin6_2026_11_18_1030(self):
        """2026-11-18 10:30（丙申日 癸巳时）。

        手算：
          节气 = 立冬（2026-11-07 17:52 交节，阴遁；三元 6/9/3）。
          日柱丙申 = 六十甲子第 33 位（1 起）；往前推至甲/己日 = 甲午（第 31 位），
            符头地支午属子午卯酉 -> 上元 -> 阴遁六局。
          地盘（阴遁逆布 戊己庚辛壬癸丁丙乙 自六宫起）：
            戊6 己5 庚4 辛3 壬2 癸1 丁9 丙8 乙7。
          时柱癸巳：癸(10)巳(6) -> 六十甲子第 30 位 = 甲申旬首；旬首之仪 = 庚，
            庚落四宫 -> 值符天辅（四宫星）、值使杜门（四宫门）。
          时干癸落一宫 -> 天盘值符（天辅）加一宫。
          阴遁逆行，九星环 1-8-3-4-9-2-7-6 逆布：天辅1 天柱2 天任3 天蓬4
            天英6 天芮7(+天禽) 天冲8 天心9。
          值使：时辰在旬内序数 = 巳(6) - 申(9) = 9（0 起）；自四宫（环第 4 位）
            阴遁逆行 9 位 -> 环第 3 位 = 三宫，杜门落三宫。
          八门自三宫逆布：死1 休2 杜3 伤4 惊6 开7 景8 生9。
          八神自一宫逆布：值符1 六合2 九地3 玄武4 螣蛇6 太阴7 九天8 白虎9。
          天盘干随星走（星带本宫地盘干）：天辅(4宫庚)->1宫庚 … 天芮(2宫壬)->7宫壬，
            天禽带中五宫己。
          旬空：甲申旬 -> 午、未。
        """
        res, warnings = pan(2026, 11, 18, 10, 30)
        self.assertEqual(res["ju"], {"dun": "阴遁", "number": 6})
        self.assertEqual(res["jieqi"]["name"], "立冬")
        self.assertEqual(res["yuan"], "上元")
        self.assertEqual(res["yuan_detail"]["fu_tou"], "甲午")
        self.assertEqual(res["xunshou"], "甲申")
        self.assertEqual(res["xun_yi"], "庚")
        self.assertEqual(res["kongwang"], ["午", "未"])
        self.assertEqual(res["time"]["day_ganzhi"], "丙申")
        self.assertEqual(res["time"]["hour_ganzhi"], "癸巳")
        self.assertEqual(res["zhifu_star"], "天辅")
        self.assertEqual(res["zhishi_gate"], "杜门")
        self.assertEqual((res["zhifu_home_gong"], res["zhifu_landing_gong"]), (4, 1))
        self.assertEqual(res["zhishi_landing_gong"], 3)
        self.assertEqual(table(res, "earth_stem"),
                         {1: "癸", 2: "壬", 3: "辛", 4: "庚", 5: "己",
                          6: "戊", 7: "乙", 8: "丙", 9: "丁"})
        self.assertEqual(table(res, "star"),
                         {1: "天辅", 2: "天柱", 3: "天任", 4: "天蓬",
                          6: "天英", 7: "天芮", 8: "天冲", 9: "天心"})
        self.assertEqual(table(res, "sky_stem"),
                         {1: "庚", 2: "乙", 3: "丙", 4: "癸",
                          6: "丁", 7: "壬", 8: "辛", 9: "戊"})
        self.assertEqual(table(res, "gate"),
                         {1: "死门", 2: "休门", 3: "杜门", 4: "伤门",
                          6: "惊门", 7: "开门", 8: "景门", 9: "生门"})
        self.assertEqual(table(res, "deity"),
                         {1: "值符", 2: "六合", 3: "九地", 4: "玄武",
                          6: "螣蛇", 7: "太阴", 8: "九天", 9: "白虎"})
        # 天禽随天芮，并带中五宫之地盘干
        p7 = next(p for p in res["palaces"] if p["gong"] == 7)
        self.assertEqual(p7.get("star_extra"), "天禽")
        self.assertEqual(p7.get("sky_stem_extra"), "己")
        # 中五宫：设计如此——寄坤二宫，不列星门神
        p5 = next(p for p in res["palaces"] if p["gong"] == 5)
        self.assertEqual(p5["earth_stem"], "己")
        self.assertIsNone(p5["sky_stem"])
        self.assertIsNone(p5["star"])
        self.assertIsNone(p5["gate"])
        self.assertIsNone(p5["deity"])
        self.assertTrue(p5["is_center"])
        self.assertIn("SCHOOL_VARIANT", codes(warnings))

    def test_zhishi_gate_walks_ring8_not_ring9(self):
        """值使门走**八宫环并跳过中宫**（不是九宫含中宫）——最易被"顺手改成九宫"的一处。

        2026-11-18 三个时辰（同为阴遁六局，地盘不变）：
          10:30 癸巳（甲申旬，值使杜门原宫 4，旬内序数 9）-> 环 4-9 = -5 -> 三宫；
          13:30 乙未（甲午旬，旬首之仪辛落三宫，值使伤门原宫 3，旬内序数 1）-> 八宫；
          15:30 丙申（甲午旬同旬，值使伤门原宫 3，旬内序数 2）-> 坎一宫。
        若按九宫（含中宫）数，13:30 会落到二宫、15:30 会落到六宫——两说都有传承，
        本实现取八宫环，result.zhishi_rule 与 school_notes 里写明；这三条必须写死。
        """
        want = [("10:30", "癸巳", "甲申", "杜门", 4, 3, 9),
                ("13:30", "乙未", "甲午", "伤门", 3, 8, 1),
                ("15:30", "丙申", "甲午", "伤门", 3, 1, 2)]
        for hhmm, hour_gz, xun, gate, home, landing, steps in want:
            h, mi = [int(x) for x in hhmm.split(":")]
            res, _w = pan(2026, 11, 18, h, mi)
            self.assertEqual(res["time"]["hour_ganzhi"], hour_gz, hhmm)
            self.assertEqual(res["xunshou"], xun, hhmm)
            self.assertEqual(res["zhishi_gate"], gate, hhmm)
            self.assertEqual(res["zhifu_home_gong"], home, hhmm)
            self.assertEqual(res["zhishi_steps"], steps, hhmm)
            self.assertEqual(res["zhishi_landing_gong"], landing, hhmm)
        # 口径必须显式出现在 result 里，供下游与文档引用
        res, _w = pan(2026, 11, 18, 13, 30)
        self.assertIn("八宫环", res["zhishi_rule"])
        self.assertIn("跳过中宫", res["zhishi_rule"])
        self.assertTrue(any("八宫环" in n for n in res["school_notes"]))

    def test_yang1_甲子_shi_fuyin(self):
        """2026-01-04 23:00（甲子日 甲子时）-> 阳遁一局，伏吟盘。

        手算：
          冬至后（2026-01-05 才交小寒，此处仍在冬至三元 1/7/4 内），日柱甲子 ->
            符头 = 甲子，地支子 -> 上元 -> 阳遁一局。
          地盘：戊1 己2 庚3 辛4 壬5 癸6 丁7 丙8 乙9。
          甲子旬首，旬首之仪 = 戊落一宫 -> 值符天蓬、值使休门。
          时干甲 -> 用旬首之仪戊 -> 天盘值符加一宫，即**星门俱归本宫（伏吟）**。
          八神自一宫阳遁顺布：值符1 螣蛇8 太阴3 六合4 白虎9 玄武2 九地7 九天6。
          旬空：甲子旬 -> 戌、亥。
        """
        res, _w = pan(2026, 1, 4, 23, 0)
        self.assertEqual(res["ju"], {"dun": "阳遁", "number": 1})
        self.assertEqual(res["yuan"], "上元")
        self.assertEqual(res["xunshou"], "甲子")
        self.assertEqual(res["kongwang"], ["戌", "亥"])
        self.assertEqual((res["zhifu_star"], res["zhishi_gate"]), ("天蓬", "休门"))
        self.assertEqual(res["zhifu_landing_gong"], 1)
        self.assertEqual(res["zhishi_landing_gong"], 1)
        # 伏吟：九星与八门全在本宫，天盘干 = 地盘干
        for p in res["palaces"]:
            if p["gong"] == 5:
                continue
            self.assertEqual(p["star"], Q.STAR_HOME[p["gong"]])
            self.assertEqual(p["gate"], Q.GATE_HOME[p["gong"]])
            self.assertEqual(p["sky_stem"], p["earth_stem"])
        self.assertEqual(table(res, "deity"),
                         {1: "值符", 2: "玄武", 3: "太阴", 4: "六合",
                          6: "九天", 7: "九地", 8: "螣蛇", 9: "白虎"})
        # 夜子时：日柱已按子初换日
        self.assertTrue(res["time"]["late_zi"])
        self.assertIn("LATE_ZI", codes(_w))

    def test_yang1_yichou(self):
        """2026-01-05 01:00（甲子日 乙丑时）-> 阳遁一局。

        手算：
          时干乙 -> 地盘乙在九宫 -> 值符（天蓬）加离九宫；
          值使休门：时辰在旬内序数 = 丑(2) - 子(1) = 1，阳遁顺行自坎一宫进一位 -> 艮八宫。
          九星顺布自九宫：天蓬9 天英1 天任2 天柱3 天心4 天辅6 天冲7 天芮8(+禽)。
          八门自八宫顺布：休8 生3 伤4 杜9 景2 死7 惊6 开1。
          八神自九宫顺布：值符9 螣蛇2 太阴7 六合6 白虎1 玄武8 九地3 九天4。
        """
        res, _w = pan(2026, 1, 5, 1, 0)
        self.assertEqual(res["ju"], {"dun": "阳遁", "number": 1})
        self.assertEqual(res["time"]["hour_ganzhi"], "乙丑")
        self.assertEqual(res["zhifu_landing_gong"], 9)
        self.assertEqual(res["zhishi_landing_gong"], 8)
        self.assertEqual(table(res, "star"),
                         {1: "天英", 2: "天任", 3: "天柱", 4: "天心",
                          6: "天辅", 7: "天冲", 8: "天芮", 9: "天蓬"})
        self.assertEqual(table(res, "gate"),
                         {1: "开门", 2: "景门", 3: "生门", 4: "伤门",
                          6: "惊门", 7: "死门", 8: "休门", 9: "杜门"})
        self.assertEqual(table(res, "deity"),
                         {1: "白虎", 2: "螣蛇", 3: "九地", 4: "九天",
                          6: "六合", 7: "太阴", 8: "玄武", 9: "值符"})

    def test_yin9_yichou(self):
        """2026-07-04 01:00（甲子日 乙丑时）-> 阴遁九局。

        手算：
          夏至后（阴遁），日柱甲子 -> 符头甲子 -> 上元 -> 阴遁九局。
          地盘（阴遁逆布）：戊9 己8 庚7 辛6 壬5 癸4 丁3 丙2 乙1。
          甲子旬，旬首之仪戊落九宫 -> 值符天英、值使景门。
          时干乙落一宫 -> 天英加坎一宫；阴遁逆行，环 1-8-3-4-9-2-7-6 逆布：
            天英1 天心2 天冲3 天任4 天芮6(+禽) 天柱7 天辅8 天蓬9。
          值使景门原宫九宫（环第 5 位），旬内序数 1，阴遁退一位 -> 巽四宫。
          八门自四宫逆布：景4 死3 惊8 开1 休6 生7 伤2 杜9。
          八神自一宫逆布：值符1 螣蛇6 太阴7 六合2 白虎9 玄武4 九地3 九天8。
        """
        res, _w = pan(2026, 7, 4, 1, 0)
        self.assertEqual(res["ju"], {"dun": "阴遁", "number": 9})
        self.assertEqual((res["zhifu_star"], res["zhishi_gate"]), ("天英", "景门"))
        self.assertEqual((res["zhifu_home_gong"], res["zhifu_landing_gong"]), (9, 1))
        self.assertEqual(res["zhishi_landing_gong"], 4)
        self.assertEqual(table(res, "star"),
                         {1: "天英", 2: "天心", 3: "天冲", 4: "天任",
                          6: "天芮", 7: "天柱", 8: "天辅", 9: "天蓬"})
        self.assertEqual(table(res, "gate"),
                         {1: "开门", 2: "伤门", 3: "死门", 4: "景门",
                          6: "休门", 7: "生门", 8: "惊门", 9: "杜门"})
        self.assertEqual(table(res, "deity"),
                         {1: "值符", 2: "六合", 3: "九地", 4: "玄武",
                          6: "螣蛇", 7: "太阴", 8: "九天", 9: "白虎"})


class Rules(unittest.TestCase):
    """口径级检查：局数表、符头、旬空、不变量。"""

    def test_ju_table_covers_24_terms_and_dun(self):
        """三元局数表：24 节气齐备、局数 1-9、冬至到芒种阳遁、夏至到大雪阴遁。"""
        self.assertEqual(len(Q.JU_TABLE), 24)
        yang = {"冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明",
                "谷雨", "立夏", "小满", "芒种"}
        for term, (dun, nums) in Q.JU_TABLE.items():
            self.assertEqual(len(nums), 3, term)
            for n in nums:
                self.assertTrue(1 <= n <= 9, term)
            self.assertEqual(dun, "阳遁" if term in yang else "阴遁", term)
        # 口诀抽查：「冬至惊蛰一七四」「大寒春分三九六」「夏至白露九三六」「立冬六九三」
        self.assertEqual(Q.JU_TABLE["冬至"][1], (1, 7, 4))
        self.assertEqual(Q.JU_TABLE["惊蛰"][1], (1, 7, 4))
        self.assertEqual(Q.JU_TABLE["大寒"][1], (3, 9, 6))
        self.assertEqual(Q.JU_TABLE["春分"][1], (3, 9, 6))
        self.assertEqual(Q.JU_TABLE["夏至"][1], (9, 3, 6))
        self.assertEqual(Q.JU_TABLE["白露"][1], (9, 3, 6))
        self.assertEqual(Q.JU_TABLE["立冬"][1], (6, 9, 3))

    def test_yuan_by_futou(self):
        """符头定元：上前推至甲/己日，地支子午卯酉=上元、寅申巳亥=中元、辰戌丑未=下元。"""
        self.assertEqual(Q.yuan_of_day("甲子"), ("上元", "甲子"))
        self.assertEqual(Q.yuan_of_day("乙丑"), ("上元", "甲子"))
        self.assertEqual(Q.yuan_of_day("己巳"), ("中元", "己巳"))
        self.assertEqual(Q.yuan_of_day("丙申"), ("上元", "甲午"))
        self.assertEqual(Q.yuan_of_day("甲戌"), ("下元", "甲戌"))
        self.assertEqual(Q.yuan_of_day("癸酉"), ("中元", "己巳"))   # 第 10 位 -> 符头己巳

    def test_kongwang_six_xun(self):
        """六旬旬空逐条核对。"""
        want = {"甲子": ("戌", "亥"), "甲戌": ("申", "酉"), "甲申": ("午", "未"),
                "甲午": ("辰", "巳"), "甲辰": ("寅", "卯"), "甲寅": ("子", "丑")}
        for xun, kw in want.items():
            name, _bi, start = Q.xun_of({"甲子": "甲子", "甲戌": "甲戌",
                                         "甲申": "甲申", "甲午": "甲午",
                                         "甲辰": "甲辰", "甲寅": "甲寅"}[xun])
            self.assertEqual(name, xun)
            self.assertEqual(Q.kongwang(start), kw, xun)

    def test_earth_stems_yang_forward_yin_backward(self):
        """地盘三奇六仪：阳遁自局数宫顺布、阴遁逆布；九宫恰好各得一干。"""
        for ju in range(1, 10):
            for dun in ("阳遁", "阴遁"):
                stems = Q.earth_stems(ju, dun)
                self.assertEqual(sorted(stems.keys()), list(range(1, 10)))
                self.assertEqual(sorted(stems.values()), sorted(Q.YIQI_ORDER))
                self.assertEqual(stems[ju], "戊")   # 局数宫必为戊（六仪之首）
                step = 1 if dun == "阳遁" else -1
                for k, stem in enumerate(Q.YIQI_ORDER):
                    self.assertEqual(stems[((ju - 1 + step * k) % 9) + 1], stem)

    def test_pan_invariants(self):
        """任意盘的硬不变量：八星八门八神不重不漏，门神不入中五，天盘干=星本宫地盘干。"""
        for y, mo, d, h in [(2026, 11, 18, 10), (2026, 1, 5, 1), (2026, 7, 4, 1),
                            (2030, 5, 5, 7), (1980, 3, 3, 15)]:
            res, _w = pan(y, mo, d, h)
            stars = [p["star"] for p in res["palaces"] if p["star"]]
            gates = [p["gate"] for p in res["palaces"] if p["gate"]]
            deities = [p["deity"] for p in res["palaces"] if p["deity"]]
            self.assertEqual(len(stars), 8)
            self.assertEqual(len(set(stars)), 8)
            self.assertEqual(len(gates), 8)
            self.assertEqual(len(set(gates)), 8)
            self.assertEqual(len(deities), 8)
            self.assertEqual(set(deities), set(Q.DEITY_ORDER))
            center = next(p for p in res["palaces"] if p["gong"] == 5)
            self.assertIsNone(center["gate"])
            self.assertIsNone(center["deity"])
            for p in res["palaces"]:
                if p["gong"] == 5:
                    continue
                home = Q.STAR_HOME_INV[p["star"]]
                self.assertEqual(p["sky_stem"], res["earth_stems"][str(home)])

    def test_center_palace_jigong(self):
        """时干落中五宫 -> 寄坤二宫，并给 CENTER_JIGONG。"""
        res, warnings = pan(2026, 1, 2, 2, 0)
        self.assertEqual(res["ju"], {"dun": "阳遁", "number": 4})
        self.assertIn("CENTER_JIGONG", codes(warnings))
        self.assertEqual(res["zhifu_landing_gong"], 2)

    def test_ju_override(self):
        """--ju 覆盖局数并显式告警。"""
        res, warnings = pan(2026, 11, 18, 10, 30, ju_override=3)
        self.assertEqual(res["ju"], {"dun": "阴遁", "number": 3})
        self.assertIn("JU_OVERRIDE", codes(warnings))
        # 阴遁三局：戊3 己2 庚1 辛9 壬8 癸7 丁6 丙5 乙4（自三宫逆布）
        self.assertEqual(res["earth_stems"], {"1": "庚", "2": "己", "3": "戊",
                                              "4": "乙", "5": "丙", "6": "丁",
                                              "7": "癸", "8": "壬", "9": "辛"})

    def test_feipan_variant(self):
        """飞盘：九星按宫序飞泊、可入中五；八门不入中五；result.pan 区分盘式。"""
        res, warnings = pan(2026, 11, 18, 10, 30, pan="飞盘")
        self.assertEqual(res["pan"], "飞盘")
        self.assertEqual(res["ju"], {"dun": "阴遁", "number": 6})
        self.assertIn("SCHOOL_VARIANT", codes(warnings))
        center = next(p for p in res["palaces"] if p["gong"] == 5)
        self.assertIsNotNone(center["star"])     # 飞盘中五有星
        self.assertIsNone(center["gate"])        # 但八门不入中五
        stars = [p["star"] for p in res["palaces"] if p["star"]]
        self.assertEqual(len(stars), 9)
        self.assertEqual(len(set(stars)), 9)
        gates = [p["gate"] for p in res["palaces"] if p["gate"]]
        self.assertEqual(len(set(gates)), 8)


class ClockChange(unittest.TestCase):
    """夏令时（1986–1991）：口径 fix —— 钟表时 −1h 还原标准时，CLOCK_CHANGE 必发。

    奇门是时家盘，时柱错一个时辰整盘就变，所以这条必须锁死。
    """

    def test_dst_fix_shifts_hour_pillar(self):
        """1990-05-15 13:30 钟表时 -> 12:30 标准时：未时(癸未) 变 午时(壬午)，整盘随之变。

        若不做夏令时还原，13:30 属未时、时柱为癸未；还原后 12:30 属午时、时柱为壬午,
        值符落宫、八门八神全部跟着换——这正是"必须修正"的理由。
        """
        res, warnings = pan(1990, 5, 15, 13, 30)
        self.assertIn("CLOCK_CHANGE", codes(warnings))
        self.assertEqual(res["time"]["input_solar"], "1990-05-15 13:30")
        self.assertEqual(res["time"]["solar"], "1990-05-15 12:30")
        self.assertEqual(res["time"]["clock_fix"]["from"], "1990-05-15 13:30")
        self.assertEqual(res["time"]["clock_fix"]["to"], "1990-05-15 12:30")
        self.assertEqual(res["time"]["shichen"], "午")
        self.assertEqual(res["time"]["hour_ganzhi"], "壬午")
        # 不做修正时 13:30 应为未时、时柱癸未（此处只断言"确实不是那个"）
        self.assertNotEqual(res["time"]["hour_ganzhi"], "癸未")

    def test_dst_crosses_midnight(self):
        """1990-05-15 00:30 钟表时 -> 1990-05-14 23:30 标准时：跨日进夜子时。

        夏令时修正会跨日，日柱随时支一起变；必须同时发 CLOCK_CHANGE 与 LATE_ZI。
        """
        res, warnings = pan(1990, 5, 15, 0, 30)
        self.assertIn("CLOCK_CHANGE", codes(warnings))
        self.assertEqual(res["time"]["solar"], "1990-05-14 23:30")
        self.assertEqual(res["time"]["shichen"], "子")
        self.assertTrue(res["time"]["late_zi"])
        self.assertIn("LATE_ZI", codes(warnings))

    def test_non_dst_untouched(self):
        """非夏令时日期不做任何修正、也不发 CLOCK_CHANGE。"""
        res, warnings = pan(1990, 11, 15, 13, 30)
        self.assertNotIn("CLOCK_CHANGE", codes(warnings))
        self.assertEqual(res["time"]["solar"], "1990-11-15 13:30")
        self.assertEqual(res["time"]["shichen"], "未")
        self.assertEqual(res["time"]["hour_ganzhi"], "辛未")
        self.assertIsNone(res["time"]["clock_fix"])


class Boundaries(unittest.TestCase):
    """节气交接与换遁边界。"""

    def test_xiazhi_boundary_switches_to_yindun(self):
        """2026 夏至 06-21 16:24 交节：15:00 仍属芒种（阳遁），17:00 起阴遁。"""
        before, _w = pan(2026, 6, 21, 15, 0)
        after, _w2 = pan(2026, 6, 21, 17, 0)
        self.assertEqual(before["jieqi"]["name"], "芒种")
        self.assertEqual(before["ju"]["dun"], "阳遁")
        self.assertEqual(after["jieqi"]["name"], "夏至")
        self.assertEqual(after["ju"]["dun"], "阴遁")

    def test_dongzhi_boundary_switches_to_yangdun(self):
        """2026 冬至 12-22 04:50 交节：03:00 属大雪（阴遁），06:00 起冬至阳遁。

        当日日柱庚午（第 7 位），符头己巳（第 6 位），地支巳属寅申巳亥 -> 中元，
        冬至三元 1/7/4 -> 中元七局。
        """
        before, _w = pan(2026, 12, 22, 3, 0)
        after, _w2 = pan(2026, 12, 22, 6, 0)
        self.assertEqual(before["jieqi"]["name"], "大雪")
        self.assertEqual(before["ju"]["dun"], "阴遁")
        self.assertEqual(after["jieqi"]["name"], "冬至")
        self.assertEqual(after["ju"], {"dun": "阳遁", "number": 7})
        self.assertEqual(after["yuan"], "中元")
        self.assertEqual(after["yuan_detail"]["fu_tou"], "己巳")


class Envelope(unittest.TestCase):
    """契约 §3 信封 / 缺输入报错。"""

    def test_json_envelope_via_cli(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--solar", "2026-11-18",
                               "--hour", "10:30", "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)
        self.assertEqual(sorted(payload.keys()),
                         ["cmd", "engine", "input", "ok", "result", "schema_version",
                          "seed", "warnings"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cmd"], "qimen")
        for key in ("time", "jieqi", "yuan", "ju", "zhifu_star", "zhishi_gate",
                    "palaces", "warnings"):
            self.assertIn(key, payload["result"])
        self.assertEqual(len(payload["result"]["palaces"]), 9)
        for p in payload["result"]["palaces"]:
            for key in ("gong", "direction", "earth_stem", "sky_stem",
                        "star", "gate", "deity"):
                self.assertIn(key, p)

    def _rc(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = Q.main(argv)
        return rc, buf.getvalue()

    def test_missing_hour_is_error(self):
        """时家奇门必须有时辰：不给 --hour 直接报错（契约 §4）。"""
        rc, out = self._rc(["--solar", "2026-11-18", "--json"])
        self.assertEqual(rc, 2)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "BAD_INPUT")

    def test_bad_inputs(self):
        for argv in (["--solar", "2026-11-18", "--hour", "10:30",
                      "--pan", "太极盘", "--json"],
                     ["--solar", "2026-02-30", "--hour", "10:30", "--json"],
                     ["--solar", "2026-11-18", "--hour", "25:00", "--json"]):
            rc, out = self._rc(argv)
            self.assertEqual(rc, 2, argv)
            self.assertFalse(json.loads(out)["ok"])


if __name__ == "__main__":
    unittest.main()
