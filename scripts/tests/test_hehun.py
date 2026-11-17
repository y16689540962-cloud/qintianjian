"""合婚关系计算的回归测试。

分两层：
  1. 单元层：直接测关系表（干支合冲刑害），不跑子进程；
  2. 端到端：跑 hehun.py，确认信封与产物结构（依赖 bazi.py）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import hehun as H  # noqa: E402


class TestRelationTables(unittest.TestCase):
    def test_stem_he(self):
        kinds = [k for k, _ in H._stem_relation("甲", "己")]
        self.assertIn("stem_he", kinds)
        self.assertEqual(H.STEM_HE[("甲", "己")], "土")

    def test_stem_chong(self):
        kinds = [k for k, _ in H._stem_relation("甲", "庚")]
        self.assertIn("stem_chong", kinds)

    def test_branch_chong(self):
        kinds = [k for k, _ in H._branch_relation("子", "午")]
        self.assertIn("branch_chong", kinds)

    def test_branch_liuhe(self):
        kinds = [k for k, _ in H._branch_relation("寅", "亥")]
        self.assertIn("branch_he", kinds)

    def test_branch_sanhe(self):
        kinds = [k for k, _ in H._branch_relation("申", "子")]
        self.assertIn("branch_sanhe", kinds)

    def test_branch_hai(self):
        kinds = [k for k, _ in H._branch_relation("卯", "辰")]
        self.assertIn("branch_hai", kinds)

    def test_branch_xing(self):
        kinds = [k for k, _ in H._branch_relation("子", "卯")]
        self.assertIn("branch_xing", kinds)

    def test_self_xing(self):
        kinds = [k for k, _ in H._branch_relation("辰", "辰")]
        self.assertIn("branch_self_xing", kinds)

    def test_plain_pair_has_no_relation(self):
        """辰与亥无合冲刑害，不应臆造关系。"""
        self.assertEqual(H._branch_relation("辰", "亥"), [])


class TestEndToEnd(unittest.TestCase):
    def test_envelope_and_relations(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "hehun.py"),
               "--a-solar", "1990-05-15", "--a-hour", "12:00", "--a-sex", "男",
               "--b-solar", "1992-08-03", "--b-hour", "09:20", "--b-sex", "女",
               "--json"]
        proc = subprocess.run(cmd, cwd=os.path.dirname(SCRIPTS),
                              capture_output=True, text=True, timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr[:400])
        payload = json.loads(proc.stdout)
        for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
            self.assertIn(key, payload)
        self.assertEqual(payload["cmd"], "hehun")
        result = payload["result"]
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertEqual(result["a"]["day_pillar"], "庚辰")
        self.assertEqual(result["b"]["day_pillar"], "辛亥")
        # 庚辛同类，应识别为 stem_same
        types = [r["type"] for r in result["relations"]]
        self.assertIn("stem_same", types)
        # 每条关系都必须带出处状态，禁止裸结论
        for rel in result["relations"]:
            self.assertIn(rel["status"], ("pub", "school", "undated"))

    def test_missing_sex_is_rejected(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, "hehun.py"),
               "--a-solar", "1990-05-15", "--b-solar", "1992-08-03", "--json"]
        proc = subprocess.run(cmd, cwd=os.path.dirname(SCRIPTS),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "HEHUN_ERROR")


if __name__ == "__main__":
    unittest.main()
