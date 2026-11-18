"""install.sh 的行为测试（P0-4）。

旧版问题：`doctor || true` 吞掉自检失败；目标/卸载无守卫，可能破坏别的 skill。
这里全部在临时目录里跑（HOME 也指向临时目录），不碰真实安装。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
INSTALL = os.path.join(REPO, "install.sh")
BASH = shutil.which("bash")


def make_source(tmp):
    """把运行必需的最小集合复制成一份「源仓库」，避免测试依赖真实仓库状态。"""
    src = os.path.join(tmp, "src")
    os.makedirs(src)
    shutil.copy2(INSTALL, os.path.join(src, "install.sh"))
    shutil.copy2(os.path.join(REPO, "SKILL.md"), os.path.join(src, "SKILL.md"))
    shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(src, "scripts"),
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    os.chmod(os.path.join(src, "install.sh"), 0o755)
    return src


@unittest.skipIf(BASH is None, "没有 bash")
class TestInstallSh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.src = make_source(self.tmp)
        self.env = dict(os.environ, HOME=self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *args, src=None):
        # 安装日志里混有中文与 emoji，且不同机器 locale 不同：用 replace 兜住解码错误，
        # 否则测试会因为「输出解码」而不是「安装行为」失败。
        return subprocess.run([BASH, os.path.join(src or self.src, "install.sh")] + list(args),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=self.env, timeout=180)

    def test_syntax_ok(self):
        proc = subprocess.run([BASH, "-n", INSTALL], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_install_success(self):
        target = os.path.join(self.tmp, "install", "qintianjian")
        proc = self.run_install(target)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(target, "SKILL.md")))
        self.assertTrue(os.path.isdir(os.path.join(target, "scripts")))
        # 自检真的跑了
        self.assertIn("全部检查通过", proc.stdout)

    def test_refuse_skills_root_and_keep_other_skills(self):
        root = os.path.join(self.home, ".dsh", "skills")
        other = os.path.join(root, "other-skill")
        os.makedirs(other)
        with open(os.path.join(other, "keep.txt"), "w", encoding="utf-8") as fh:
            fh.write("别删我")
        proc = self.run_install(root)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("skills 根目录", proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(other, "keep.txt")))

    def test_refuse_foreign_target(self):
        target = os.path.join(self.tmp, "foreign")
        os.makedirs(target)
        with open(os.path.join(target, "data.txt"), "w", encoding="utf-8") as fh:
            fh.write("用户数据")
        proc = self.run_install(target)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("不是本 skill", proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(target, "data.txt")))

    def test_force_overwrites_foreign_target(self):
        target = os.path.join(self.tmp, "foreign2")
        os.makedirs(target)
        with open(os.path.join(target, "data.txt"), "w", encoding="utf-8") as fh:
            fh.write("会被覆盖")
        proc = self.run_install(target, "--force")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(target, "SKILL.md")))

    def test_uninstall_refuses_foreign_dir(self):
        target = os.path.join(self.tmp, "foreign3")
        os.makedirs(target)
        proc = self.run_install("--uninstall", target)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("拒绝卸载", proc.stderr)
        self.assertTrue(os.path.isdir(target))

    def test_uninstall_removes_own_install(self):
        target = os.path.join(self.tmp, "install2", "qintianjian")
        self.assertEqual(self.run_install(target).returncode, 0)
        proc = self.run_install("--uninstall", target)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(target))

    def test_broken_source_fails_and_leaves_no_target(self):
        """源头坏掉（模块导入即抛错）→ 自检失败 → 安装必须非零退出，且不留半成品。"""
        with open(os.path.join(self.src, "scripts", "tarot.py"), "w", encoding="utf-8") as fh:
            fh.write("raise ImportError('boom')\n")
        target = os.path.join(self.tmp, "broken-target")
        proc = self.run_install(target)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("自检未通过", proc.stderr)
        self.assertFalse(os.path.exists(target))
        leftovers = [p for p in os.listdir(self.tmp) if ".installing." in p]
        self.assertEqual(leftovers, [], "临时目录没清理：%s" % leftovers)

    def test_no_verify_allows_skip(self):
        """显式 --no-verify 才跳过自检；这是唯一允许装坏包的路径。"""
        with open(os.path.join(self.src, "scripts", "tarot.py"), "w", encoding="utf-8") as fh:
            fh.write("raise ImportError('boom')\n")
        target = os.path.join(self.tmp, "noverify")
        proc = self.run_install(target, "--no-verify")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(target, "SKILL.md")))


if __name__ == "__main__":
    unittest.main()
