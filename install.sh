#!/usr/bin/env bash
# 钦天监 · 安装脚本（v1.2：自检不再吞失败，目标/卸载均有守卫）
#
# 用法：
#   ./install.sh                 # 自动探测：装到 ~/.dsh/skills/qintianjian（DSH）
#   ./install.sh dsh             # 装到 ~/.dsh/skills/qintianjian
#   ./install.sh claude          # 装到 ~/.claude/skills/qintianjian（Claude Code）
#   ./install.sh codex           # 装到 ~/.codex/skills/qintianjian
#   ./install.sh /custom/path    # 装到指定目录（必须是"这个 skill 的目录"，不能是 skills 根目录）
#   ./install.sh --uninstall [path]   # 卸载；只删带本 skill 标记的目录
#
# 选项：
#   --force      目标已存在且不是本 skill 时，仍覆盖 / 仍卸载
#   --no-verify  跳过安装后的 doctor 自检（不推荐；默认自检失败 = 安装失败）
#
# 安全规则：
#   1. 拒绝装到 /、$HOME、以及各 agent 的 skills 根目录（那会污染/覆盖别的 skill）。
#   2. 拒绝装进源目录内部（避免递归复制）。
#   3. 目标已存在但没有本 skill 标记（SKILL.md 里 name: qintianjian）→ 拒绝，除非 --force。
#   4. 卸载只删带标记的目录；确认要删非本 skill 目录需 --force。
#   5. 先装到临时目录并跑自检，通过后才替换正式目录；失败不留半个安装。

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="qintianjian"
MARKER_RE="^name:[[:space:]]*${NAME}[[:space:]]*$"

die() { echo "错误：$*" >&2; exit 1; }
note() { echo "· $*"; }

have_marker() {
  [ -f "$1/SKILL.md" ] && grep -qE "$MARKER_RE" "$1/SKILL.md"
}

is_nonempty_dir() {
  [ -d "$1" ] && [ -n "$(ls -A "$1" 2>/dev/null || true)" ]
}

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

usage() { sed -n '3,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

# ---------- 参数 ----------
MODE="install"
TARGET=""
FORCE=0
VERIFY=1

while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) MODE="uninstall"; shift ;;
    --force)     FORCE=1; shift ;;
    --no-verify) VERIFY=0; shift ;;
    -h|--help)   usage; exit 0 ;;
    dsh)         TARGET="$HOME/.dsh/skills/$NAME"; shift ;;
    claude)      TARGET="$HOME/.claude/skills/$NAME"; shift ;;
    codex)       TARGET="$HOME/.codex/skills/$NAME"; shift ;;
    -*)          die "未知选项：$1（见 --help）" ;;
    *)           TARGET="$1"; shift ;;
  esac
done

[ -n "$TARGET" ] || TARGET="$(detect_target)"

# ---------- 目标守卫 ----------
validate_target() {
  local t="$1"
  [ -n "$t" ] || die "目标路径为空"

  case "$t" in
    "/"|"$HOME"|"$HOME/"|"."|"..") die "拒绝安装到危险路径：$t" ;;
  esac

  local root
  for root in "$HOME/.dsh/skills" "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agent-skills"; do
    [ "$t" = "$root" ] && die "拒绝安装到 skills 根目录：${t}
  —— 请指向它下面的子目录，例如 ${root}/${NAME}"
  done

  case "$t/" in
    "$SRC"/*) die "目标不能位于源目录内部：${t}（源：${SRC}）" ;;
  esac

  if [ -e "$t" ]; then
    [ -d "$t" ] || die "目标已存在且不是目录：$t"
    if have_marker "$t"; then
      note "检测到已安装的本 skill，将原地升级：$t"
      return 0
    fi
    if is_nonempty_dir "$t"; then
      [ "$FORCE" = 1 ] || die "目标已存在且不是本 skill（SKILL.md 缺失或 name 不是 ${NAME}）：${t}
  —— 为免破坏其它 skill，已中止。确认要覆盖请加 --force"
      note "--force：将覆盖非本 skill 目录 $t"
    fi
  fi
}

validate_uninstall_target() {
  local t="$1"
  [ -n "$t" ] || die "卸载目标为空"
  [ -e "$t" ] || die "目标不存在：$t"
  [ -d "$t" ] || die "目标不是目录：$t"
  case "$t" in
    "/"|"$HOME"|"$HOME/") die "拒绝删除危险路径：$t" ;;
  esac
  if ! have_marker "$t"; then
    [ "$FORCE" = 1 ] || die "拒绝卸载：$t 里没有本 skill 标记（SKILL.md 中 name: ${NAME}）
  —— 为免误删其它 skill/数据，已中止。确认要删请加 --force"
    note "--force：将删除非本 skill 目录 $t"
  fi
}

# ---------- 卸载 ----------
if [ "$MODE" = "uninstall" ]; then
  validate_uninstall_target "$TARGET"
  echo "将删除：$TARGET"
  rm -rf -- "$TARGET"
  echo "已卸载：$TARGET"
  exit 0
fi

# ---------- 安装 ----------
validate_target "$TARGET"

TMP="${TARGET}.installing.$$"
cleanup() { rm -rf -- "$TMP" 2>/dev/null || true; }
trap cleanup EXIT

note "源目录：$SRC"
note "目标：  $TARGET"
mkdir -p "$TMP"

for item in SKILL.md README.md README.en.md LICENSE references scripts evals; do
  if [ -e "$SRC/$item" ]; then
    cp -R "$SRC/$item" "$TMP/$item"
  fi
done

find "$TMP" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# 安装后自检：失败 = 安装失败（v1.2：不再用 `|| true` 吞掉）
if [ "$VERIFY" = 1 ]; then
  echo
  echo "安装后自检："
  if ! python3 "$TMP/scripts/xuan.py" doctor; then
    die "自检未通过，安装已中止（临时目录已清理，原目标未被改动）。
  —— 如果确认要跳过自检（不推荐），加 --no-verify 重跑"
  fi
fi

if [ -e "$TARGET" ]; then
  rm -rf -- "$TARGET"
fi
mv -- "$TMP" "$TARGET"
trap - EXIT

echo
echo "安装完成：$TARGET"
echo "试用："
echo "  python3 \"$TARGET/scripts/bazi.py\" --solar 1990-05-15 --hour 12:00 --sex 男"
