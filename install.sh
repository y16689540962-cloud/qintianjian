#!/usr/bin/env bash
# 钦天监 · 安装脚本
#
# 用法：
#   ./install.sh                 # 自动探测：装到 ~/.dsh/skills/qintianjian（DSH）
#   ./install.sh dsh             # 装到 ~/.dsh/skills/qintianjian
#   ./install.sh claude          # 装到 ~/.claude/skills/qintianjian（Claude Code）
#   ./install.sh codex           # 装到 ~/.codex/skills/qintianjian
#   ./install.sh /custom/path    # 装到指定目录
#   ./install.sh --uninstall     # 按探测结果卸载
#
# 只复制运行必需的文件（SKILL.md / references / scripts / evals / README / LICENSE），
# 不带 .git、.build 等开发文件。

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="qintianjian"

detect_target() {
  if [ -d "$HOME/.dsh/skills" ]; then
    echo "$HOME/.dsh/skills/$NAME"
  elif [ -d "$HOME/.claude/skills" ]; then
    echo "$HOME/.claude/skills/$NAME"
  elif [ -d "$HOME/.codex" ]; then
    echo "$HOME/.codex/skills/$NAME"
  else
    echo "$HOME/.agent-skills/$NAME"
  fi
}

case "${1:-}" in
  --uninstall)
    TARGET="${2:-$(detect_target)}"
    if [ -d "$TARGET" ]; then
      rm -rf "$TARGET"
      echo "已卸载：$TARGET"
    else
      echo "未安装：$TARGET"
    fi
    exit 0
    ;;
  dsh)      TARGET="$HOME/.dsh/skills/$NAME" ;;
  claude)   TARGET="$HOME/.claude/skills/$NAME" ;;
  codex)    TARGET="$HOME/.codex/skills/$NAME" ;;
  "")       TARGET="$(detect_target)" ;;
  *)        TARGET="$1" ;;
esac

echo "源目录：$SRC"
echo "目标：  $TARGET"

mkdir -p "$TARGET"
for item in SKILL.md README.md LICENSE references scripts evals; do
  if [ -e "$SRC/$item" ]; then
    rm -rf "$TARGET/$item"
    cp -R "$SRC/$item" "$TARGET/$item"
  fi
done

# 清掉 __pycache__，避免把字节码带进安装目录
find "$TARGET" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo
echo "安装完成。自检："
python3 "$TARGET/scripts/xuan.py" doctor || true
echo
echo "试用："
echo "  python3 \"$TARGET/scripts/bazi.py\" --solar 1990-05-15 --hour 12:00 --sex 男"
