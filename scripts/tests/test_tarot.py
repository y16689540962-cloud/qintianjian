#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔罗引擎的 unittest。

已知标准答案（RWS 公共领域牌库的固定事实，人工核对）：
  · 78 张 = 大阿卡纳 22 + 权杖/圣杯/宝剑/星币各 14
  · 大阿卡纳 0 号愚者、21 号世界；女祭司属水、皇帝属火
  · 小牌英文名：Knight of Cups / Page of Swords / King of Pentacles
  · 花色元素：权杖火、圣杯水、宝剑风、星币土
  · 牌阵牌位数：单张 1、三张 3、凯尔特十字 10
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

import tarot as T  # noqa: E402


def card_by(**kw):
    for c in T.DECK_RWS:
        if all(c.get(k) == v for k, v in kw.items()):
            return c
    raise AssertionError("找不到牌：%s" % kw)


class TestDeckStructure(unittest.TestCase):
    """牌库结构：78 张、花色与大小牌配比。"""

    def test_deck_size_and_composition(self):
        self.assertEqual(len(T.DECK_RWS), 78)
        self.assertEqual(len([c for c in T.DECK_RWS if c["arcana"] == "major"]), 22)
        for suit in T.SUITS:
            self.assertEqual(len([c for c in T.DECK_RWS if c["suit"] == suit]), 14)

    def test_no_duplicate_card_ids(self):
        ids = [c["id"] for c in T.DECK_RWS]
        self.assertEqual(len(ids), len(set(ids)))
        names = [c["name"] for c in T.DECK_RWS]
        self.assertEqual(len(names), len(set(names)), "牌名重复")

    def test_major_numbers_are_0_to_21(self):
        nums = sorted(c["num"] for c in T.DECK_RWS if c["arcana"] == "major")
        self.assertEqual(nums, list(range(22)))

    def test_suit_elements(self):
        self.assertEqual(T.SUIT_ELEMENT, {"权杖": "火", "圣杯": "水", "宝剑": "风", "星币": "土"})
        for c in T.DECK_RWS:
            if c["suit"]:
                self.assertEqual(c["element"], T.SUIT_ELEMENT[c["suit"]])


class TestKnownCards(unittest.TestCase):
    """具体牌面事实（手工核对）。"""

    def test_fool_and_world(self):
        self.assertEqual(card_by(num=0)["name"], "愚者")
        self.assertEqual(card_by(num=0)["element"], "风")
        self.assertEqual(card_by(num=21)["name"], "世界")
        self.assertEqual(card_by(num=21)["element"], "土")

    def test_high_priestess_water_emperor_fire(self):
        self.assertEqual(card_by(name="女祭司")["element"], "水")
        self.assertEqual(card_by(name="皇帝")["element"], "火")
        self.assertEqual(card_by(name="星星")["element"], "风")

    def test_minor_english_names(self):
        self.assertEqual(card_by(suit="圣杯", rank="Knight")["name_en"], "Knight of Cups")
        self.assertEqual(card_by(suit="宝剑", rank="Page")["name_en"], "Page of Swords")
        self.assertEqual(card_by(suit="星币", rank="King")["name_en"], "King of Pentacles")
        self.assertEqual(card_by(suit="权杖", rank="A")["name_en"], "Ace of Wands")
        for c in T.DECK_RWS:
            self.assertTrue(c["name_en"].isascii(), "%s 的英文名混入了中文：%s" % (c["name"], c["name_en"]))

    def test_minor_chinese_names(self):
        self.assertEqual(card_by(suit="星币", rank="A")["name"], "星币一")
        self.assertEqual(card_by(suit="宝剑", rank="10")["name"], "宝剑十")
        self.assertEqual(card_by(suit="权杖", rank="Queen")["name"], "权杖王后")

    def test_every_card_has_both_meanings(self):
        for c in T.DECK_RWS:
            self.assertTrue(c["upright"].strip(), "%s 缺正位义" % c["name"])
            self.assertTrue(c["reversed"].strip(), "%s 缺逆位义" % c["name"])
            self.assertNotEqual(c["upright"], c["reversed"], "%s 正逆位义相同" % c["name"])


class TestSpreads(unittest.TestCase):
    """牌阵牌位数与牌位含义。"""

    def test_position_counts(self):
        self.assertEqual(len(T.SPREADS["single"]["positions"]), 1)
        self.assertEqual(len(T.SPREADS["three"]["positions"]), 3)
        self.assertEqual(len(T.SPREADS["celtic"]["positions"]), 10)

    def test_three_positions_are_past_present_future(self):
        self.assertEqual([p["name"] for p in T.SPREADS["three"]["positions"]], ["过去", "现在", "未来"])

    def test_celtic_first_and_last(self):
        pos = T.SPREADS["celtic"]["positions"]
        self.assertEqual(pos[0]["name"], "现状")
        self.assertEqual(pos[1]["name"], "阻碍")
        self.assertEqual(pos[-1]["name"], "结果")

    def test_draw_returns_distinct_cards(self):
        for spread in ("single", "three", "celtic"):
            cards, _w, _s, picked = T.draw(spread, 42)
            self.assertEqual(len(cards), len(T.SPREADS[spread]["positions"]))
            self.assertEqual(len(picked), len(set(picked)), "抽到重复牌")

    def test_draw_is_without_replacement(self):
        for seed in range(30):
            _cards, _w, _s, picked = T.draw("celtic", seed)
            self.assertEqual(len(picked), 10)
            self.assertEqual(len(set(picked)), 10)


class TestReproducibility(unittest.TestCase):
    """seed 回放与正逆位分布。"""

    def test_same_seed_same_cards(self):
        a = T.analyze("three", "问", "rws", 42)
        b = T.analyze("three", "问", "rws", 42)
        self.assertEqual(json.dumps(a["result"], sort_keys=True), json.dumps(b["result"], sort_keys=True))

    def test_different_seed_different_cards(self):
        a = T.analyze("celtic", "问", "rws", 1)
        b = T.analyze("celtic", "问", "rws", 2)
        self.assertNotEqual([c["card_id"] for c in a["result"]["cards"]],
                            [c["card_id"] for c in b["result"]["cards"]])

    def test_orientation_roughly_balanced(self):
        up = down = 0
        for seed in range(200):
            _c, _w, _s, _p = T.draw("single", seed)
            res = T.analyze("single", "问", "rws", seed)["result"]["cards"][0]
            if res["upright"]:
                up += 1
            else:
                down += 1
        self.assertGreater(up, 60)
        self.assertGreater(down, 60)

    def test_generated_seed_is_recorded(self):
        out = T.analyze("single", "问", "rws", None)
        self.assertIsInstance(out["seed"], int)
        replay = T.analyze("single", "问", "rws", out["seed"])
        self.assertEqual([c["card_id"] for c in out["result"]["cards"]],
                         [c["card_id"] for c in replay["result"]["cards"]])


class TestResultContract(unittest.TestCase):
    """§6 result 字段与 CLI 信封。"""

    def test_required_fields(self):
        r = T.analyze("three", "问事", "rws", 7)["result"]
        for key in ("deck", "spread", "cards", "warnings"):
            self.assertIn(key, r)
        for c in r["cards"]:
            for key in ("pos", "name", "arcana", "orientation", "element", "keywords"):
                self.assertIn(key, c)
            self.assertIsInstance(c["keywords"], list)
            self.assertGreaterEqual(len(c["keywords"]), 2)
            self.assertIn(c["orientation"], ("正位", "逆位"))

    def test_keywords_follow_orientation(self):
        r = T.analyze("celtic", "问", "rws", 5)["result"]
        for c in r["cards"]:
            card = card_by(id=c["card_id"])
            src = card["upright"] if c["upright"] else card["reversed"]
            self.assertEqual(c["keywords"], [x.strip() for x in src.split("、") if x.strip()])

    def test_relations_and_summary(self):
        r = T.analyze("celtic", "问", "rws", 3)["result"]
        self.assertTrue(r["relations"])
        for rel in r["relations"]:
            self.assertEqual(len(rel["between"]), 2)
            self.assertIn("type", rel)
        s = r["summary"]
        self.assertEqual(s["count"], 10)
        self.assertEqual(s["major_count"] + s["minor_count"], 10)
        self.assertEqual(s["upright_count"] + s["reversed_count"], 10)

    def test_cli_json_envelope(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "tarot.py"),
               "--spread", "three", "--seed", "42", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        env = json.loads(proc.stdout)
        self.assertTrue(env["ok"])
        self.assertEqual(env["cmd"], "tarot")
        self.assertEqual(env["seed"], 42)
        self.assertEqual(len(env["result"]["cards"]), 3)

    def test_bad_deck_exit2(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "tarot.py"),
               "--spread", "single", "--deck", "thoth", "--json"]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
