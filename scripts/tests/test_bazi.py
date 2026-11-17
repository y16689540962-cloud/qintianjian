# -*- coding: utf-8 -*-
"""bazi 八字引擎测试。

测试分三类：
  1) **已知标准答案**（KnownPillars / KnownTables）：四柱由 lunar_python 1.4.9
     （寿星天文历，底层历法）与 MIT 许可的 pai_pan.py 双源核对一致后写死；
     藏干、纳音、十神、空亡、大运顺逆/起运按《渊海子平》《三命通会》通行口诀手推核对。
  2) **口径与边界**（BranchCases）：早晚子时两派、缺时辰降级、缺性别降级、
     1986–1991 夏令时还原、立春/交节临界、已故截断、真太阳时、朔边界。
  3) **信封与 CLI**（Envelope）：JSON 信封字段、错误退出码、--lunar/--leap、--dayun-n。

未覆盖（不要在文档里写成"全部已验证"）：
  * 神煞取通行口诀，流派口径不一致处已在返回项 status 标 school，未逐派校勘；
  * 大运/流年的吉凶判断、格局高低、用神喜忌——本引擎只排盘，不做断语。

跑：cd <repo> && python3 -m unittest discover -s scripts/tests -q
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import bazi as B  # noqa: E402


def chart(**kw):
    kw.setdefault("input_note", {"calendar": "solar"})
    result, warnings = B.build_chart(**kw)
    return result, warnings


def codes(warnings):
    return [w["code"] for w in warnings]


def pillars(result):
    return {k: (v["ganzhi"] if v else None) for k, v in result["pillars"].items()}


class KnownPillars(unittest.TestCase):
    """四柱已知标准答案。"""

    def test_1990_05_15_1200_male(self):
        r, w = chart(solar_ymd=(1990, 5, 15), hour=12, sex="男")
        self.assertEqual(pillars(r), {"year": "庚午", "month": "辛巳",
                                      "day": "庚辰", "hour": "壬午"})
        self.assertEqual(r["lunar"]["day_cn"], "廿一")
        self.assertEqual(r["day_master"], {"stem": "庚", "wuxing": "金", "yinyang": "阳"})

    def test_1949_10_01(self):
        r, _ = chart(solar_ymd=(1949, 10, 1), hour=12, sex="男")
        self.assertEqual(pillars(r), {"year": "己丑", "month": "癸酉",
                                      "day": "甲子", "hour": "庚午"})

    def test_1900_01_01(self):
        r, _ = chart(solar_ymd=(1900, 1, 1), hour=12, sex="男")
        self.assertEqual(pillars(r)["year"], "己亥")
        self.assertEqual(pillars(r)["month"], "丙子")
        self.assertEqual(pillars(r)["day"], "甲戌")

    def test_1984_lichun_before_after(self):
        # 1984-02-04 23:19 立春：此前年柱癸亥，此后甲子
        r_before, _ = chart(solar_ymd=(1984, 2, 2), hour=12, sex="男")
        r_after, _ = chart(solar_ymd=(1984, 2, 10), hour=8, sex="男")
        self.assertEqual(pillars(r_before)["year"], "癸亥")
        self.assertEqual(pillars(r_after)["year"], "甲子")
        self.assertEqual(pillars(r_after), {"year": "甲子", "month": "丙寅",
                                            "day": "甲戌", "hour": "戊辰"})


class KnownTables(unittest.TestCase):
    """藏干 / 纳音 / 十神 / 空亡 / 起运的对照表答案。"""

    def setUp(self):
        self.result, self.warnings = chart(solar_ymd=(1990, 5, 15), hour=12, sex="男")

    def test_canggan(self):
        self.assertEqual([c["stem"] for c in self.result["pillars"]["month"]["canggan"]],
                         ["丙", "庚", "戊"])
        self.assertEqual([c["level"] for c in self.result["pillars"]["month"]["canggan"]],
                         ["本气", "中气", "余气"])
        self.assertEqual([c["stem"] for c in self.result["pillars"]["day"]["canggan"]],
                         ["戊", "乙", "癸"])

    def test_nayin(self):
        expect = {"year": "路旁土", "month": "白蜡金", "day": "白蜡金", "hour": "杨柳木"}
        for key, value in expect.items():
            self.assertEqual(self.result["pillars"][key]["nayin"], value, key)

    def test_shishen(self):
        p = self.result["pillars"]
        self.assertEqual(p["year"]["shishen"], "比肩")     # 庚见庚
        self.assertEqual(p["month"]["shishen"], "劫财")    # 庚见辛
        self.assertEqual(p["hour"]["shishen"], "食神")     # 庚见壬
        self.assertEqual(p["day"]["shishen"], "日主")
        self.assertEqual(B.shishen_of("庚", "丁"), "正官")
        self.assertEqual(B.shishen_of("庚", "丙"), "七杀")
        self.assertEqual(B.shishen_of("庚", "甲"), "偏财")
        self.assertEqual(B.shishen_of("庚", "戊"), "偏印")

    def test_kongwang(self):
        kw = {x["pillar"]: x for x in self.result["kongwang"]}
        self.assertEqual(kw["年柱"]["kong"], ["戌", "亥"])   # 庚午在甲子旬
        self.assertEqual(kw["日柱"]["kong"], ["申", "酉"])   # 庚辰在甲戌旬
        self.assertEqual(kw["日柱"]["xun"], "甲戌旬")

    def test_wuxing_and_shishen_tally(self):
        count = self.result["wuxing_count"]
        self.assertEqual(sum(count.values()), 8)
        self.assertEqual(count, {"木": 0, "火": 3, "土": 1, "金": 3, "水": 1})
        self.assertEqual(self.result["wuxing_weighted"]["火"], 6.0)
        sc = self.result["shishen_count"]
        self.assertEqual(sum(sc.values()), 13)   # 3 干 + 10 藏干
        self.assertEqual(sc["比肩"], 2)

    def test_qiyun_three_days_one_year(self):
        dy = self.result["dayun"]
        self.assertEqual(dy["direction"], "顺行")
        q = dy["qiyun"]
        self.assertEqual((q["years"], q["months"], q["days"]), (7, 3, 9))
        self.assertEqual(q["start_date"], "1997-08-24")
        self.assertEqual(dy["list"][0]["ganzhi"], "壬午")
        self.assertEqual(dy["list"][1]["ganzhi"], "癸未")
        self.assertEqual(dy["list"][0]["start_year"], 1997)

    def test_qiyun_reverse_female(self):
        r, _ = chart(solar_ymd=(1990, 5, 15), hour=12, sex="女")
        self.assertEqual(r["dayun"]["direction"], "逆行")
        q = r["dayun"]["qiyun"]
        self.assertEqual((q["years"], q["months"]), (3, 1))
        self.assertEqual(r["dayun"]["list"][0]["ganzhi"], "庚辰")

    def test_shensha(self):
        names = [s["name"] for s in self.result["shensha"]]
        self.assertIn("魁罡", names)     # 庚辰日
        kw = [s for s in self.result["shensha"] if s["name"] == "魁罡"][0]
        self.assertEqual(kw["hits"], ["日柱"])
        for s in self.result["shensha"]:
            self.assertIn(s["status"], ("pub", "school"))
            self.assertTrue(s["rule"])

    def test_liunian_anchor_and_ages(self):
        years = [x["year"] for x in self.result["liunian"]]
        self.assertEqual(len(years), 10)
        self.assertEqual(years, list(range(years[0], years[0] + 10)))
        first = self.result["liunian"][0]
        self.assertEqual(first["age_xusui"], first["year"] - 1990 + 1)


class BranchCases(unittest.TestCase):
    """口径与边界。"""

    def test_late_zi_two_schools(self):
        r_next, w_next = chart(solar_ymd=(2024, 5, 15), hour=23, minute=30, sex="男")
        r_same, w_same = chart(solar_ymd=(2024, 5, 15), hour=23, minute=30, sex="男",
                               late_zi="same_day")
        self.assertEqual(pillars(r_next)["day"], "庚辰")   # 次日日柱
        self.assertEqual(pillars(r_next)["hour"], "丙子")
        self.assertEqual(pillars(r_same)["day"], "己卯")   # 当日日柱
        self.assertEqual(pillars(r_same)["hour"], "甲子")
        self.assertIn("LATE_ZI", codes(w_next))
        self.assertIn("SCHOOL_VARIANT", codes(w_next))
        self.assertIn("LATE_ZI", codes(w_same))
        msg = [w for w in w_next if w["code"] == "LATE_ZI"][0]["message"]
        self.assertIn("same_day", msg)

    def test_not_late_zi_before_23(self):
        r, w = chart(solar_ymd=(2024, 5, 15), hour=22, minute=30, sex="男")
        self.assertEqual(pillars(r)["day"], "己卯")
        self.assertNotIn("LATE_ZI", codes(w))

    def test_no_hour_degrades(self):
        r, w = chart(solar_ymd=(1990, 5, 15), hour=None, sex="男")
        self.assertIsNone(r["pillars"]["hour"])
        self.assertIn("SHICHEN_UNKNOWN", codes(w))
        self.assertIn("LOW_CONFIDENCE", codes(w))
        self.assertEqual(sum(r["wuxing_count"].values()), 6)   # 三柱六字

    def test_no_sex_degrades(self):
        r, w = chart(solar_ymd=(1990, 5, 15), hour=12, sex=None)
        self.assertIsNone(r["dayun"]["direction"])
        self.assertEqual(r["dayun"]["list"], [])
        self.assertIn("SEX_REQUIRED", codes(w))
        self.assertEqual(pillars(r)["hour"], "壬午")

    def test_dst_clock_change(self):
        r, w = chart(solar_ymd=(1990, 6, 1), hour=12, sex="男")
        self.assertIn("CLOCK_CHANGE", codes(w))
        self.assertEqual(r["birth"]["clock"], "1990-06-01 11:00")
        self.assertEqual(r["birth"]["clock_change"]["from"], "1990-06-01 12:00")
        self.assertEqual(r["input"]["late_zi"], "next_day")
        # 非夏令时年份不修正
        r2, w2 = chart(solar_ymd=(1992, 6, 1), hour=12, sex="男")
        self.assertNotIn("CLOCK_CHANGE", codes(w2))
        self.assertEqual(r2["birth"]["clock"], "1992-06-01 12:00")

    def test_dst_boundary_changes_shichen(self):
        # 13:30（夏令时）还原为 12:30 → 仍是午时；未还原的 13:30 会是未时
        r, w = chart(solar_ymd=(1990, 5, 15), hour=13, minute=30, sex="男")
        self.assertEqual(pillars(r)["hour"], "壬午")
        self.assertEqual(r["birth"]["shichen"]["branch"], "午")

    def test_true_solar_time_applied(self):
        r, w = chart(solar_ymd=(2024, 5, 15), hour=12, sex="男", longitude=87.62)
        self.assertIn("TST_APPLIED", codes(w))
        self.assertLess(r["birth"]["true_solar_time"]["correction_seconds"], -600)
        self.assertEqual(r["input"]["longitude"], 87.62)

    def test_place_resolves_longitude(self):
        r, w = chart(solar_ymd=(2024, 5, 15), hour=12, sex="男", place="北京")
        self.assertAlmostEqual(r["input"]["longitude"], 116.41, places=2)
        self.assertIn("TST_APPLIED", codes(w))

    def test_jieqi_boundary_warning(self):
        # 1990 立夏 = 05-06 02:35。不还原夏令时（03:00 原样）时距交节 25 分钟 → 巳月 + 临界警告
        r, w = chart(solar_ymd=(1990, 5, 6), hour=3, sex="男", handle_dst=False)
        self.assertIn("JIEQI_BOUNDARY", codes(w))
        self.assertEqual(pillars(r)["month"], "辛巳")
        # 还原夏令时（03:00 → 02:00）后仍在立夏前，月柱回到辰月——同一钟表时因口径不同而变月柱
        r2, _ = chart(solar_ymd=(1990, 5, 6), hour=3, sex="男")
        self.assertEqual(pillars(r2)["month"], "庚辰")

    def test_deceased_year_truncates_liunian(self):
        r, w = chart(solar_ymd=(2024, 5, 15), hour=12, sex="男", deceased_year=2030)
        self.assertIn("DECEASED_LIUNIAN_CAP", codes(w))
        self.assertLessEqual(max(x["year"] for x in r["liunian"]), 2030)

    def test_shuo_boundary_warning(self):
        # 1914-11-17 是争议月首前一天（朔在北京时 11-18 00:01:44）
        r, w = chart(solar_ymd=(1914, 11, 17), hour=10, sex="女")
        self.assertIn("SHUO_BOUNDARY", codes(w))
        self.assertEqual(r["lunar"]["day"], 30)

    def test_dayun_n(self):
        r, _ = chart(solar_ymd=(1990, 5, 15), hour=12, sex="男", dayun_n=3)
        self.assertEqual(len(r["dayun"]["list"]), 3)


class Envelope(unittest.TestCase):
    """JSON 信封与 CLI。"""

    def _run(self, argv):
        buf = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            code = B.main(argv)
        return code, buf.getvalue(), err.getvalue()

    def test_json_envelope(self):
        code, out, _ = self._run(["--solar", "1990-05-15", "--hour", "12:00",
                                 "--sex", "男", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
            self.assertIn(key, payload)
        self.assertEqual(payload["cmd"], "bazi")
        self.assertEqual(payload["input"]["solar"], "1990-05-15")
        self.assertEqual(payload["input"]["hour"], "12:00")
        self.assertEqual(payload["input"]["sex"], "男")
        result = payload["result"]
        for key in ("input", "lunar", "pillars", "day_master", "wuxing_count",
                    "shishen_count", "dayun", "liunian", "shensha", "kongwang", "warnings"):
            self.assertIn(key, result)
        for key in ("year", "month", "day", "hour"):
            self.assertIn(key, result["pillars"])
        for key in ("ganzhi", "stem", "branch", "shishen", "canggan", "nayin", "wuxing"):
            self.assertIn(key, result["pillars"]["year"])
        self.assertEqual(result["pillars"]["hour"]["ganzhi"], "壬午")
        for key in ("direction", "qiyun", "list"):
            self.assertIn(key, result["dayun"])
        for key in ("years", "months", "days", "start_date"):
            self.assertIn(key, result["dayun"]["qiyun"])

    def test_error_exit_code(self):
        code, out, _ = self._run(["--solar", "1990-02-30", "--sex", "男", "--json"])
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "BAD_DATE")

    def test_lunar_input_with_leap(self):
        code, out, _ = self._run(["--lunar", "2020-04-01", "--leap", "--hour", "12:00",
                                  "--sex", "女", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["result"]["input"]["calendar"], "lunar")
        self.assertEqual(payload["result"]["input"]["solar"], "2020-05-23")

    def test_shichen_argument(self):
        code, out, _ = self._run(["--solar", "1990-05-15", "--shichen", "午",
                                  "--sex", "男", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["result"]["pillars"]["hour"]["ganzhi"], "壬午")

    def test_human_output_contains_tables(self):
        code, out, _ = self._run(["--solar", "1990-05-15", "--hour", "12:00", "--sex", "男"])
        self.assertEqual(code, 0)
        for token in ("# 八字排盘", "| 年柱 | 庚午 |", "大运", "流年", "空亡"):
            self.assertIn(token, out)


if __name__ == "__main__":
    unittest.main()
