# 发布与分发：被 agent 抓到、被人类 star

> 本文是「号池评价 + 事实裁决」的结论，不是许愿清单。
> 评价方法：5 个模型独立评审方案 v0，原始回答在 `.out/review-skill/probe5-raw/`。
> 事实核查：ClawHub 实际搜索结果、本机 agent 环境、仓库现状。

## 0. 先摆三个能查证的事实（推翻主张前先看这个）

| 事实 | 证据 | 对策略的影响 |
|---|---|---|
| **ClawHub 八字类目已饱和且无流量** | `clawhub search "八字"` 返回 20+ 个 skill，绝大多数 **0–1 installs / 60d**；已有 `chinese-fortune-telling`（八字·六爻·塔罗）做组合定位 | ClawHub 是**分发占位**，不是增长发动机；别指望它带 star |
| **agent 的发现入口是 SKILL.md frontmatter，不是 README** | Claude Code / DSH / Codex 一类加载器读的是 skill 目录下的 `SKILL.md`（name + description）；GitHub 的 README 是人类的入口 | 双语触发词要写进 **description**，不是写进 README |
| **没有通用的 `catalog.json` / llms.txt 消费方** | 三类加载器都不读这两者；`llms.txt` 是给「已访问你站点」的爬虫用的，GitHub 仓库不经过这条路径 | 这两个文件不产生运行时行为，自造元数据 = 多一份要同步的东西 |

## 1. 号池评价：谁主张什么

| 动作 | 判「白做」的模型 | 判「先做」的模型 | 裁决 |
|---|---|---|---|
| `llms.txt` | glm、kimi | minimax | **砍**。没有消费方；等有独立 docs 站点时再说 |
| `catalog.json` / `skill-card.json` | kimi、mimo、minimax | deepseek | **砍**。无运行时消费者，且会与 SKILL.md 元数据漂移 |
| 首发就发 ClawHub | glm、deepseek、mimo、minimax | — | **降级为占位**：查重已做（20+ 同类），发布成本 10 分钟，但不计入增长预期 |
| awesome 清单 PR | kimi、minimax | glm（隐含） | **后置**：等仓库有 star 和 demo，PR 才像样 |
| 首屏放 GIF | deepseek | — | **后置**：先做「一条命令 + 预期输出」，GIF 是加分项不是卡点 |
| issue 模板「报一个算错的盘」 | deepseek | — | **保留但后置**：star < 100 时没人用，等有用户再开 |
| README 首屏 + About 双语关键词 | — | glm、kimi、mimo、minimax、deepseek（共识 5/5） | **先做（P0）** |
| 把证据（216 单测 / 32 用例 / 哈希）链到第二屏 | — | glm、kimi、minimax | **先做（P0）** |

## 2. 三个模型指出的真缺口（我采纳）

1. **golden demo**（deepseek）：agent 抓到 skill 后要能自检「现在还能不能跑」。→ 在 `SKILL.md` 顶部加「30 秒自检」三条命令 + 期望输出前三行。
2. **安装到第一次出盘的端到端验证文档**（glm）：方案 10 条全在讲「被找到」，没有一条验证「装上真能跑」。→ `docs/INSTALL-TEST.md`：按 DSH 实测记录，Claude Code / Codex 未测就写明未测。
3. **CI + badge**（minimax）：README 里的「216 测试全绿」如果只是口头声明，Release 后无法证明当前代码还过。→ `.github/workflows/ci.yml`：push/PR 跑单测 + 跑批 + lint，README 挂 badge。

## 3. 主线顺序（按「卡点 → 杠杆」排，不按好听排）

### P0 · 发布前（半天内）
1. **`SKILL.md` description 双语化**：英文首句 + 中文触发词 + 英文关键词 + 一句边界。这是 agent 的唯一入口。
2. **README 首屏三行**：一句定位 / 一条可复制命令 / 一句「证据在哪」。详细内容全部下移。
3. **`README.en.md`**：不是全文翻译，只写「能做什么 / 怎么装 / 证据 / 边界」，顶部互链。英文关键词铺开。
4. **`SKILL.md` 加 30 秒自检块**（doctor + 一条排盘 + 期望输出）。
5. **CI**：`.github/workflows/ci.yml`（py3.9/3.11 矩阵：unittest + evals + lint samples）。
6. **About + topics**（写进本文件 §5，复制粘贴用）：精准 topic，不堆 `ai-agents` 这类泛词。

### P1 · 发布当天
7. GitHub Release `v1.1.0` + `CHANGELOG.md`（已有 v1.1 变更）。
8. ClawHub 发布（`clawhub skill publish`，slug 用 `qintianjian`；预期低，只为 SkillHub 同步占位）。
9. 中文渠道：叙事锚定「开源排盘引擎 + 可复现测试」，**不出现「预测/改运/化解」话术**（合规红线，见 §4）。

### P2 · 有 star 之后
10. awesome 清单 PR、demo GIF、issue 模板、讨论区。

## 4. 风险与规避（综合 5 份意见 + 事实）

| 风险 | 为什么真 | 规避 |
|---|---|---|
| 平台把 divination 当迷信降权 | 中文平台对占卜类内容有整治记录；GitHub 不受影响，但中文分发会失效 | 中文文案只说「排盘算法 / 可复现 / 文化研究」，不说预测与改运；风水、姻缘在中文文案里降权，只作英文关键词 |
| 「排错了」的口碑攻击 | 术数有流派分歧（真太阳时、晚子时、紫微闰月、奇门置闰），用户拿专业软件一对就会吵 | README 与 SKILL.md 明示**每条争议规则取了哪一版**，并给 `SCHOOL_VARIANT` 警告码；被指错时先问「你用的是哪一派」 |
| 出生资料隐私 | 生日+时辰+地点是敏感个人信息 | 全本地运行、不收集、不上传；README 写死「不联网」 |
| 元数据漂移 | 自造 catalog.json 与 SKILL.md 两套名字/版本 | 不做第二套；版本只存在 `SKILL.md` 与 `CHANGELOG.md` |

## 5. 可直接复制粘贴的 GitHub 元数据

**About（350 字符内，双语关键词）**

> 九术合一的 Agent Skill：八字·紫微·奇门·六爻·玄空风水·姻缘·塔罗·佛学·择日。排盘由零依赖 Python 脚本确定性计算，每条判断标出处等级，算不出来就直说。| Auditable Chinese astrology agent skill: BaZi, Zi Wei, Qi Men, Liu Yao, Feng Shui, tarot, I Ching. Deterministic zero-dependency Python charts, source-graded claims, no hallucinated readings.

**Topics（精准优先，别堆泛词）**

```
claude-skills, agent-skills, chinese-astrology, bazi, ziwei, qimen, liuyao,
feng-shui, tarot, iching, divination, zero-dependency, python, deterministic
```

**仓库名**：`qintianjian`（保持；中文名做显示名，英文关键词靠 About 与 description 覆盖）。

## 6. 发布前要替换的占位符

README 顶部加 CI badge（把 `y16689540962-cloud` 换掉）：

```markdown
[![ci](https://github.com/y16689540962-cloud/qintianjian/actions/workflows/ci.yml/badge.svg)](https://github.com/y16689540962-cloud/qintianjian/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT%20%2B%20CC%20BY%204.0-blue)](LICENSE)
```

README.en.md 里的 `https://github.com/y16689540962-cloud/qintianjian`、`y16689540962-cloud` 两处也要替换；`docs/INSTALL-TEST.md` §2 的「未验证」保持原样，
发布说明里照抄——**别把没测过的平台写成支持**。
