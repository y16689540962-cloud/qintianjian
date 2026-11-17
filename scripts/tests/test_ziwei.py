# -*- coding: utf-8 -*-
"""ziwei 紫微斗数引擎测试。

测试分两类：
  1) **已知标准答案**（KnownCharts）：期望值全部由手算规则逐条推演，推导过程写在
     docstring 里；其中命宫/身宫/五行局/十四主星落宫另与 iztro 2.6.2（MIT，
    在 /tmp 临时 npm 跑，未 import、未提交）独立核对一致。
  2) 口径与边界（BranchCases / Envelope）：闰月、夜子时、立春分界、缺时辰降级、
     大限方向、流年、错误码、JSON 信封。

未覆盖（不要在文档里写成"全部已验证"）：
  * 流月/流日/流时盘、飞星四化、小限、长生十二神——本引擎不实现；
  * 庙旺表、四化版本属流派口径，见 ziwei.BRIGHTNESS / ziwei.SI_HUA 的注释。

跑：cd <repo> && python3 -m unittest discover -s scripts/tests -q
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import ziwei as Z  # noqa: E402

SCRIPT = os.path.join(_SCRIPTS, "ziwei.py")


def chart(**kw):
    return Z.ziwei_chart(**kw)


def major_by_branch(result):
    """{地支: 排序后的主星名列表}"""
    out = {}
    for p in result["palaces"]:
        out[p["branch"]] = sorted(s["name"] for s in p["stars"] if s["type"] == "主星")
    return out


def norm(mapping):
    """把 {地支: [星名...]} 的列表顺序归一（本引擎同宫主星按固定次序排，测试不依赖该次序）。"""
    return {k: sorted(v) for k, v in mapping.items()}


def codes(warnings):
    return [w["code"] for w in warnings]


class KnownCharts(unittest.TestCase):
    """已知标准答案：手算逐条推演 + iztro 2.6.2 交叉核对。"""

    def test_1990_05_15_wu_shi_nan(self):
        """1990-05-15 12:00 男（庚午年农历四月廿一 午时）。

        手算：
          月宫 = 寅起正月顺数至四月 -> 巳(5)；时支午 = 6。
          命宫 = (5 - 6) % 12 = 亥(11)；身宫 = (5 + 6) % 12 = 亥(11)。彼此同宫。
          年干庚 -> 五虎遁「乙庚之年戊为头」，寅宫天干 = 戊；顺行至亥 = 丁 -> 丁亥。
          丁亥纳音 = 屋上土 -> 土五局（起运 5 岁）。
          土五局廿一日：商 = ceil(21/5) = 5，借数 = 5*5-21 = 4（偶，顺进）
            -> 紫微 = 寅 + (5-1) + 4 = 第 10 位 = 戌。
          紫微系逆行：天机酉、太阳未、武曲午、天同巳、廉贞寅。
          天府 = (4 - 10) % 12 = 6 = 午；天府系顺行：太阴未、贪狼申、巨门酉、
            天相戌、天梁亥、七杀子、破军辰。
          生年四化（庚）：太阳禄、武曲权、太阴科、天同忌。
        """
        res, _w = chart(solar="1990-05-15", hour=12, minute=0, sex="男")
        self.assertEqual(res["lunar"]["year_ganzhi"], "庚午")
        self.assertEqual((res["lunar"]["month"], res["lunar"]["day"]), (4, 21))
        self.assertEqual(res["ming_gong"]["branch"], "亥")
        self.assertEqual(res["ming_gong"]["ganzhi"], "丁亥")
        self.assertEqual(res["shen_gong"]["branch"], "亥")
        self.assertEqual(res["wuxing_ju"]["name"], "土五局")
        self.assertEqual(res["wuxing_ju"]["number"], 5)
        self.assertEqual(res["wuxing_ju"]["element"], "土")
        self.assertEqual(res["yin_yang"]["combo"], "阳男")
        self.assertEqual(res["yin_yang"]["daxian_direction"], "顺行")
        self.assertEqual(res["ming_zhu"], "巨门")     # 命宫在亥 -> 命主巨门
        self.assertEqual(res["shen_zhu"], "火星")     # 午年 -> 身主火星

        want = {
            "子": ["七杀"], "丑": [], "寅": ["廉贞"], "卯": [],
            "辰": ["破军"], "巳": ["天同"], "午": ["天府", "武曲"],
            "未": ["太阳", "太阴"], "申": ["贪狼"], "酉": ["天机", "巨门"],
            "戌": ["天相", "紫微"], "亥": ["天梁"],
        }
        self.assertEqual(major_by_branch(res), norm(want))

        # 庙旺与四化：抽查手算得出的三个（全表见 ziwei.BRIGHTNESS）
        stars = {s["name"]: s for p in res["palaces"] for s in p["stars"]}
        self.assertEqual(stars["天梁"]["brightness"], "陷")      # 天梁在亥为陷
        self.assertEqual(stars["太阳"]["sihua"], "禄")
        self.assertEqual(stars["武曲"]["sihua"], "权")
        self.assertEqual(stars["太阴"]["sihua"], "科")
        self.assertEqual(stars["天同"]["sihua"], "忌")
        # 四化落宫
        pos = res["sihua_year"]["positions"]
        self.assertEqual(pos["太阳"]["branch"], "未")
        self.assertEqual(pos["太阳"]["palace"], "财帛")
        self.assertEqual(pos["天同"]["palace"], "迁移")
        # 大限：阳男顺行，土五局 5 岁起
        dx = res["daxian"]
        self.assertEqual((dx[0]["branch"], dx[0]["start_age"], dx[0]["end_age"]),
                         ("亥", 5, 14))
        self.assertEqual((dx[1]["branch"], dx[1]["start_age"]), ("子", 15))
        self.assertEqual(len(dx), 12)

    def test_2000_08_08_zi_shi_nan(self):
        """2000-08-08 00:00 男（庚辰年农历七月初九 早子时）。

        手算：
          月宫 = 寅+6 = 申(8)；时支子 = 0 -> 命宫 = 申；身宫 = 申。
          庚年 寅宫戊，顺行至申 = 甲 -> 甲申；甲申纳音 = 泉中水 -> 水二局。
          水二局初九：商 = ceil(9/2) = 5，借数 = 10-9 = 1（奇，逆退）
            -> 紫微 = 寅 + 4 - 1 = 第 5 位 = 巳。
          紫微巳：天机辰、太阳寅、武曲丑、天同子、廉贞酉；
          天府 = (4 - 5) % 12 = 11 = 亥；太阴子、贪狼丑、巨门寅、天相卯、
            天梁辰、七杀巳、破军酉。
        """
        res, _w = chart(solar="2000-08-08", hour=0, minute=0, sex="男")
        self.assertEqual(res["lunar"]["year_ganzhi"], "庚辰")
        self.assertEqual((res["lunar"]["month"], res["lunar"]["day"]), (7, 9))
        self.assertEqual(res["ming_gong"]["branch"], "申")
        self.assertEqual(res["ming_gong"]["ganzhi"], "甲申")
        self.assertEqual(res["shen_gong"]["branch"], "申")
        self.assertEqual(res["wuxing_ju"]["name"], "水二局")
        self.assertEqual(major_by_branch(res), norm({
            "子": ["太阴", "天同"], "丑": ["贪狼", "武曲"], "寅": ["太阳", "巨门"],
            "卯": ["天相"], "辰": ["天机", "天梁"], "巳": ["七杀", "紫微"],
            "午": [], "未": [], "申": [], "酉": ["廉贞", "破军"], "戌": [],
            "亥": ["天府"],
        }))

    def test_1950_01_15_zi_shi_nv(self):
        """1950-01-15 00:00 女（农历己丑年冬月/十一月廿七 早子时，未过 1950 春节）。

        手算：
          公历 1/15 未到春节(1950-02-17)，故农历年 = 1949 -> 年干支 = 己丑
            （紫微用农历年界，不用立春）。
          月宫 = 寅 + (11-1) = 2+10 = 12 -> 回绕至 子(0)；时支子 -> 命宫 = 子；
          己年 寅宫丙，顺行至子 = 丙（右旋 10 位回到丙）-> 丙子；
          丙子纳音 = 涧下水 -> 水二局。
          水二局廿七：商 = ceil(27/2) = 14，借数 = 28-27 = 1（奇，逆退）
            -> 紫微 = 寅 + 13 - 1 = 第 14 位 = 第 2 位 = 寅。
          紫微寅：天机丑、太阳亥、武曲戌、天同酉、廉贞午；
          天府 = (4 - 2) % 12 = 2 = 寅（紫微天府同宫于寅）；太阴卯、贪狼辰、
            巨门巳、天相午、天梁未、七杀申、破军子。
        """
        res, _w = chart(solar="1950-01-15", hour=0, minute=0, sex="女")
        self.assertEqual(res["lunar"]["year"], 1949)
        self.assertEqual(res["lunar"]["year_ganzhi"], "己丑")
        self.assertEqual(res["ming_gong"]["branch"], "子")
        self.assertEqual(res["ming_gong"]["ganzhi"], "丙子")
        self.assertEqual(res["wuxing_ju"]["name"], "水二局")
        stars = major_by_branch(res)
        self.assertEqual(stars["寅"], ["天府", "紫微"])
        self.assertEqual(stars["午"], ["天相", "廉贞"])
        self.assertEqual(stars["戌"], ["武曲"])
        self.assertEqual(stars["子"], ["破军"])

    def test_lichun_boundary_uses_lunar_new_year(self):
        """2026-02-04 12:00 男 —— 当日 04:02 已立春，但农历仍在乙巳年腊月十七。

        紫微斗数取农历年（正月初一）为界：年干支必须是 乙巳，不是丙午。
        手算：月 = 12，时支午 = 6 -> 月宫 = 寅+11 = 丑 -> 命宫 = (1-6)%12 = 未(7)。
        乙年 寅宫戊，顺行至未 = 癸 -> 癸未；癸未纳音 = 杨柳木 -> 木三局。
        木三局十七：商 = 6，借数 = 18-17 = 1（奇）-> 紫微 = 寅+5-1 = 午。
        """
        res, warnings = chart(solar="2026-02-04", hour=12, minute=0, sex="男")
        self.assertEqual(res["lunar"]["year_ganzhi"], "乙巳")
        self.assertEqual((res["lunar"]["month"], res["lunar"]["day"]), (12, 17))
        self.assertEqual(res["ming_gong"]["branch"], "未")
        self.assertEqual(res["wuxing_ju"]["name"], "木三局")
        stars = major_by_branch(res)
        self.assertEqual(stars["午"], ["紫微"])
        self.assertEqual(stars["巳"], ["天机"])
        self.assertIn("SCHOOL_VARIANT", codes(warnings))

    def test_late_zi_shifts_to_next_day(self):
        """1990-11-15 23:30 男（夜子时）——子初换日，农历推进到九月三十。

        选 1990-11-15 是因为它在 1986–1991 夏令时区间**之外**（11 月已过夏令时结束日），
        夜子时不会被 −1h 还原掉。
        手算（按次日日序 1990-11-16）：农历九月三十，月 = 9，时支子 = 0
          -> 命宫 = (2+9-1-0)%12 = 戌(10)。
        庚年 五虎遁「乙庚戊为头」，寅宫戊；顺行至戌 = 丙 -> 丙戌。
        丙戌纳音 = 屋上土 -> 土五局。
        土五局三十日：商 = ceil(30/5) = 6，借数 = 30-30 = 0
          -> 紫微 = 寅 + (6-1) + 0 = 第 6 位 = 未；天府 = (4-7)%12 = 酉（不同宫）；
             破军 = 天府 + 10 = 酉+10 = 未，故紫微与破军同宫于未。
        """
        res, warnings = chart(solar="1990-11-15", hour=23, minute=30, sex="男")
        self.assertEqual((res["lunar"]["month"], res["lunar"]["day"]), (9, 30))
        self.assertTrue(res["input"]["late_zi"])
        self.assertEqual(res["ming_gong"]["branch"], "戌")
        self.assertEqual(res["ming_gong"]["ganzhi"], "丙戌")
        self.assertEqual(res["wuxing_ju"]["name"], "土五局")
        self.assertEqual(major_by_branch(res)["未"], ["破军", "紫微"])
        self.assertIn("LATE_ZI", codes(warnings))

    def test_dst_night_zi_is_not_late_zi_after_fix(self):
        """夏令时区间内 23:30 出生：先 −1h 还原成 22:30 亥时，**不再算夜子时**。

        1990-05-15 在夏令时区间（1990-04-15 ~ 1990-09-16）：钟表 23:30 的标准时是 22:30，
        时支为亥、农历日期不推进。若不做夏令时还原，会把亥时误判成夜子时（差一天+差一宫）。
        """
        res, warnings = chart(solar="1990-05-15", hour=23, minute=30, sex="男")
        self.assertIn("CLOCK_CHANGE", codes(warnings))
        self.assertFalse(res["input"]["late_zi"])
        self.assertEqual(res["lunar"]["shichen"], "亥")
        self.assertEqual(res["time_resolution"]["effective"], "1990-05-15 22:30")
        self.assertEqual((res["lunar"]["month"], res["lunar"]["day"]), (4, 21))
        self.assertNotIn("LATE_ZI", codes(warnings))


class BranchCases(unittest.TestCase):
    """口径与边界。"""

    def test_leap_month_split_at_15(self):
        """闰月口径：初一至十五算本月，十六以后算次月（折中口径，原文作整月按下月）。

        2020 年闰四月。闰四月初十（6/1）-> 月序号 4；闰四月廿四（6/15）-> 月 5。
        命宫（午时 6）：月4 -> (5-6)%12 = 亥；月5 -> (6-6)%12 = 子。
        """
        r1, w1 = chart(solar="2020-06-01", hour=12, minute=0, sex="男")
        r2, w2 = chart(solar="2020-06-15", hour=12, minute=0, sex="男")
        self.assertEqual(r1["lunar"]["month_index_used"], 4)
        self.assertEqual(r2["lunar"]["month_index_used"], 5)
        self.assertEqual(r1["ming_gong"]["branch"], "亥")
        self.assertEqual(r2["ming_gong"]["branch"], "子")
        self.assertIn("LEAP_MONTH", codes(w1))
        self.assertIn("LEAP_MONTH", codes(w2))
        # 折中口径必须写在 school_notes 里，不能对用户说成原文
        self.assertTrue(any("split_15" in n for n in r1["school_notes"]))
        self.assertTrue(any("整月按下月" in n for n in r1["school_notes"]))

    def test_palace_names_run_backwards_from_ming(self):
        """十二宫自命宫起逆排：命宫、兄弟、夫妻、子女、财帛、疾厄、迁移、交友、官禄、田宅、福德、父母。"""
        res, _w = chart(solar="1990-05-15", hour=12, minute=0, sex="男")
        ming = res["ming_gong"]["index"]
        by_branch = {p["index"]: p["name"] for p in res["palaces"]}
        self.assertEqual(len(by_branch), 12)
        for k, name in enumerate(Z.PALACE_NAMES):
            self.assertEqual(by_branch[(ming - k) % 12], name, "%s 宫名不符" % name)
        self.assertEqual([p["name"] for p in res["palaces"] if p["is_ming"]], ["命宫"])
        self.assertEqual(len([p for p in res["palaces"] if p["is_shen"]]), 1)

    def test_daxian_direction_by_yinyang_sex(self):
        """阳男阴女顺行、阴男阳女逆行；起运岁 = 五行局数。"""
        cases = [
            ("1990-05-15", "男", "阳男", "顺行", "土五局", 5),
            ("1990-05-15", "女", "阳女", "逆行", "土五局", 5),
            ("1991-03-20", "男", "阴男", "逆行", "火六局", 6),
            ("1991-03-20", "女", "阴女", "顺行", "火六局", 6),
        ]
        for solar, sex, combo, direction, ju, start in cases:
            res, _w = chart(solar=solar, hour=12, minute=0, sex=sex)
            self.assertEqual(res["yin_yang"]["combo"], combo)
            self.assertEqual(res["yin_yang"]["daxian_direction"], direction)
            self.assertEqual(res["wuxing_ju"]["name"], ju)
            self.assertEqual(res["daxian"][0]["start_age"], start)
            self.assertEqual(res["daxian"][0]["palace"], "命宫")

    def test_liunian_gong_and_sihua(self):
        """流年：2026 丙午 -> 流年命宫在午；虚岁 = 2026-1990+1 = 37 -> 落在 35-44 大限（寅）。"""
        res, _w = chart(solar="1990-05-15", hour=12, minute=0, sex="男",
                        liunian=2026)
        ln = res["liunian"]
        self.assertEqual(ln["ganzhi"], "丙午")
        self.assertEqual(ln["ming_gong_branch"], "午")
        self.assertEqual(ln["nominal_age"], 37)
        self.assertEqual(ln["daxian"]["branch"], "寅")
        self.assertEqual((ln["daxian"]["start_age"], ln["daxian"]["end_age"]), (35, 44))
        self.assertEqual((ln["sihua"]["lu"], ln["sihua"]["quan"],
                          ln["sihua"]["ke"], ln["sihua"]["ji"]),
                         ("天同", "天机", "文昌", "廉贞"))
        # 流年十二宫自流年命宫逆排
        ln_names = {p["branch"]: p["name"] for p in ln["palaces"]}
        self.assertEqual(ln_names["午"], "命宫")
        self.assertEqual(ln_names["巳"], "兄弟")

    def test_sihua_table_and_documented_deviation(self):
        """生年四化十干表 + **已知偏离必须落在字段里**（不许静默改派）。

        甲–辛、癸 与《紫微斗数全书》卷二四化诀一致（scribe-a 维基文库原文核对）；
        壬干本实现取 左辅化科（现代排盘通行，与 iztro 一致），原文「壬梁紫府武」作
        天府化科——这是刻意保留的偏离，必须出现在 result.sihua_year.variant_note
        与 warnings 的 SCHOOL_VARIANT 里，否则下游会把它当原文引用。
        """
        want = {
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
        self.assertEqual(Z.SI_HUA, want)
        # 偏离显式化：字段、口径说明、warning 三处都要有
        res, warnings = chart(solar="1990-05-15", hour=12, minute=0, sex="男")
        note = res["sihua_year"]["variant_note"]
        self.assertIn("天府", note)
        self.assertIn("壬", note)
        self.assertIn("左辅", res["sihua_year"]["school"])
        self.assertTrue(any("SCHOOL_VARIANT" == c for c in codes(warnings)))
        self.assertTrue(any("sihua=ren_zuofu_deviation" in w["message"]
                            for w in warnings))
        self.assertTrue(any("壬" in n for n in res["school_notes"]))

    def test_unknown_hour_degrades_without_guessing(self):
        """缺时辰：发 SHICHEN_UNKNOWN，命宫/五行局/星曜全不编造。"""
        res, warnings = chart(solar="1990-05-15", sex="男")
        self.assertIn("SHICHEN_UNKNOWN", codes(warnings))
        self.assertIsNone(res["ming_gong"])
        self.assertIsNone(res["shen_gong"])
        self.assertIsNone(res["wuxing_ju"])
        self.assertEqual(res["palaces"], [])
        self.assertEqual(res["daxian"], [])
        self.assertEqual(res["sihua_year"]["ji"], "天同")   # 不依赖时辰的信息照给

    def test_true_solar_time_shifts_hour(self):
        """纯真太阳时移时（**刻意选非夏令时日期** 1990-01-15，避免与夏令时修正叠加）。

        经度 87.6（乌鲁木齐）：12:00 − 139 分 ≈ 09:41 -> 巳时(5)。
        1990-01-15 农历腊月十九，月 = 12 -> 命宫 = (1-5)%12 = 申(8)；
        己年 寅宫丙 -> 申宫壬 -> 壬申，纳音剑锋金 -> 金四局。
        """
        res, warnings = chart(solar="1990-01-15", hour=12, minute=0, sex="男",
                              longitude=87.6)
        self.assertNotIn("CLOCK_CHANGE", codes(warnings))   # 非夏令时区间
        self.assertEqual(res["lunar"]["shichen"], "巳")
        self.assertEqual(res["ming_gong"]["branch"], "申")
        self.assertEqual(res["ming_gong"]["ganzhi"], "壬申")
        self.assertEqual(res["wuxing_ju"]["name"], "金四局")
        self.assertEqual(res["time_resolution"]["true_solar"]["to"], "1990-01-15 09:41")

    def test_dst_then_true_solar_order(self):
        """顺序不能反：钟表时先按 resolve_clock 还原标准时，再换真太阳时。

        1990-05-15 12:00（夏令时内）-> 11:00（标准时）-> −126 分 -> 08:54 辰时，
        辰时(4) -> 命宫 = (5-4)%12 = 丑。若先算真太阳时再减 1 小时，结果同样落在辰时，
        但当跨时支边界时两者会差一宫，故代码里固定为「先时钟修正、后真太阳时」。
        """
        res, warnings = chart(solar="1990-05-15", hour=12, minute=0, sex="男",
                              longitude=87.6)
        self.assertIn("CLOCK_CHANGE", codes(warnings))
        self.assertEqual(res["lunar"]["shichen"], "辰")
        self.assertEqual(res["ming_gong"]["branch"], "丑")
        self.assertEqual(res["time_resolution"]["clock_fix"]["to"], "1990-05-15 11:00")
        self.assertEqual(res["time_resolution"]["true_solar"]["to"], "1990-05-15 08:54")

    def test_dst_window_fixed_by_one_hour(self):
        """1986–1991 夏令时：钟表时 −1 小时还原标准时，并必须发 CLOCK_CHANGE。

        口径 = calendar_core.resolve_clock(dt, "fix")（准确性优先）。
        1990-05-15 12:00 -> 11:00（同为午时，命盘不变但时刻记录变），
        1990-05-15 02:30 -> 01:30（丑时 -> 丑时仍是丑时，但记录变），
        1990-05-15 08:30 -> 07:30（辰时 -> 辰时），
        而 1992 年（无夏令时）同样输入不修正。
        """
        res, warnings = chart(solar="1990-05-15", hour=12, minute=0, sex="男")
        self.assertIn("CLOCK_CHANGE", codes(warnings))
        self.assertEqual(res["time_resolution"]["effective"], "1990-05-15 11:00")
        self.assertEqual(res["time_resolution"]["clock_fix"]["from"], "1990-05-15 12:00")
        self.assertEqual(res["time_resolution"]["clock_fix"]["to"], "1990-05-15 11:00")
        res2, warnings2 = chart(solar="1992-05-15", hour=12, minute=0, sex="男")
        self.assertNotIn("CLOCK_CHANGE", codes(warnings2))
        self.assertEqual(res2["time_resolution"]["effective"], "1992-05-15 12:00")

    def _rc(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = Z.main(argv)
        return rc, buf.getvalue()

    def test_bad_date_and_missing_sex(self):
        rc, out = self._rc(["--solar", "1990-02-30", "--hour", "12:00",
                            "--sex", "男", "--json"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(out)["error"]["code"], "BAD_DATE")
        rc, out = self._rc(["--solar", "1990-05-15", "--hour", "12:00", "--json"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(out)["error"]["code"], "BAD_INPUT")
        rc, out = self._rc(["--solar", "1990-05-15", "--hour", "12:00",
                            "--shichen", "午", "--sex", "男", "--json"])
        self.assertEqual(rc, 2)
        self.assertFalse(json.loads(out)["ok"])


class Envelope(unittest.TestCase):
    """契约 §3 信封 / §9 规范。"""

    def test_json_envelope_via_cli(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--solar", "1990-05-15",
                               "--hour", "12:00", "--sex", "男", "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)          # stdout 必须是**一个** JSON 对象
        self.assertEqual(sorted(payload.keys()),
                         ["cmd", "engine", "input", "ok", "result", "schema_version",
                          "seed", "warnings"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cmd"], "ziwei")
        self.assertEqual(payload["seed"], None)
        for key in ("lunar", "ming_gong", "shen_gong", "wuxing_ju", "yin_yang",
                    "palaces", "daxian", "sihua_year", "warnings"):
            self.assertIn(key, payload["result"])

    def test_palace_star_fields(self):
        """palaces[].stars[] 必含 name/type/brightness/sihua；主星才给庙旺。"""
        res, _w = chart(solar="1990-05-15", hour=12, minute=0, sex="男")
        for p in res["palaces"]:
            self.assertIn("name", p)
            self.assertIn("branch", p)
            for s in p["stars"]:
                self.assertEqual(set(s.keys()) >= {"name", "type", "brightness", "sihua"},
                                 True)
                if s["type"] == "主星":
                    self.assertIn(s["brightness"], "庙旺得利平不陷")
                else:
                    self.assertIsNone(s["brightness"])


if __name__ == "__main__":
    unittest.main()
