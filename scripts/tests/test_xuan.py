"""统一入口 xuan.py 的回归测试。

覆盖：子命令分发、--json 位置无关、信封字段、错误码、doctor 零依赖自检。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # scripts/tests -> scripts -> repo root
SCRIPTS = os.path.join(ROOT, "scripts")
XUAN = os.path.join(SCRIPTS, "xuan.py")


def run(args, timeout=120):
    proc = subprocess.run([sys.executable, XUAN] + args, cwd=ROOT,
                          capture_output=True, text=True, timeout=timeout)
    return proc


class TestDispatch(unittest.TestCase):
    def test_help_without_args(self):
        proc = run([])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("calendar", proc.stdout)
        self.assertIn("doctor", proc.stdout)

    def test_unknown_command_exit_2(self):
        proc = run(["nosuchcmd", "--json"])
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNKNOWN_COMMAND")

    def test_calendar_envelope(self):
        proc = run(["calendar", "--date", "1990-05-15", "--json"])
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        # 契约 §3 冻结的顶层键
        for key in ("ok", "schema_version", "cmd", "engine", "input", "result", "warnings", "seed"):
            self.assertIn(key, payload)
        self.assertEqual(payload["cmd"], "calendar")
        self.assertEqual(payload["result"]["lunar"]["month"], 4)
        self.assertEqual(payload["result"]["lunar"]["day"], 21)

    def test_calendar_bad_date_exit_2(self):
        proc = run(["calendar", "--date", "1990-02-30", "--json"])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "BAD_DATE")

    def test_json_flag_position_agnostic(self):
        """`--json` 写在子命令前或后，结果必须完全一致。"""
        a = run(["--json", "calendar", "--date", "2026-02-17"])
        b = run(["calendar", "--date", "2026-02-17", "--json"])
        self.assertEqual(a.returncode, 0)
        self.assertEqual(b.returncode, 0)
        ja, jb = json.loads(a.stdout), json.loads(b.stdout)
        self.assertEqual(ja["result"], jb["result"])

    def test_module_subcommand_json(self):
        proc = run(["fengshui", "feixing", "--facing", "187", "--yun", "8", "--json"])
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cmd"], "fengshui")
        self.assertEqual(payload["result"]["sub"], "feixing")
        self.assertEqual(payload["result"]["pattern"], "双星到向")


class TestDoctor(unittest.TestCase):
    def test_doctor_reports_zero_third_party(self):
        proc = run(["doctor", "--json"])
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["third_party_imports"], {})
        self.assertTrue(payload["result"]["python_ok"])
        # 所有引擎都应可导入
        for name, info in payload["result"]["modules"].items():
            if name in ("hehun",):  # 可选模块
                continue
            self.assertTrue(info.get("importable"), "%s 导入失败：%s" % (name, info.get("error")))


if __name__ == "__main__":
    unittest.main()
