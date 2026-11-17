#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""风水引擎的 unittest。

已知标准答案（手工核对 / 通行排盘）：
  · 二十四山度数：0°=子、45°=艮、90°=卯、135°=巽、187°=午、315°=乾
  · 八运子山午向：运盘入中 8，山星 4 顺飞、向星 3 逆飞，离宫山星=向星=8（双星会向）
  · 八运乾山巽向：乾宫山星 8、巽宫向星 8 → 旺山旺向
  · 命卦：1990 男坎一、1984 男兑七、1990 女艮八、1984 女艮八
  · 流年紫白：1984 七赤、2004 五黄、2019 八白、2024 三碧、2026 一白
  · 三煞：申子辰煞南、亥卯未煞西、寅午戌煞北、巳酉丑煞东
  · 建除：2026-11-18 丙申日（亥月）为「收」日，冲虎(丙寅)煞南
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
REPO = os.path.dirname(SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import fengshui as F  # noqa: E402


def palace(result, gong):
    for p in result["palaces"]:
        if p["gong"] == gong:
            return p
    raise AssertionError("无宫位 %d" % gong)


class TestLuopan(unittest.TestCase):
    """二十四山与度数映射。"""

    def test_shan_of_deg_known(self):
        expect = {0: "子", 45: "艮", 90: "卯", 135: "巽", 180: "午",
                  187: "午", 225: "坤", 270: "酉", 315: "乾", 350: "壬"}
        for deg, shan in expect.items():
            self.assertEqual(F.shan_of_deg(deg), shan, "%d° 应属%s山" % (deg, shan))

    def test_shan_center_deg(self):
        self.assertEqual(F.shan_center_deg("子"), 0.0)
        self.assertEqual(F.shan_center_deg("午"), 180.0)
        self.assertEqual(F.shan_center_deg("乾"), 315.0)

    def test_jian_xiang_threshold(self):
        # 188° 距午山中心 8°（>4.5）→ 兼向；180° 正向
        r1 = F.feixing("187", 8, None, None)
        self.assertTrue(r1["jian_xiang"])
        r2 = F.feixing("180", 8, None, None)
        self.assertFalse(r2["jian_xiang"])

    def test_facing_name_and_direction_words(self):
        r = F.feixing("午", 8, None, None)
        self.assertEqual((r["xiang"], r["shan"]), ("午", "子"))
        self.assertEqual(r["facing_deg"], 180.0)
        self.assertFalse([w for w in r["warnings"] if w["code"] == "LOW_CONFIDENCE"])
        r2 = F.feixing("朝南", 8, None, None)
        self.assertTrue([w for w in r2["warnings"] if w["code"] == "LOW_CONFIDENCE"])


class TestFeixingKnownCharts(unittest.TestCase):
    """玄空飞星：两张手工核对过的经典盘。"""

    def test_yun8_zi_shan_wu_xiang(self):
        """八运子山午向：山星逆顺、双星会向，离宫 8/8。"""
        r = F.feixing("187", 8, None, None)
        self.assertEqual(r["yun"], 8)
        self.assertEqual(palace(r, 5)["yun_star"], 8, "运盘八白入中")
        self.assertEqual(r["shan_ruzhong"], 4)
        self.assertEqual(r["xiang_ruzhong"], 3)
        self.assertEqual(r["shan_direction"], "顺飞")   # 4 星本宫巽，天元龙巽为阳
        self.assertEqual(r["xiang_direction"], "逆飞")  # 3 星本宫震，天元龙卯为阴
        li = palace(r, 9)
        self.assertEqual((li["shan_star"], li["xiang_star"]), (8, 8))
        self.assertEqual(r["pattern"], "双星到向")

    def test_yun8_qian_shan_xun_xiang(self):
        """八运乾山巽向为旺山旺向：乾宫山星 8、巽宫向星 8。"""
        r = F.feixing("135", 8, None, None)
        self.assertEqual((r["shan"], r["xiang"]), ("乾", "巽"))
        self.assertEqual(palace(r, 6)["shan_star"], 8)
        self.assertEqual(palace(r, 4)["xiang_star"], 8)
        self.assertEqual(r["pattern"], "旺山旺向")

    def test_palaces_complete(self):
        r = F.feixing("187", 8, None, None)
        self.assertEqual(len(r["palaces"]), 9)
        self.assertEqual(sorted(p["gong"] for p in r["palaces"]), list(range(1, 10)))
        for p in r["palaces"]:
            for key in ("gong", "direction", "yun_star", "shan_star", "xiang_star"):
                self.assertIn(key, p)
            for key in ("yun_star", "shan_star", "xiang_star"):
                self.assertTrue(1 <= p[key] <= 9)

    # ---- 逐宫 golden：四张公开盘的完整九宫（山星/向星） ----------------------
    # 来源：衍象坊玄空飞星排盘（下卦）八运子山午向 / 九运子山午向 /
    #       七运卯山酉向 / 九运壬山丙向，逐宫比对，四盘全中。
    GOLDEN_CHARTS = [
        # (运, 向首山, 期望格局, {宫: (山星, 向星)})
        (8, "午", "双星到向", {4: (3, 4), 9: (8, 8), 2: (1, 6), 3: (2, 5), 5: (4, 3),
                              7: (6, 1), 8: (7, 9), 1: (9, 7), 6: (5, 2)}),
        (9, "午", "双星到坐", {4: (6, 3), 9: (1, 8), 2: (8, 1), 3: (7, 2), 5: (5, 4),
                              7: (3, 6), 8: (2, 7), 1: (9, 9), 6: (4, 5)}),
        (7, "酉", "旺山旺向", {4: (6, 1), 9: (1, 5), 2: (8, 3), 3: (7, 2), 5: (5, 9),
                              7: (3, 7), 8: (2, 6), 1: (9, 4), 6: (4, 8)}),
        (9, "丙", "双星到向", {4: (4, 5), 9: (9, 9), 2: (2, 7), 3: (3, 6), 5: (5, 4),
                              7: (7, 2), 8: (8, 1), 1: (1, 8), 6: (6, 3)}),
    ]

    def test_golden_charts_cell_by_cell(self):
        for yun, xiang, pattern, want in self.GOLDEN_CHARTS:
            r = F.feixing(str(F.shan_center_deg(xiang)), yun, None, None)
            got = {p["gong"]: (p["shan_star"], p["xiang_star"]) for p in r["palaces"]}
            self.assertEqual(got, want, "%d运%s山%s向 逐宫不符" % (yun, r["shan"], r["xiang"]))
            self.assertEqual(r["pattern"], pattern, "%d运%s山%s向 格局不符" % (yun, r["shan"], r["xiang"]))

    def test_wu_huang_rule(self):
        """五黄入中取本山三元龙阴阳：九运子午逆飞(阴/双星到坐)、九运壬丙顺飞(阳/双星到向)。"""
        zi = F.feixing(str(F.shan_center_deg("午")), 9, None, None)
        self.assertEqual(zi["shan_ruzhong"], 5)
        self.assertEqual(zi["shan_direction"], "逆飞")
        self.assertEqual(zi["pattern"], "双星到坐")
        ren = F.feixing(str(F.shan_center_deg("丙")), 9, None, None)
        self.assertEqual(ren["shan_ruzhong"], 5)
        self.assertEqual(ren["shan_direction"], "顺飞")
        self.assertEqual(ren["pattern"], "双星到向")

    def test_pattern_value_set_is_fixed(self):
        """pattern 只允许五种取值，便于程序判断。"""
        allowed = {"旺山旺向", "上山下水", "双星到向", "双星到坐", "其他"}
        for yun in range(1, 10):
            for xiang in F.SHAN_24:
                r = F.feixing(str(F.shan_center_deg(xiang)), yun, None, None)
                self.assertIn(r["pattern"], allowed)

    # ---- 格局总表 golden：七/八/九运 --------------------------------------
    # 通行结构：七运、八运为 6/6/6/6；九运无旺山旺向，为 0/12/12。
    PATTERN_TABLE = {
        7: {
            "旺山旺向": "酉卯 辛乙 戌辰 卯酉 乙辛 辰戌",
            "上山下水": "庚甲 乾巽 亥巳 甲庚 巽乾 巳亥",
            "双星到向": "午子 丁癸 坤艮 申寅 壬丙 丑未",
            "双星到坐": "未丑 子午 癸丁 艮坤 寅申 丙壬",
        },
        8: {
            "旺山旺向": "未丑 乾巽 亥巳 丑未 巽乾 巳亥",
            "上山下水": "坤艮 申寅 戌辰 艮坤 寅申 辰戌",
            "双星到向": "庚甲 子午 癸丁 卯酉 乙辛 丙壬",
            "双星到坐": "午子 丁癸 酉卯 辛乙 壬丙 甲庚",
        },
        9: {
            "旺山旺向": "",
            "上山下水": "",
            "双星到向": "午子 丁癸 坤艮 申寅 酉卯 辛乙 戌辰 壬丙 丑未 甲庚 巽乾 巳亥",
            "双星到坐": "未丑 庚甲 乾巽 亥巳 子午 癸丁 艮坤 寅申 卯酉 乙辛 辰戌 丙壬",
        },
    }

    def test_pattern_table_by_yun(self):
        for yun, table in self.PATTERN_TABLE.items():
            groups = {}
            for xiang in F.SHAN_24:
                r = F.feixing(str(F.shan_center_deg(xiang)), yun, None, None)
                groups.setdefault(r["pattern"], set()).add("%s%s" % (r["shan"], r["xiang"]))
            for pattern, names in table.items():
                want = set(names.split()) if names else set()
                self.assertEqual(groups.get(pattern, set()), want,
                                 "%d运「%s」局不符：多%s 少%s" % (
                                     yun, pattern,
                                     groups.get(pattern, set()) - want,
                                     want - groups.get(pattern, set())))

    def test_jian_xiang_tigua_hint(self):
        r = F.feixing("187", 8, None, None)
        self.assertTrue(r["jian_xiang"])
        self.assertIsNotNone(r["tigua_hint"])
        self.assertIn("替卦", r["tigua_hint"])
        codes = [w["code"] for w in r["warnings"]]
        self.assertIn("JIAN_XIANG", codes)
        self.assertIn("SCHOOL_VARIANT", codes)
        r2 = F.feixing("180", 8, None, None)
        self.assertFalse(r2["jian_xiang"])
        self.assertIsNone(r2["tigua_hint"])

    def test_yun_from_built_year(self):
        self.assertEqual(F.yun_of_year(2004), 8)
        self.assertEqual(F.yun_of_year(2023), 8)
        self.assertEqual(F.yun_of_year(2024), 9)
        self.assertEqual(F.yun_of_year(1984), 7)
        self.assertEqual(F.yun_of_year(1864), 1)


class TestMingua(unittest.TestCase):
    """命卦与东西四命。"""

    def test_mingua_numbers_known(self):
        self.assertEqual(F.mingua_number(1990, "男"), 1)   # 坎
        self.assertEqual(F.mingua_number(1984, "男"), 7)   # 兑
        self.assertEqual(F.mingua_number(1990, "女"), 8)   # 5 寄艮
        self.assertEqual(F.mingua_number(1984, "女"), 8)   # 艮

    def test_mingua_group(self):
        r = F.mingua("1990-05-15", "男")
        self.assertEqual((r["gua"], r["group"]), ("坎", "东四命"))
        r2 = F.mingua("1984-05-15", "男")
        self.assertEqual((r2["gua"], r2["group"]), ("兑", "西四命"))

    def test_four_good_four_bad_kan(self):
        """坎命四吉：巽生气、震天医、离延年、坎伏位；四凶：坤绝命、艮五鬼、乾六煞、兑祸害。"""
        r = F.mingua("1990-05-15", "男")
        good = {x["star"]: x["direction"] for x in r["four_good"]}
        bad = {x["star"]: x["direction"] for x in r["four_bad"]}
        self.assertEqual(good, {"生气": "东南", "天医": "东", "延年": "南", "伏位": "北"})
        self.assertEqual(bad, {"绝命": "西南", "五鬼": "东北", "六煞": "西北", "祸害": "西"})

    def test_bad_sex_rejected(self):
        with self.assertRaises(ValueError):
            F.mingua("1990-05-15", "其他")


class TestBazhai(unittest.TestCase):
    """八宅游年七星。"""

    def test_kan_zhai_you_nian(self):
        """坎宅：伏位北、生气东南、天医东、延年南、绝命西南、五鬼东北、六煞西北、祸害西。"""
        r = F.bazhai("180", None, None)
        self.assertEqual(r["zhai_gua"], "坎")
        table = {x["star"]: x["direction"] for x in r["you_nian"]}
        self.assertEqual(table, {
            "伏位": "北", "生气": "东南", "天医": "东", "延年": "南",
            "绝命": "西南", "五鬼": "东北", "六煞": "西北", "祸害": "西",
        })

    def test_qian_zhai_you_nian(self):
        """乾宅：伏位西北、生气西、天医东北、延年西南、绝命南、五鬼东、六煞北、祸害东南。"""
        r = F.bazhai("135", None, None)  # 坐乾
        self.assertEqual((r["zhai_gua"], r["shan"]), ("乾", "乾"))
        table = {x["star"]: x["direction"] for x in r["you_nian"]}
        self.assertEqual(table, {
            "伏位": "西北", "生气": "西", "天医": "东北", "延年": "西南",
            "绝命": "南", "五鬼": "东", "六煞": "北", "祸害": "东南",
        })

    def test_you_nian_symmetry(self):
        """游年关系对称：A 宅看 B 卦的九星，与 B 宅看 A 卦的九星必须相同。"""
        guas = list(F.TRIGRAM_BITS)
        for a in guas:
            for b in guas:
                wa = [v for v in F.younian_of(a).values() if v["gua"] == b][0]["star"]
                wb = [v for v in F.younian_of(b).values() if v["gua"] == a][0]["star"]
                self.assertEqual(wa, wb, "%s↔%s 游年不对称" % (a, b))

    def test_with_mingua(self):
        r = F.bazhai("180", "1990-05-15", "男")
        self.assertIn("mingua", r)
        self.assertIn(r["ming_zhai_he"], ("命宅相合", "命宅不合"))
        self.assertEqual(r["mingua"]["gua"], "坎")
        self.assertEqual(r["ming_zhai_he"], "命宅相合")


class TestLiunian(unittest.TestCase):
    """流年紫白、太岁、岁破、三煞、五黄。"""

    def test_year_star_known(self):
        expect = {1984: 7, 2004: 5, 2019: 8, 2024: 3, 2026: 1}
        for year, star in expect.items():
            self.assertEqual(F.year_zi_bai(year), star, "%d 年年星应 %d" % (year, star))

    def test_liunian_2026(self):
        r = F.liunian(2026)
        self.assertEqual(r["year_ganzhi"], "丙午")
        self.assertEqual(r["zodiac"], "马")
        self.assertEqual(r["tai_sui"], {"branch": "午", "direction": "南"})
        self.assertEqual(r["sui_po"], {"branch": "子", "direction": "北"})
        self.assertEqual(r["san_sha"]["direction"], "北")   # 寅午戌煞北
        self.assertEqual(r["zi_bai"]["year_star"], 1)
        self.assertEqual(r["zi_bai"]["wu_huang_direction"], "南")

    def test_san_sha_by_year_branch(self):
        expect = {2020: "南", 2021: "东", 2019: "西", 2026: "北"}  # 子/丑/亥/午 年
        for year, direction in expect.items():
            self.assertEqual(F.liunian(year)["san_sha"]["direction"], direction,
                             "%d 年三煞应在%s" % (year, direction))

    def test_palaces_nine(self):
        r = F.liunian(2026)
        self.assertEqual(len(r["zi_bai"]["palaces"]), 9)
        stars = sorted(p["star"] for p in r["zi_bai"]["palaces"])
        self.assertEqual(stars, list(range(1, 10)))


class TestDay(unittest.TestCase):
    """建除十二神、黄黑道、冲煞、宜忌。"""

    def test_jianchu_2026_11_18(self):
        """2026-11-18 丙申日，亥月 → 建除「收」，冲虎(丙寅)煞南。"""
        r = F.day_detail("2026-11-18")
        self.assertEqual(r["ganzhi"]["day"], "丙申")
        self.assertEqual(r["ganzhi"]["month"], "己亥")
        self.assertEqual(r["jianchu"], "收")
        self.assertEqual(r["huangdao"], "黑道")
        self.assertEqual(r["chong"], "冲虎(丙寅)煞南")
        self.assertEqual(r["chong_detail"]["zodiac"], "虎")
        self.assertEqual(r["chong_detail"]["ganzhi"], "丙寅")

    def test_jianchu_2026_12_08(self):
        """2026-12-08 丙辰日，子月 → 建除「定」，黄道。"""
        r = F.day_detail("2026-12-08")
        self.assertEqual(r["ganzhi"]["day"], "丙辰")
        self.assertEqual(r["jianchu"], "定")
        self.assertEqual(r["huangdao"], "黄道")

    def test_huangdao_mapping(self):
        for jc in ("除", "危", "定", "执", "成", "开"):
            self.assertEqual(F.huangdao_of(jc), "黄道", jc)
        for jc in ("建", "满", "平", "破", "收", "闭"):
            self.assertEqual(F.huangdao_of(jc), "黑道", jc)

    def test_jianchu_offset_formula(self):
        # 建除 index = (日支 - 月支) % 12
        self.assertEqual(F.jianchu_of("子", "子"), "建")
        self.assertEqual(F.jianchu_of("午", "子"), "破")
        self.assertEqual(F.jianchu_of("丑", "子"), "除")

    def test_day_required_fields(self):
        r = F.day_detail("2026-11-18")
        for key in ("date", "ganzhi", "jianchu", "huangdao", "chong", "yi", "ji", "shensha"):
            self.assertIn(key, r)
        self.assertIsInstance(r["yi"], list)
        self.assertIsInstance(r["ji"], list)
        self.assertTrue(r["yi"], "收日应有宜做事项")

    def test_month_po_found(self):
        """2026-12-10 戊午日，子月 → 月破。"""
        r = F.day_detail("2026-12-10")
        names = [s["name"] for s in r["shensha"]]
        self.assertIn("月破", names)


class TestZeri(unittest.TestCase):
    """择日：先排凶、再排序。"""

    def test_blockers_are_readable_chinese(self):
        r = F.zeri("嫁娶", "2026-12-01", "2026-12-20", [1990])
        self.assertTrue(r["candidates"])
        self.assertTrue(r["blocked"])
        joined = "；".join(b for c in r["blocked"] for b in c["blockers"])
        for token in ("月破", "岁破", "冲命主"):
            self.assertIn(token, joined)
        # 凶煞类 blocker 必须是「理由（细节）」；建除类用「」引事项名
        for c in r["blocked"]:
            for b in c["blockers"]:
                self.assertIsInstance(b, str)
                self.assertGreater(len(b), 2)
                if b.startswith("建除"):
                    self.assertIn("「", b)
                else:
                    self.assertIn("（", b, "blockers 应是「理由（细节）」的中文短句：%s" % b)
                    self.assertTrue(b.endswith("）"), "细节括号应闭合：%s" % b)

    def test_blocked_days_never_in_candidates(self):
        r = F.zeri("入宅", "2026-12-01", "2026-12-31", None)
        usable = {c["date"] for c in r["candidates"]}
        blocked = {c["date"] for c in r["blocked"]}
        self.assertFalse(usable & blocked)
        self.assertEqual(len(usable) + len(blocked), r["summary"]["total_days"])

    def test_two_birth_years(self):
        r = F.zeri("入宅", "2026-12-01", "2026-12-15", [1990, 1992])
        self.assertEqual([m["year"] for m in r["ming_list"]], [1990, 1992])
        joined = "；".join(b for c in r["blocked"] for b in c["blockers"])
        self.assertIn("1990", joined)
        self.assertIn("1992", joined)

    def test_candidates_sorted_by_score(self):
        r = F.zeri("开市", "2026-12-01", "2026-12-31", None)
        scores = [c["score"] for c in r["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for c in r["candidates"]:
            for key in ("date", "ganzhi", "jianchu", "score", "reasons", "blockers"):
                self.assertIn(key, c)
            self.assertEqual(c["blockers"], [])

    def test_unknown_event_rejected(self):
        with self.assertRaises(ValueError):
            F.zeri("飞天", "2026-12-01", "2026-12-05", None)


class TestCli(unittest.TestCase):
    """独立运行与信封契约。"""

    def test_feixing_cli(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "fengshui.py"),
               "feixing", "--facing", "187", "--yun", "8", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        env = json.loads(proc.stdout)
        self.assertTrue(env["ok"])
        self.assertEqual(env["cmd"], "fengshui")
        self.assertEqual(env["result"]["sub"], "feixing")
        self.assertEqual(env["result"]["yun"], 8)
        self.assertEqual(len(env["result"]["palaces"]), 9)
        self.assertEqual(env["result"]["palaces"][4]["gong"], 5)

    def test_all_subcommands_json(self):
        cases = [
            ["mingua", "--birth", "1990-05-15", "--sex", "男"],
            ["bazhai", "--facing", "187"],
            ["liunian", "--year", "2026"],
            ["day", "--date", "2026-11-18"],
            ["zeri", "--event", "嫁娶", "--start", "2026-12-01", "--end", "2026-12-10"],
        ]
        for args in cases:
            cmd = [sys.executable, os.path.join(SCRIPTS, "fengshui.py")] + args + ["--json"]
            proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, "%s 失败：%s" % (args[0], proc.stderr))
            env = json.loads(proc.stdout)
            self.assertTrue(env["ok"], args[0])
            for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
                self.assertIn(key, env)

    def test_bad_facing_exit2(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "fengshui.py"),
               "feixing", "--facing", "某某", "--yun", "8", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["ok"])

    def test_missing_yun_exit2(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "fengshui.py"),
               "feixing", "--facing", "187", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
