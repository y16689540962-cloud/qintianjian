# Qintianjian · 钦天监

[简体中文](README.md) · **English**

**An auditable Chinese astrology & divination agent skill. Every chart is computed by zero-dependency Python — never guessed by the model. Every claim is source-graded. When it cannot compute something, it says so.**

```bash
python3 scripts/xuan.py doctor                                     # self-check, ~10s, no deps
python3 scripts/bazi.py --solar 1990-05-15 --hour 12:00 --sex 男     # four pillars / luck cycles
```

`216` unit tests · `32` end-to-end cases · evidence + file hashes in [`evals/evidence/`](evals/evidence/) ·
calendar cross-checked on all `91,676` days (1850–2100) against an independent implementation, with 7 disputed
new moons arbitrated by the **USNO** moon-phase API

## What it covers

| Domain | Script | Notes |
|---|---|---|
| BaZi (four pillars) | `bazi.py` | pillars, hidden stems, ten gods, luck cycles, annual pillars, shensha |
| Zi Wei Dou Shu | `ziwei.py` | 12 palaces, five-element bureau, 14 major stars, four transformations, decadal cycles |
| Qi Men Dun Jia | `qimen.py` | hourly rotating chart: bureau, nine palaces, eight gates/stars/deities, duty officer |
| Liu Yao (I Ching) | `liuyao.py` | coin/yarrow/manual casting, Najia, shi-ying, six relatives, six spirits, hidden lines |
| Xuan Kong Feng Shui | `fengshui.py` | flying stars (mountain/water), Eight Mansions, annual purple-white, date selection |
| Marriage matching | `hehun.py` | day-pillar relationships, spouse stars, day-branch clashes |
| Tarot | `tarot.py` | full 78-card RWS deck, single/three/Celtic Cross spreads, seeded and replayable |
| Buddhist texts | — | canonical index with CBETA numbers; citation discipline, no ordination/ritual claims |
| Date selection | `fengshui.py day/zeri` | 12 officers, yellow/black paths, month/solar-year breaks, candidate ranking |

## Install

Clone the repo (or copy it) into your agent's skills directory:

```bash
git clone <repo-url> qintianjian
cp -R qintianjian ~/.claude/skills/qintianjian      # Claude Code
# or: ~/.dsh/skills/qintianjian (DSH) · ~/.codex/skills/qintianjian (Codex)
python3 ~/.claude/skills/qintianjian/scripts/xuan.py doctor
```

`install.sh` does the same with platform detection. Python 3.9+, **no third-party packages**, works offline.

## Why it is different

1. **Charts are computed, not narrated.** Every stem/branch/star/hexagram in an answer must be traceable to a
   script output in the same session.
2. **Claims carry a basis.** `calc` (from script fields) / `cited` (registered source) / `school` (lineage
   convention) / `model` (the model's own judgement). Model judgements may not use absolute wording.
3. **Silence over invention.** Missing birth hour → six-character chart only, with a `SHICHEN_UNKNOWN` warning.
   Null results → a three-paragraph "why I cannot answer" instead of a fabricated low-confidence reading.
4. **Disagreement is surfaced, not averaged.** Multiple lineages are presented side by side with an
   agree/disagree matrix; no "overall it's moderately auspicious".
5. **Hard limits.** No death/lifespan predictions, no medical diagnosis, no lawsuit outcomes, no stock calls,
   no fetal sex, no irreversible decisions on the user's behalf.

## Verify it yourself

```bash
python3 -m unittest discover -s scripts/tests -q   # 216 tests
python3 evals/run_evals.py                        # 32 end-to-end cases
python3 evals/lint_reading.py evals/samples/good.md
```

## Limits (read this before trusting any reading)

- Divination traditions disagree on many rules (true solar time, late *zi* hour, leap months, Qi Men bureau
  placement). The skill picks one convention per rule, labels it, and emits a `SCHOOL_VARIANT` warning.
- Qi Men, Liu Yao and Feng Shui charts are verified against *written rules*, not against an external oracle.
- Zi Wei is cross-checked against `iztro@2.6.2` on 546 charts (543 identical; 3 explainable differences).
- Culture and self-reflection only. Not medical, legal or financial advice.

## License

MIT for code; CC BY 4.0 for documentation. Classical texts and the *I Ching* are public domain.
