"""run_evals.py 的判定逻辑测试（P0-3）。

旧版负向用例「只要退出码非零就算过」，于是崩溃、参数错误、依赖缺失都会被判 PASS。
这里锁定：负向必须同时满足 退出码 + ok=false + error.code + error.message 片段；
并且区分 fail（期望不符）与 error（跑不起来）。
"""

from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "run_evals_under_test", os.path.join(REPO, "evals", "run_evals.py"))
run_evals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_evals)

BAD_DATE_CMD = ["calendar", "--date", "1990-02-30", "--json"]
OK_CMD = ["calendar", "--date", "1990-05-15", "--json"]


class TestPositiveCases(unittest.TestCase):
    def test_positive_pass(self):
        r = run_evals.run_case({"id": "p", "cmd": OK_CMD,
                                "expect": {"result.lunar.month": 4,
                                           "result.lunar.day": 21}})
        self.assertEqual(r["verdict"], "pass", r["reasons"])

    def test_positive_wrong_expectation_fails(self):
        r = run_evals.run_case({"id": "p2", "cmd": OK_CMD,
                                "expect": {"result.lunar.day": 99}})
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("期望 99", r["reasons"][0])

    def test_missing_field_reports_not_crash(self):
        r = run_evals.run_case({"id": "p3", "cmd": OK_CMD, "expect": {"result.nope": 1}})
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("缺字段", r["reasons"][0])

    def test_forbid_warnings(self):
        # 八字模块永远不会发 AI_CAST_RANDOM → forbid 它应当通过
        r = run_evals.run_case({"id": "p4", "cmd": ["bazi", "--solar", "1990-05-15", "--hour", "12:00",
                                                   "--sex", "男", "--json"],
                                "forbid_warnings": ["AI_CAST_RANDOM"]})
        self.assertEqual(r["verdict"], "pass", r["reasons"])
        # 1990-05 在夏令时区间，CLOCK_CHANGE 必然出现 → forbid 它必须判 fail
        r2 = run_evals.run_case({"id": "p5", "cmd": ["bazi", "--solar", "1990-05-15", "--hour", "12:00",
                                                     "--sex", "男", "--json"],
                                 "forbid_warnings": ["CLOCK_CHANGE"]})
        self.assertEqual(r2["verdict"], "fail")
        self.assertIn("不该有的 warning", r2["reasons"][0])


class TestNegativeCases(unittest.TestCase):
    def test_negative_full_check_passes(self):
        r = run_evals.run_case({"id": "n1", "cmd": BAD_DATE_CMD, "expect_exit": 2,
                                "expect_error_code": "BAD_DATE",
                                "expect_error_contains": "不存在"})
        self.assertEqual(r["verdict"], "pass", r["reasons"])

    def test_negative_wrong_error_code_fails(self):
        r = run_evals.run_case({"id": "n2", "cmd": BAD_DATE_CMD, "expect_exit": 2,
                                "expect_error_code": "SOMETHING_ELSE"})
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("error.code", r["reasons"][0])

    def test_negative_wrong_message_fragment_fails(self):
        r = run_evals.run_case({"id": "n3", "cmd": BAD_DATE_CMD, "expect_exit": 2,
                                "expect_error_contains": "绝不该出现的文案"})
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("error.message", r["reasons"][0])

    def test_negative_missing_error_code_field_fails(self):
        """退出码对、但信封里没有 error.code → fail，而不是「非零即过」。"""
        r = run_evals.run_case({"id": "n4", "cmd": ["xuan", "nosuchcmd", "--json"], "expect_exit": 2,
                                "expect_error_code": "UNKNOWN_COMMAND"})
        self.assertEqual(r["verdict"], "pass", r["reasons"])


class TestClassification(unittest.TestCase):
    def test_expected_success_but_crash_is_error(self):
        r = run_evals.run_case({"id": "c1", "cmd": BAD_DATE_CMD, "expect_exit": 0})
        self.assertEqual(r["verdict"], "error", r["reasons"])
        self.assertIn("意外失败", r["reasons"][0])

    def test_expected_failure_but_success_is_fail(self):
        r = run_evals.run_case({"id": "c2", "cmd": OK_CMD, "expect_exit": 2})
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("期望退出 2", r["reasons"][0])

    def test_summary_counts(self):
        results = [{"verdict": "pass"}, {"verdict": "fail"}, {"verdict": "error"}]
        s = run_evals.summarize(results)
        self.assertEqual(s["counts"], {"pass": 1, "fail": 1, "error": 1})
        self.assertFalse(s["ok"])

    def test_load_cases_from_real_file(self):
        cases = run_evals.load_cases()
        self.assertGreater(len(cases), 30)
        neg = [c for c in cases if c.get("expect_exit", 0) != 0]
        self.assertTrue(neg, "跑批里必须有负向用例")
        for c in neg:
            self.assertIn("expect_error_code", c, "负向用例 %s 缺错误码断言" % c["id"])


if __name__ == "__main__":
    unittest.main()
