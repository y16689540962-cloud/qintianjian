"""doctor 自检的失败路径测试（P0-1）。

关键点：以前 `ok` 只由「第三方依赖」决定，模块缺失/导入失败/历法失灵/Python 版本不符都返回成功。
这里用临时目录构造每一种坏情况，确认 `diagnose()` 返回 ok=False 且 failure 指向具体检查项。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
REPO = os.path.dirname(SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import xuan  # noqa: E402


def copy_scripts(dst):
    """把真实 scripts 目录复制到临时目录（不含 tests，避免递归拖慢）。"""
    shutil.copytree(SCRIPTS, os.path.join(dst, "scripts"),
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    return os.path.join(dst, "scripts")


class TestDiagnose(unittest.TestCase):
    def test_healthy_repo_passes(self):
        report = xuan.diagnose(base_dir=SCRIPTS)
        self.assertTrue(report["ok"], report["failures"])
        self.assertTrue(report["checks"]["calendar"]["ok"])
        self.assertEqual(report["third_party_imports"], {})

    def test_missing_module_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            os.remove(os.path.join(dst, "tarot.py"))
            report = xuan.diagnose(base_dir=dst)
            self.assertFalse(report["ok"])
            checks = [f["check"] for f in report["failures"]]
            self.assertIn("module:tarot", checks)
            self.assertFalse(report["modules"]["tarot"]["present"])

    def test_broken_module_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            with open(os.path.join(dst, "qimen.py"), "w", encoding="utf-8") as fh:
                fh.write("raise ImportError('boom in qimen')\n")
            report = xuan.diagnose(base_dir=dst)
            self.assertFalse(report["ok"])
            checks = [f["check"] for f in report["failures"]]
            self.assertIn("module:qimen", checks)
            self.assertFalse(report["modules"]["qimen"]["importable"])
            self.assertIn("boom in qimen", report["modules"]["qimen"]["error"])

    def test_third_party_import_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            with open(os.path.join(dst, "sneaky.py"), "w", encoding="utf-8") as fh:
                fh.write("import requests\n")
            report = xuan.diagnose(base_dir=dst)
            self.assertFalse(report["ok"])
            self.assertIn("sneaky.py", report["third_party_imports"])
            self.assertIn("third_party", [f["check"] for f in report["failures"]])

    def test_python_too_old_fails(self):
        report = xuan.diagnose(base_dir=SCRIPTS, python_version=(3, 8, 0))
        self.assertFalse(report["ok"])
        self.assertFalse(report["python_ok"])
        self.assertIn("python", [f["check"] for f in report["failures"]])

    def test_calendar_probe_fails_on_wrong_answer(self):
        """历法文件在、能导入，但算错 → 必须抓出来（这是「文件存在 ≠ 能用」）。"""
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            with open(os.path.join(dst, "calendar_core.py"), "w", encoding="utf-8") as fh:
                fh.write(
                    "def solar_to_lunar(y, m, d):\n"
                    "    return {'year': y, 'month': 5, 'day': 1, 'leap': False}\n"
                    "def ganzhi_day(dt):\n"
                    "    return ('甲', '子')\n")
            report = xuan.diagnose(base_dir=dst)
            self.assertFalse(report["ok"])
            calendar_failures = [f for f in report["failures"] if f["check"] == "calendar"]
            self.assertEqual(len(calendar_failures), 1, report["failures"])
            self.assertIn("历法抽查不符", calendar_failures[0]["detail"])

    def test_missing_calendar_core_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            os.remove(os.path.join(dst, "calendar_core.py"))
            report = xuan.diagnose(base_dir=dst)
            self.assertFalse(report["ok"])
            self.assertFalse(report["has_calendar_core"])
            self.assertIn("calendar", [f["check"] for f in report["failures"]])


class TestDoctorCli(unittest.TestCase):
    def test_doctor_exit_code_nonzero_when_broken(self):
        """CLI 层：模块缺失时退出码必须是 2，且 JSON 里 ok=false。"""
        import json
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            dst = copy_scripts(tmp)
            os.remove(os.path.join(dst, "ziwei.py"))
            proc = subprocess.run([sys.executable, os.path.join(dst, "xuan.py"), "doctor", "--json"],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 2, proc.stdout[:300])
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["result"]["failures"])


if __name__ == "__main__":
    unittest.main()
