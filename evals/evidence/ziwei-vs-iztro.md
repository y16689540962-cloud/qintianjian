# 紫微斗数：本仓 `scripts/ziwei.py` vs `iztro@2.6.2`（MIT）

> 状态：**外部交叉核对**，2026-11-18 执行。`iztro` 是**外部 oracle，不是本 skill 的依赖**；
> 本仓 `scripts/` 零第三方依赖（`python3 scripts/xuan.py doctor` 会扫 import）。
> 需要 Node.js ≥ 18（本次用 v24.16.0）与 `npm i iztro@2.6.2` 才能重跑。

## 1 · 比对口径

| 项 | 取值 |
|---|---|
| oracle 版本 | `iztro@2.6.2`（自带 `lunar-typescript`） |
| 调用方式 | `astro.bySolar('<YYYY-M-D>', timeIndex, gender, true, 'zh-CN')`（第 4 参 = 是否配平闰月，固定 `true`） |
| 时辰映射 | `timeIndex=0` → `hour=0`（早子时）；`timeIndex=12` → `hour=23`（晚子时）；其余 → `hour = 2 × timeIndex` |
| 输入 | 只喂**公历**，避免农历输入本身的换算差异（农历输入的已知偏差单列在第 4 节） |
| 比较字段 | 命宫地支 / 身宫地支 / 五行局 / 命主 / 身主 / 12 宫名 / 12 宫干 / 14 主星**集合** / 主星庙旺 / 生年四化 / 主辅星（本仓实现的那 18 颗）/ 大限起止岁 |
| 归一 | iztro 的 `仆役`→`交友`、`奴仆`→`交友`；本仓按通行名对齐 |
| 判定 | 任一字段不等即记一条 fail，不做"差不多"式的容忍 |

**不比**：流年/流月飞星四化（iztro 的 `horoscope` 与本文口径不同）、小限、神煞全集——这几项在 README「已知局限」里已标未交叉核对。

## 2 · 覆盖范围

| 批次 | 盘数 | 日期 | timeIndex | 说明 |
|---|---|---|---|---|
| 第 1 批 | 208 | 1950–2035 | 0,1,3,5,6,7,9,11 各 26 | 固定 8 个时辰位 + 性别覆盖 |
| 第 2 批 | 330 | 1900–2035 | 1–11 | 随机日期，含 1916-02-15 |
| 第 3 批（晚子时专项） | 8 | 1950–2026 | 12 | 专测 `23:00–24:00` 换日口径 |
| **合计** | **546** | 1900–2035 | 0–12 | 538 盘覆盖 **333 个不同日期**（同日期多时辰/多性别）+ 8 盘晚子时；男 262 / 女 276 |

## 3 · 结果（真实跑数）

**543 / 546 盘逐字段 0 差异**；**3 盘有差异，归为 2 类根因**：

| 类 | 盘 | 差异字段 | 根因 |
|---|---|---|---|
| ① 农历月首差一天 | `1916-02-15`（第 2 批 r176，丑时） | 12 宫主星集合整盘错位（命宫/身宫/五行局仍一致） | iztro 把 1916 年正月初一定在 **02-03**，本实现（USNO 月相仲裁）定在 **02-04**；紫微按农历**日**安星 → 差一天即整体错一位 |
| ② 晚子时换日口径 | `1990-05-15`（ti=12）、`2020-06-15`（ti=12） | 命宫/身宫/五行局 + 由命宫派生的宫名、大限、主星全盘错位（各 40 条字段级差异） | 23:00–24:00 这一小时：本实现按**子初换日**处理（发 `LATE_ZI` 警告），iztro 对命宫仍按当日、日柱却已进次日 |

> README 写「2 处已标注例外」是**按根因类**计；按盘数是 3 盘。两处说法并不矛盾，但以本文件的分盘清单为准。
> 第 ① 类的本质是**历法**问题，与 `calendar-vs-lunarpython.md` 里 1916-02 那个争议月首是同一件事：
> 谁把「朔在 00:05」判到前一天，谁的农历日就整体早一天。

## 4 · 复现命令

```bash
# 一次性准备（联网；建在临时目录，不污染本仓）
mkdir -p /tmp/iztro-check && cd /tmp/iztro-check
npm init -y && npm i iztro@2.6.2

# 1) 造 oracle：把 cases*.json 里每盘的盘面 dump 成 JSON
#    （gen.mjs 的字段见下；用 `node gen.mjs cases.json iztro_out.json` 调用）
# 2) 逐字段比：本仓 ziwei_chart 对 oracle 断言
python3 cmp.py    # 对应 cases.json  → cases compared: 208, fails: 0
python3 cmp2.py   # 对应 cases2.json → cases compared: 330, fails: 12（全部 major_set，同一盘 r176=1916-02-15）
python3 cmp3.py   # 对应 cases3.json → 晚子时专项：8 盘里 1990-05-15 / 2020-06-15 整盘错位
```

`gen.mjs` 里每盘取这些字段落盘（与第 1 节比较字段一一对应）：

```js
const a = astro.bySolar(c.solar, c.timeIndex, c.sex, true, 'zh-CN');
({ key, solar, timeIndex, sex, lunar: a.lunarDate, gz: a.chineseDate,
   ming: a.earthlyBranchOfSoulPalace, shen: a.earthlyBranchOfBodyPalace,
   ju: a.fiveElementsClass, soul: a.soul, body: a.body,
   palaces: a.palaces.map(p => ({
     branch: p.earthlyBranch, stem: p.heavenlyStem, name: p.name,
     major: p.majorStars.map(s => ({name: s.name, brightness: s.brightness||'', mutagen: s.mutagen||''})),
     minor: p.minorStars.map(s => ({name: s.name, mutagen: s.mutagen||''})),
     adj: (p.adjectiveStars||[]).map(s => s.name),
     decadal: p.decadal ? {range: p.decadal.range} : null })) })
```

### 4.1 差异 ①：1916-02-15 的农历输入偏早一天

```bash
node -e "const {astro}=require('iztro');
for (const d of ['1916-2-14','1916-2-15','1916-2-16']) {
  const a=astro.bySolar(d,6,'男',true,'zh-CN');
  console.log(d,'lunar='+a.lunarDate,'命='+a.earthlyBranchOfSoulPalace);
}"
# 实测：
#   1916-2-14 lunar=一九一六年正月十二 命=申
#   1916-2-15 lunar=一九一六年正月十三 命=申
#   1916-2-16 lunar=一九一六年正月十四 命=申
```

三日命宫都是 `申`（命宫只看农历月与时支，不看日），但**主星集合随农历日变**——所以 `r176`
的差异只落在 `major_set`，落在命宫上的字段反而一致。这正好证明差异来自「日」而不是「月/时」。

本实现同三日的农历是 **正月十一 / 十二 / 十三**（`solar_to_lunar` 可查，月首 1916-02-04，朔 00:05:17）。
即 iztro 的农历**早一天**；若把农历日期当输入（`byLunar`），取到的公历也会早一天——这就是"农历输入偏早"。

```bash
node -e "const {astro}=require('iztro');
const b=astro.byLunar('1916-1-13',6,'男',false,true,'zh-CN');
console.log('byLunar 1916-1-13 -> solar', b.solarDate);"
# 实测：1916-2-15（本实现：正月十三 = 1916-02-16）
```

### 4.2 差异 ②：2020-06-15 晚子时，iztro 自相矛盾

```bash
node -e "const {astro}=require('iztro');
for (const [s,ti] of [['2020-6-16',0],['2020-6-15',0],['2020-6-15',12]]) {
  const a=astro.bySolar(s,ti,'男',true,'zh-CN');
  console.log(s,'ti='+ti,'lunar='+a.lunarDate,'gz='+a.chineseDate,'命='+a.earthlyBranchOfSoulPalace,'局='+a.fiveElementsClass);
}"
# 实测：
#   2020-6-16 ti=0  lunar=二〇二〇年闰四月廿五 gz=庚子 壬午 庚寅 丙子 命=午 局=木三局
#   2020-6-15 ti=0  lunar=二〇二〇年闰四月廿四 gz=庚子 壬午 己丑 甲子 命=午 局=木三局
#   2020-6-15 ti=12 lunar=二〇二〇年闰四月廿四 gz=庚子 壬午 庚寅 丙子 命=巳 局=金四局
```

看清矛盾在哪：`2020-6-15 ti=12` 的**日柱已经是次日（庚寅 丙子）**，但**农历仍写当日（闰四月廿四）**，
命宫却给出 `巳`——既不是当日早子时的 `午`，也不是次日早子时的 `午`。同一盘内部三处口径打架，
所以这一条不能拿 iztro 当 oracle；本实现给 `午 / 木三局` 并只发 `LATE_ZI` 警告。

`1990-05-15 ti=12` 是同一类（本实现 `午`，iztro `巳`），但它不自相矛盾，只是**晚子时换不换日**的流派分歧：

```bash
node -e "const {astro}=require('iztro');
for (const [s,ti] of [['1990-5-15',0],['1990-5-16',0],['1990-5-15',12]]) {
  const a=astro.bySolar(s,ti,'男',true,'zh-CN');
  console.log(s,'ti='+ti,'gz='+a.chineseDate,'命='+a.earthlyBranchOfSoulPalace);
}"
# 实测：1990-5-15 ti=0 → 命巳；1990-5-16 ti=0 → 命巳；1990-5-15 ti=12 → 命巳（日柱已到辛巳）
```

## 5 · 已知未验证

- 1900 年以前、2035 年以后未逐盘对（iztro 与本仓的农历表在 1900 前都会退化为低精度，比了也说明不了谁对）。
- 流年/流月/流日四化、小限、神煞全集未纳入比对。
- 大限起限"虚岁 vs 周岁"口径：本次比的是 iztro `decadal.range` 的岁数区间，一致；不同 book 参数下的变体未测。
