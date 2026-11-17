# -*- coding: utf-8 -*-
"""calendar_core 历法内核测试。

测试分三类：
  1) **已知标准答案**（KnownLunar / KnownPillars / KnownTerms / KnownSolarTime）：
     农历日期取公认历日（春节、闰月、1990 年四月廿一），四柱与节气时刻由
     lunar_python 1.4.9（寿星天文历）与 JPL Horizons 交叉核对后写死；
     儒略日取天文年历公认值（J2000 = 2451545.0）。
  2) **口径与边界**（BranchCases）：立春界、节界、子初换日、真太阳时、闰月、
     争议月首（1914-11-18 经 USNO 月相 API 仲裁）。
  3) **降级与信封**（Envelope）：日期越界、JSON 信封、自检入口。

已知口径差异（不是 bug，见 calendar_core docstring）：
  * 1914-11-18 / 1916-02-04 / 1920-11-11 / 2097-08-08 等 7 个月首，
    本实现与 lunar_python 差一天，经 JPL Horizons 与 USNO 月相 API 双源仲裁，
    **本实现为准**（真朔在北京时零点后 1–5 分钟）。

跑：cd <repo> && python3 -m unittest discover -s scripts/tests -q
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import calendar_core as C  # noqa: E402


def noon(y, m, d):
    return datetime(y, m, d, 12, 0)


class KnownLunar(unittest.TestCase):
    """农历互转的已知标准答案。"""

    def test_1990_05_15_is_siyue_nianyi(self):
        lu = C.solar_to_lunar(1990, 5, 15)
        self.assertEqual((lu["year"], lu["month"], lu["day"], lu["leap"]), (1990, 4, 21, False))
        self.assertEqual(lu["month_cn"], "四月")
        self.assertEqual(lu["day_cn"], "廿一")
        self.assertEqual(lu["year_cn"], "一九九〇")
        self.assertEqual(lu["shengxiao"], "马")
        self.assertEqual(lu["ganzhi_year"], "庚午")

    def test_spring_festivals(self):
        # 公认春节：2024-02-10、2000-02-05 均为正月初一
        self.assertEqual(
            (lambda x: (x["year"], x["month"], x["day"]))(
                C.solar_to_lunar(2024, 2, 10)), (2024, 1, 1))
        self.assertEqual(
            (lambda x: (x["year"], x["month"], x["day"]))(
                C.solar_to_lunar(2000, 2, 5)), (2000, 1, 1))
        self.assertEqual(C.solar_to_lunar(2024, 2, 10)["day_cn"], "初一")

    def test_prc_founding_day(self):
        lu = C.solar_to_lunar(1949, 10, 1)
        self.assertEqual((lu["year"], lu["month"], lu["day"]), (1949, 8, 10))
        self.assertEqual(lu["day_cn"], "初十")

    def test_leap_month_2033(self):
        # 2033 年闰十一月（著名特例）：2033-12-22 为闰十一月初一
        lu = C.solar_to_lunar(2033, 12, 22)
        self.assertEqual((lu["year"], lu["month"], lu["day"], lu["leap"]), (2033, 11, 1, True))
        self.assertEqual(lu["month_cn"], "闰冬月")

    def test_leap_month_list(self):
        expect = {1984: 10, 1990: 5, 2020: 4, 2023: 2, 2025: 6, 2033: 11}
        for year, month in expect.items():
            self.assertEqual(C.leap_month_of_year(year), month, "%d 年闰月" % year)

    def test_lunar_to_solar_known(self):
        self.assertEqual(C.lunar_to_solar(1990, 4, 21), (1990, 5, 15))
        self.assertEqual(C.lunar_to_solar(2020, 4, 1, True), (2020, 5, 23))
        self.assertEqual(C.lunar_to_solar(2024, 1, 1), (2024, 2, 10))

    def test_roundtrip_30_years(self):
        for year in range(1970, 2000):
            solar = C.lunar_to_solar(year, 1, 1)
            self.assertEqual(
                (lambda x: (x["year"], x["month"], x["day"]))(
                    C.solar_to_lunar(*solar)), (year, 1, 1))


class KnownPillars(unittest.TestCase):
    """四柱的已知标准答案（与 lunar_python 1.4.9 逐柱核对一致）。"""

    def test_1990_05_15_noon(self):
        dt = noon(1990, 5, 15)
        self.assertEqual("".join(C.ganzhi_year(dt)), "庚午")
        self.assertEqual("".join(C.ganzhi_month(dt)), "辛巳")
        self.assertEqual("".join(C.ganzhi_day(dt)), "庚辰")
        self.assertEqual("".join(C.ganzhi_hour("庚", 12, 0)), "壬午")

    def test_1949_10_01_noon(self):
        dt = noon(1949, 10, 1)
        self.assertEqual("".join(C.ganzhi_year(dt)), "己丑")
        self.assertEqual("".join(C.ganzhi_month(dt)), "癸酉")
        self.assertEqual("".join(C.ganzhi_day(dt)), "甲子")

    def test_1900_01_01_noon(self):
        dt = noon(1900, 1, 1)
        self.assertEqual("".join(C.ganzhi_year(dt)), "己亥")
        self.assertEqual("".join(C.ganzhi_month(dt)), "丙子")
        self.assertEqual("".join(C.ganzhi_day(dt)), "甲戌")


class KnownTerms(unittest.TestCase):
    """节气时刻的已知标准答案（公开天文年历，分钟级）。"""

    def test_1990_lichun(self):
        self.assertEqual(C.solar_terms(1990)[2]["datetime"], "1990-02-04 10:14")

    def test_2024_dongzhi(self):
        self.assertEqual(C.solar_terms(2024)[23]["datetime"], "2024-12-21 17:20")

    def test_2000_chunfen(self):
        self.assertEqual(C.solar_terms(2000)[5]["datetime"], "2000-03-20 15:35")

    def test_structure(self):
        terms = C.solar_terms(2026)
        self.assertEqual(len(terms), 24)
        self.assertEqual([t["name"] for t in terms], list(C.TERM_NAMES))
        self.assertEqual([t["index"] for t in terms], list(range(24)))
        jds = [t["jd"] for t in terms]
        self.assertEqual(jds, sorted(jds))
        for i in range(23):
            self.assertTrue(11.0 < jds[i + 1] - jds[i] < 17.5, terms[i]["name"])

    def test_jieqi_of_day_and_neighbours(self):
        self.assertEqual(C.jieqi_of_day(datetime(1990, 2, 4, 8, 0))["name"], "立春")
        self.assertIsNone(C.jieqi_of_day(datetime(1990, 2, 5, 8, 0)))
        prev = C.prev_jieqi(datetime(2024, 6, 1, 0, 0))
        nxt = C.next_jieqi(datetime(2024, 6, 1, 0, 0))
        self.assertEqual(prev["name"], "小满")
        self.assertEqual(nxt["name"], "芒种")
        self.assertTrue(prev["ts"] < "2024-06-01" < nxt["ts"])


class KnownJulianAndSolar(unittest.TestCase):
    """儒略日与真太阳时的已知标准答案。"""

    def test_j2000(self):
        self.assertAlmostEqual(C.julian_day(2000, 1, 1, 12, 0), 2451545.0, places=6)

    def test_mjd_epoch(self):
        self.assertAlmostEqual(C.julian_day(1858, 11, 17, 0, 0), 2400000.5, places=6)

    def test_jd_roundtrip(self):
        for (y, m, d, h, mi) in ((1850, 1, 1, 0, 0), (2000, 6, 15, 13, 45), (2100, 12, 31, 23, 59)):
            jd = C.julian_day(y, m, d, h, mi)
            back = C.jd_to_datetime(jd)
            self.assertEqual(back.strftime("%Y-%m-%d %H:%M"), "%04d-%02d-%02d %02d:%02d" % (y, m, d, h, mi))

    def test_equation_of_time_max_november(self):
        # 均时差全年最大约 +16.4 分钟，出现在 11 月初
        _, corr = C.true_solar_time(datetime(2024, 11, 3, 12, 0), 120.0)
        self.assertTrue(960 <= corr <= 1010, corr)

    def test_longitude_difference(self):
        # 经度时差 = 每度 4 分钟：120.0 − 116.4 = 3.6° → 864 秒
        _, c120 = C.true_solar_time(datetime(2024, 11, 3, 12, 0), 120.0)
        _, c116 = C.true_solar_time(datetime(2024, 11, 3, 12, 0), 116.4)
        self.assertEqual(c120 - c116, 864)

    def test_true_solar_time_consistency(self):
        dt = datetime(2024, 6, 21, 12, 0)
        tst, corr = C.true_solar_time(dt, 116.4)
        self.assertEqual(round((tst - dt).total_seconds()), corr)


class BranchCases(unittest.TestCase):
    """口径与边界。"""

    def test_lichun_year_boundary(self):
        self.assertEqual("".join(C.ganzhi_year(noon(1990, 2, 3))), "己巳")
        self.assertEqual("".join(C.ganzhi_year(noon(1990, 2, 4))), "庚午")
        self.assertEqual("".join(C.ganzhi_year(datetime(1990, 2, 4, 10, 0))), "己巳")
        self.assertEqual("".join(C.ganzhi_year(datetime(1990, 2, 4, 10, 20))), "庚午")

    def test_jie_month_boundary(self):
        # 1990 立夏 05-06 02:35：交节前为辰月，交节后为巳月
        self.assertEqual("".join(C.ganzhi_month(datetime(1990, 5, 6, 2, 0))), "庚辰")
        self.assertEqual("".join(C.ganzhi_month(datetime(1990, 5, 6, 3, 0))), "辛巳")

    def test_day_boundary_at_23(self):
        self.assertEqual("".join(C.ganzhi_day(datetime(1990, 5, 15, 22, 59))), "庚辰")
        self.assertEqual("".join(C.ganzhi_day(datetime(1990, 5, 15, 23, 0))), "辛巳")
        self.assertEqual("".join(C.ganzhi_day(datetime(1990, 5, 16, 0, 30))), "辛巳")

    def test_shichen(self):
        expect = {0: "子", 1: "丑", 2: "丑", 3: "寅", 11: "午", 12: "午",
                  13: "未", 22: "亥", 23: "子"}
        for hour, branch in expect.items():
            self.assertEqual(C.shichen_of(hour, 0)["branch"], branch, "%d 点" % hour)
        self.assertTrue(C.shichen_of(23, 30)["late_zi"])
        self.assertTrue(C.shichen_of(0, 30)["early_zi"])
        self.assertEqual(C.shichen_of(12, 0)["range"], "11:00-12:59")

    def test_ganzhi_hour_wushudun(self):
        # 五鼠遁：甲己日甲子起、乙庚日丙子起、丙辛日戊子起、丁壬日庚子起、戊癸日壬子起
        self.assertEqual("".join(C.ganzhi_hour("甲", 0, 0)), "甲子")
        self.assertEqual("".join(C.ganzhi_hour("乙", 0, 0)), "丙子")
        self.assertEqual("".join(C.ganzhi_hour("丙", 0, 0)), "戊子")
        self.assertEqual("".join(C.ganzhi_hour("丁", 0, 0)), "庚子")
        self.assertEqual("".join(C.ganzhi_hour("戊", 0, 0)), "壬子")
        self.assertEqual("".join(C.ganzhi_hour("庚", 12, 0)), "壬午")

    def test_shuo_boundary_1914(self):
        # 1914-11-18 的朔在北京时 00:01:44（JPL 00:01:41、USNO 判为 11-17 16:02 UT）
        lu = C.solar_to_lunar(1914, 11, 18)
        self.assertEqual((lu["month"], lu["day"]), (10, 1))
        self.assertTrue(lu["shuo_near_midnight"])
        self.assertEqual(lu["month_start"], "1914-11-18")
        self.assertLess(abs(lu["shuo_offset_minutes"]), 15.0)

    def test_resolve_clock(self):
        fixed, warns, meta = C.resolve_clock(datetime(1990, 6, 1, 12, 0), "fix")
        self.assertEqual(fixed.strftime("%H:%M"), "11:00")
        self.assertEqual(warns[0]["code"], "CLOCK_CHANGE")
        self.assertEqual(meta["from"], "1990-06-01 12:00")
        same, warns2, meta2 = C.resolve_clock(datetime(1990, 6, 1, 12, 0), "warn")
        self.assertEqual(same.strftime("%H:%M"), "12:00")
        self.assertEqual(warns2[0]["code"], "CLOCK_CHANGE")
        outside, warns3, _ = C.resolve_clock(datetime(1992, 6, 1, 12, 0), "fix")
        self.assertEqual((outside.strftime("%H:%M"), warns3), ("12:00", []))
        self.assertEqual(C.dst_window_of(datetime(1987, 7, 1, 9, 0))["start"], "1987-04-12 02:00")


class Envelope(unittest.TestCase):
    """降级、错误与 JSON 信封。"""

    def test_range_guard(self):
        for bad in ((1849, 12, 31), (2101, 1, 1)):
            with self.assertRaises(C.DateError):
                C.solar_to_lunar(*bad)
        with self.assertRaises(C.DateError):
            C.lunar_to_solar(1849, 1, 1)

    def test_bad_date(self):
        with self.assertRaises(C.DateError):
            C.julian_day(1990, 2, 30)

    def test_lunar_month_missing(self):
        with self.assertRaises(C.DateError):
            C.lunar_to_solar(2024, 13, 1)
        with self.assertRaises(C.DateError):
            C.lunar_to_solar(2024, 6, 1, True)    # 2024 没有闰六月
        with self.assertRaises(C.DateError):
            C.lunar_to_solar(2024, 4, 31)

    def test_json_envelope(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = C.main(["--date", "1990-05-15", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
            self.assertIn(key, payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cmd"], "calendar")
        self.assertEqual(payload["result"]["lunar"]["day_cn"], "廿一")
        self.assertEqual("".join(payload["result"]["ganzhi"]["day"]), "庚辰")

    def test_error_exit_code(self):
        buf = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            code = C.main(["--date", "1990-02-30", "--json"])
        self.assertEqual(code, 2)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "BAD_DATE")

    def test_self_check_passes(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = C.main([])
        self.assertEqual(code, 0, buf.getvalue())

    def test_year_terms_output(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = C.main(["--year", "2026", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(len(payload["result"]["terms"]), 24)

    def test_now_tz(self):
        now = C.now_tz()
        utc = datetime.now().replace()
        delta = abs((now - utc).total_seconds())
        self.assertLess(delta, 9 * 3600)
        self.assertIsInstance(now, datetime)


if __name__ == "__main__":
    unittest.main()
