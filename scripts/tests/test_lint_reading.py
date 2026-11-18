"""lint_reading.py 的正反测试（P0-2）。

覆盖三处旧缺陷：
  1. 表格里的断语被跳过 → 现在必须检查；
  2. 「据《书》」这种模糊引文被当成有状态 → 现在必须 ERROR；
  3. 一行两句、一句有 basis 另一句没有 → 现在逐句判定，不能互相掩盖。
另外锁定 WARN/ERROR 的显式规则表。
"""

from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LINT_PATH = os.path.join(REPO, "evals", "lint_reading.py")
_spec = importlib.util.spec_from_file_location("lint_reading_under_test", LINT_PATH)
lint_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_mod)


def doc(section2):
    """拼一份五段齐全的解读，只让第 2 段可变。"""
    return ("## 1. 盘面事实\n四柱 庚午 辛巳 庚辰 壬午\n\n"
            "## 2. 规则判断\n" + section2 + "\n"
            "## 3. 置信与分歧\n置信：中\n"
            "## 4. 可行动建议\n先做一件事\n"
            "## 5. 边界声明\n仅供参考\n")


def codes(items):
    return [i.split(" ", 1)[0] for i in items]


class TestStructure(unittest.TestCase):
    def test_missing_sections_error(self):
        errors, _ = lint_mod.lint("随便一段话")
        self.assertEqual(codes(errors).count("S1"), 5)

    def test_complete_sections_pass(self):
        errors, warns = lint_mod.lint(doc("- 日主庚金（calc）"))
        self.assertEqual(errors, [], errors)


class TestCitationStatus(unittest.TestCase):
    def test_vague_citation_without_status_is_error(self):
        """「据《滴天髓》……」是模糊引文，不能算有状态。"""
        errors, _ = lint_mod.lint(doc("- 据《滴天髓》云：身弱不胜财。"))
        self.assertTrue(any(e.startswith("S2") for e in errors), errors)

    def test_book_name_without_status_is_error(self):
        errors, _ = lint_mod.lint(doc("- 参考《三命通会》的用法。"))
        self.assertTrue(any(e.startswith("S2") for e in errors), errors)

    def test_explicit_status_passes(self):
        for status in ("（pub）", "（verified）", "（school）", "（undated）", "，pub）"):
            errors, _ = lint_mod.lint(doc("- 据《滴天髓》云：身弱不胜财%s。" % status))
            self.assertEqual(errors, [], "%s → %s" % (status, errors))


class TestBasisRule(unittest.TestCase):
    def test_judgment_without_basis_is_error(self):
        errors, _ = lint_mod.lint(doc("- 今年宜守不宜攻。"))
        self.assertTrue(any(e.startswith("S8") for e in errors), errors)

    def test_judgment_with_basis_passes(self):
        for tag in ("（calc）", "（cited）", "（school）", "（model）", "basis: model"):
            errors, _ = lint_mod.lint(doc("- 今年宜守不宜攻%s。" % tag))
            self.assertEqual(errors, [], "%s → %s" % (tag, errors))

    def test_table_judgment_is_checked(self):
        """旧版跳过以 | 开头的行；现在表格里的判断也要 basis。"""
        table = "| 流年 | 判断 |\n|---|---|\n| 2026 | 今年宜守 |\n"
        errors, _ = lint_mod.lint(doc(table))
        self.assertTrue(any(e.startswith("S8") for e in errors), errors)

    def test_table_judgment_with_basis_passes(self):
        table = "| 流年 | 判断 |\n|---|---|\n| 2026 | 今年宜守（model） |\n"
        errors, _ = lint_mod.lint(doc(table))
        self.assertEqual(errors, [], errors)

    def test_one_basis_cannot_cover_two_sentences(self):
        """一行两句：第一句有 basis，第二句没有 → 必须抓出第二句。"""
        errors, _ = lint_mod.lint(doc("- 今年宜守（model）；明年必有变动。"))
        s8 = [e for e in errors if e.startswith("S8")]
        self.assertEqual(len(s8), 1, errors)
        self.assertIn("变动", s8[0])


class TestWarnVsError(unittest.TestCase):
    def test_rules_table_matches_behaviour(self):
        """规则表与行为一致：表里 ERROR 的必须真的 ERROR，WARN 的不能变成 ERROR。"""
        self.assertEqual(lint_mod.RULES["S2"], "ERROR")
        self.assertEqual(lint_mod.RULES["S8"], "ERROR")
        for code in ("S5", "S6", "S10"):
            self.assertEqual(lint_mod.RULES[code], "WARN")

    def test_warn_only_case_stays_passing(self):
        """只触发 WARN（提到未知但没有 warning 码）时，不应判不合格。"""
        errors, warns = lint_mod.lint(doc("- 日主庚金（calc）\n时辰未知。"))
        self.assertEqual(errors, [], errors)
        self.assertTrue(any(w.startswith("S5") for w in warns), warns)

    def test_barnum_history_is_error(self):
        errors, _ = lint_mod.lint(doc("- 你 2015 年大概率有过一次搬迁（model）。"))
        self.assertTrue(any(e.startswith("S9") for e in errors), errors)

    def test_sample_files(self):
        for name, expect_ok in (("good.md", True), ("bad.md", False)):
            with open(os.path.join(REPO, "evals", "samples", name), encoding="utf-8") as fh:
                errors, _ = lint_mod.lint(fh.read())
            self.assertEqual(not errors, expect_ok, "%s → %s" % (name, errors))


class TestSummarize(unittest.TestCase):
    def test_summary_counts_by_code(self):
        errors, warns = lint_mod.lint(doc("- 今年宜守。\n- 据《滴天髓》云：x。"))
        stats = lint_mod.summarize(errors, warns)
        self.assertFalse(stats["ok"])
        self.assertEqual(stats["errors"], len(errors))
        self.assertGreaterEqual(stats["by_error"].get("S8", 0), 1)
        self.assertGreaterEqual(stats["by_error"].get("S2", 0), 1)
        self.assertIn("rules", stats)


if __name__ == "__main__":
    unittest.main()
