# 安装验证记录

> 目的：不是「我觉得能装」，而是「哪一步实测过、哪一步没测」。
> 记录日期 2026-11-18；环境 macOS 26（Apple Silicon）· Python 3.9.6。

## 1. 已验证（本机实测）

| 步骤 | 命令 | 结果 |
|---|---|---|
| DSH 安装 | `./install.sh dsh` | 复制到 `~/.dsh/skills/qintianjian`，`doctor` 8 模块 OK，第三方依赖「无」 |
| Claude Code 目录安装 | `./install.sh claude` | 复制到 `~/.claude/skills/qintianjian`，从该目录跑 `doctor` 通过（验证后已删副本，避免和 DSH 版混淆） |
| 从安装目录出盘 | `python3 ~/.dsh/skills/qintianjian/scripts/xuan.py calendar --date 2026-02-17` | 输出「丙午年 庚寅月 壬戌日 / 正月初一」，与仓库内运行一致 |
| 端到端 | `python3 evals/run_evals.py` | 34 passed, 0 failed, 0 errors |
| 单元测试 | `python3 -m unittest discover -s scripts/tests -q` | 260 tests, OK |

## 2. 未验证（必须在发布说明里写明，不许含糊）

| 项 | 为什么没测 | 风险 |
|---|---|---|
| **Claude Code 的 skill 自动发现** | 需要在 Claude Code 里新开会话才触发加载，本机没有该会话环境 | 文件放对了但没被发现；用户会以为「装了没反应」 |
| **Codex 的 skill 机制** | 本机 `~/.codex` 存在，但其 skill 加载约定未核实 | 同上；可能在 Codex 里根本不吃 SKILL.md |
| Windows | 没有环境 | 路径分隔符与 `shasum` 不可用（脚本本身纯 Python，理论可用） |
| Python 3.13+ | 只测了 3.9 / 3.11 / 3.12（CI 矩阵） | 低 |

## 3. 发布前必须做的一次验证（30 分钟）

1. 在 **Claude Code** 里新开会话，问一句「帮我算个八字」。若它没有调用本 skill，说明 `SKILL.md` 的
   frontmatter 或目录层级不对——这是发布阻塞项，不是小事。
2. 同一句话在 **Codex** 里再试一次；若 Codex 不认 SKILL.md，就在 README 里直接写「Codex 需手动把
   `scripts/` 当工具目录」，不要假装支持。
3. 把两次实测的截图/记录贴进本文件 §1。

## 4. 已知的安装坑

- **不要装两份**（`~/.dsh/skills` 与 `~/.claude/skills` 各一份）：两个 agent 会话会读到不同版本，
  改了一处另一处不动，排查时极难发现。选定一个目录，删掉另一个。
- `__pycache__` 会被 `install.sh` 清掉；如果你手动 `cp -R`，记得也清一遍。
- 安装后**必须**跑一次 `python3 scripts/xuan.py doctor`：它会同时检查模块是否齐、有没有引入第三方依赖。
