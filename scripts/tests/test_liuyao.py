#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻纳甲引擎的 unittest。

已知标准答案（古籍/通行排盘，人工核对）：
  · 京房八宫卦序全表（64 卦归宫与世次）
  · 天风姤（乾宫一世）：纳甲、六亲、世应
  · 火地晋（乾宫游魂）：六亲、伏神子孙甲子水
  · 火天大有（乾宫归魂）：世三应六
  · 旬空：甲子旬空戌亥、丙申日属甲午旬空辰巳
  · 六神起例：甲乙日初爻青龙、丙日初爻朱雀
  · 干支：2026-11-18 = 丙午年 己亥月 丙申日
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
REPO = os.path.dirname(SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import liuyao as L  # noqa: E402


def lines_of(text: str):
    """'101011' → 六爻位（自下而上）"""
    return [int(ch) for ch in text]


def rows_by_pos(bits):
    return {r["pos"]: r for r in L.zhuang_gua(bits, "甲")}


class TestBaguaTable(unittest.TestCase):
    """八宫卦序：京房法推出来的表必须与通行表逐条一致。"""

    CLASSIC = {
        "乾": ["乾为天", "天风姤", "天山遁", "天地否", "风地观", "山地剥", "火地晋", "火天大有"],
        "坎": ["坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师"],
        "艮": ["艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐"],
        "震": ["震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随"],
        "巽": ["巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊"],
        "离": ["离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人"],
        "坤": ["坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比"],
        "兑": ["兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹"],
    }

    def test_eight_palaces_match_classic_table(self):
        for palace, names in self.CLASSIC.items():
            got = [L.gua_name(bits) for bits in L.palace_sequence(palace)]
            self.assertEqual(got, names, "%s宫卦序不符" % palace)

    def test_palace_index_is_bijection(self):
        self.assertEqual(len(L.PALACE_INDEX), 64)

    def test_shi_ying_by_generation(self):
        # 本宫世6应3，一世世1应4……游魂世4应1，归魂世3应6
        expect = [(6, 3), (1, 4), (2, 5), (3, 6), (4, 1), (5, 2), (4, 1), (3, 6)]
        for gen in range(8):
            self.assertEqual(L.shi_ying_of(gen), expect[gen], "第%d世世应错" % gen)


class TestNajiiaZhuangGua(unittest.TestCase):
    """纳甲装卦：三条手核过的卦。"""

    def test_gou_najia_liuqin_shiying(self):
        """天风姤 = 上乾下巽，乾宫一世，世1应4。"""
        bits = lines_of("011111")  # 初..上：巽(0,1,1) + 乾(1,1,1)
        self.assertEqual(L.gua_name(bits), "天风姤")
        palace, gen = L.PALACE_INDEX[tuple(bits)]
        self.assertEqual((palace, L.GENERATIONS[gen]), ("乾", "一世"))
        rows = rows_by_pos(bits)
        got = [(rows[i]["najia"]["stem"], rows[i]["najia"]["branch"], rows[i]["liuqin"]) for i in range(1, 7)]
        self.assertEqual(got, [
            ("辛", "丑", "父母"), ("辛", "亥", "子孙"), ("辛", "酉", "兄弟"),
            ("壬", "午", "官鬼"), ("壬", "申", "兄弟"), ("壬", "戌", "父母"),
        ])
        self.assertEqual((rows[1]["shi"], rows[4]["ying"]), (True, True))

    def test_jin_youhun_and_fushen(self):
        """火地晋 = 上离下坤，乾宫游魂，世4应1；缺子孙，伏神为初爻甲子水。"""
        bits = lines_of("000101")
        self.assertEqual(L.gua_name(bits), "火地晋")
        palace, gen = L.PALACE_INDEX[tuple(bits)]
        self.assertEqual((palace, L.GENERATIONS[gen]), ("乾", "游魂"))
        rows = rows_by_pos(bits)
        self.assertEqual([rows[i]["liuqin"] for i in range(1, 7)],
                         ["父母", "官鬼", "妻财", "兄弟", "父母", "官鬼"])
        self.assertEqual((rows[4]["shi"], rows[1]["ying"]), (True, True))
        fushen = L.fushen_of(bits)
        self.assertEqual(len(fushen), 1)
        self.assertEqual(fushen[0]["pos"], 1)
        self.assertEqual(fushen[0]["liuqin"], "子孙")
        self.assertEqual(fushen[0]["najia"], {"stem": "甲", "branch": "子"})
        self.assertEqual(fushen[0]["feishen_liuqin"], "父母")

    def test_dayou_guihun(self):
        """火天大有 = 上离下乾，乾宫归魂，世3应6。"""
        bits = lines_of("111101")
        self.assertEqual(L.gua_name(bits), "火天大有")
        palace, gen = L.PALACE_INDEX[tuple(bits)]
        self.assertEqual((palace, L.GENERATIONS[gen]), ("乾", "归魂"))
        self.assertEqual(L.shi_ying_of(gen), (3, 6))

    def test_qian_najia_full(self):
        """乾为天：初甲子、二甲寅、三甲辰、四壬午、五壬申、上壬戌。"""
        bits = lines_of("111111")
        got = [(x["stem"], x["branch"]) for x in L.najia_of(bits)]
        self.assertEqual(got, [("甲", "子"), ("甲", "寅"), ("甲", "辰"),
                               ("壬", "午"), ("壬", "申"), ("壬", "戌")])

    def test_liuqin_relations(self):
        # 卦宫金：土生金→父母；金生水→子孙；金克木→妻财；火克金→官鬼；金→兄弟
        self.assertEqual(L.liuqin_of("金", "土"), "父母")
        self.assertEqual(L.liuqin_of("金", "水"), "子孙")
        self.assertEqual(L.liuqin_of("金", "木"), "妻财")
        self.assertEqual(L.liuqin_of("金", "火"), "官鬼")
        self.assertEqual(L.liuqin_of("金", "金"), "兄弟")


class TestDateAndShensha(unittest.TestCase):
    """日辰、月建、旬空、月破、六神。"""

    def test_ganzhi_of_2026_11_18(self):
        import datetime as _dt
        import calendar_core as cc
        dt = _dt.datetime(2026, 11, 18, 10, 30)
        self.assertEqual("".join(cc.ganzhi_year(dt)), "丙午")
        self.assertEqual("".join(cc.ganzhi_month(dt)), "己亥")
        self.assertEqual("".join(cc.ganzhi_day(dt)), "丙申")

    def test_xunkong_known(self):
        self.assertEqual(L.xunkong_of(("甲", "子")), ["戌", "亥"])
        self.assertEqual(L.xunkong_of(("癸", "酉")), ["戌", "亥"])  # 甲子旬
        self.assertEqual(L.xunkong_of(("丙", "申")), ["辰", "巳"])  # 甲午旬
        self.assertEqual(L.xunkong_of(("甲", "寅")), ["子", "丑"])

    def test_liushen_start_by_day_stem(self):
        for stem, start in (("甲", "青龙"), ("乙", "青龙"), ("丙", "朱雀"), ("丁", "朱雀"),
                            ("戊", "勾陈"), ("己", "螣蛇"), ("庚", "白虎"), ("辛", "白虎"),
                            ("壬", "玄武"), ("癸", "玄武")):
            rows = L.zhuang_gua(lines_of("111111"), stem)
            self.assertEqual(rows[0]["liushen"], start, "%s日初爻六神错" % stem)
            self.assertEqual(rows[5]["liushen"], L.LIUSHEN_ORDER[(L.LIUSHEN_ORDER.index(start) + 5) % 6])

    def test_yuepo_and_chong(self):
        self.assertEqual(L.chong_branch("子"), "午")
        self.assertEqual(L.chong_branch("亥"), "巳")
        self.assertEqual(L.chong_branch("辰"), "戌")


class TestCasting(unittest.TestCase):
    """起卦：钱、蓍草、手输，以及 seed 回放。"""

    def test_coins_values_in_range(self):
        rng = random.Random(7)
        for _ in range(200):
            value, coins = L.toss_coins(rng)
            self.assertIn(value, (6, 7, 8, 9))
            self.assertEqual(value, sum(coins))
            self.assertEqual(len(coins), 3)

    def test_coins_mapping(self):
        # 背(3)数 ↔ 爻值：0 背=6 老阴，1 背=7 少阳，2 背=8 少阴，3 背=9 老阳
        mapping = {0: 6, 1: 7, 2: 8, 3: 9}
        for backs, expect in mapping.items():
            coins = [L.COIN_BACK] * backs + [L.COIN_FACE] * (3 - backs)
            self.assertEqual(sum(coins), expect)

    def test_yarrow_three_changes_land_on_four_values(self):
        rng = random.Random(11)
        seen = set()
        for _ in range(300):
            value = L.toss_yarrow(rng)
            self.assertIn(value, (6, 7, 8, 9))
            seen.add(value)
        self.assertEqual(seen, {6, 7, 8, 9}, "蓍草法应能出全 6/7/8/9")

    def test_seed_replay_same_result(self):
        a = L.analyze("coins", "2026-11-18", "10:30", 42, None, None, None)
        b = L.analyze("coins", "2026-11-18", "10:30", 42, None, None, None)
        self.assertEqual(json.dumps(a["result"], sort_keys=True), json.dumps(b["result"], sort_keys=True))

    def test_seed_differs_gives_different_cast(self):
        a = L.analyze("coins", "2026-11-18", "10:30", 42, None, None, None)
        b = L.analyze("coins", "2026-11-18", "10:30", 43, None, None, None)
        self.assertNotEqual(
            [x["value"] for x in a["result"]["cast"]],
            [x["value"] for x in b["result"]["cast"]])

    def test_manual_lines_and_moving(self):
        out = L.analyze("manual", "2026-11-18", "10:30", None, "101011", "3,5", None)
        r = out["result"]
        self.assertEqual(r["ben_gua"]["lines_bits"], "101011")
        moving = [row["pos"] for row in r["lines"] if row["moving"]]
        self.assertEqual(moving, [3, 5])
        self.assertEqual(r["bian_gua"]["lines_bits"], "100001")  # 第3、5爻翻转

    def test_manual_static_warns(self):
        out = L.analyze("manual", "2026-11-18", "10:30", None, "101011", None, None)
        self.assertIsNone(out["result"]["bian_gua"])
        self.assertIn("STATIC_GUA", [w["code"] for w in out["result"]["warnings"]])

    def test_bad_lines_rejected(self):
        with self.assertRaises(ValueError):
            L.analyze("manual", "2026-11-18", None, None, "10101", None, None)
        with self.assertRaises(ValueError):
            L.analyze("manual", "2026-11-18", None, None, "1010x1", None, None)


class TestCastDisclosure(unittest.TestCase):
    """诚信披露：AI 代掷必须自己说出来，用户自报爻不许被说成代掷。"""

    def test_ai_cast_warns_and_marks_cast_by_ai(self):
        for method in ("coins", "yarrow"):
            out = L.analyze(method, "2026-11-18", "10:30", 42, None, None, "问事")
            codes = [w["code"] for w in out["warnings"]]
            self.assertIn("AI_CAST_RANDOM", codes, "%s 起卦未披露 AI 代掷" % method)
            msg = [w["message"] for w in out["warnings"] if w["code"] == "AI_CAST_RANDOM"][0]
            self.assertIn("seed=42", msg)
            self.assertIn("不是用户亲手摇的", msg)
            self.assertEqual(out["result"]["cast_by"], "ai")
            # 信封与 result.warnings 必须是同一份（不能只加一处）
            self.assertIn("AI_CAST_RANDOM", [w["code"] for w in out["result"]["warnings"]])

    def test_user_cast_has_no_ai_warning(self):
        out = L.analyze("manual", "2026-11-18", "10:30", None, "101011", "3", None)
        codes = [w["code"] for w in out["warnings"]]
        self.assertNotIn("AI_CAST_RANDOM", codes)
        self.assertEqual(out["result"]["cast_by"], "user")


class TestEnvelope(unittest.TestCase):
    """§3 / §6 字段契约与独立运行。"""

    def test_result_required_fields(self):
        out = L.analyze("coins", "2026-11-18", "10:30", 42, None, None, "问事")
        r = out["result"]
        for key in ("method", "date", "day_ganzhi", "month_ganzhi", "ben_gua",
                    "bian_gua", "lines", "shi", "ying", "fushen", "warnings"):
            self.assertIn(key, r)
        for key in ("name", "trigrams", "palace", "generation"):
            self.assertIn(key, r["ben_gua"])
        self.assertEqual(len(r["lines"]), 6)
        for row in r["lines"]:
            for key in ("pos", "yinyang", "moving", "najia", "liuqin", "liushen"):
                self.assertIn(key, row)
            self.assertIn("stem", row["najia"])
            self.assertIn("branch", row["najia"])
        self.assertEqual(out["seed"], 42)

    def test_cli_json_envelope(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "liuyao.py"),
               "--coins", "--seed", "42", "--date", "2026-11-18", "--hour", "10:30", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        env = json.loads(proc.stdout)
        self.assertTrue(env["ok"])
        self.assertEqual(env["schema_version"], 1)
        self.assertEqual(env["cmd"], "liuyao")
        self.assertEqual(env["seed"], 42)
        self.assertEqual(env["input"]["date"], "2026-11-18")
        for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
            self.assertIn(key, env)

    def test_cli_bad_input_exit2(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "liuyao.py"),
               "--lines", "10", "--date", "2026-11-18", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        env = json.loads(proc.stdout)
        self.assertFalse(env["ok"])
        self.assertIn("code", env["error"])

    def test_stdout_is_pure_json(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "liuyao.py"),
               "--yarrow", "--seed", "9", "--date", "2026-11-18", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)  # 多一个字符都会抛


if __name__ == "__main__":
    unittest.main(verbosity=2)
