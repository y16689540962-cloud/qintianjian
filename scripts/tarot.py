#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔罗（Rider-Waite-Smith 体系）——78 张牌、正逆位、单张/三张/凯尔特十字。

职责
    按牌阵抽牌并给出牌位、正逆位、牌义关键词、牌间关系与全局统计。

输入
    --spread single|three|celtic  [--question 问题]  [--deck rws]  [--drawn-by ai|user]
    [--seed N]  [--json]

    诚实口径：脚本抽的牌一律带 `AI_DRAWN` 警告（drawn_by=ai，默认）；当事人亲手抽、
    只把结果交来记录时才用 `--drawn-by user`，那时不发该警告。

输出
    §3 统一信封；result 见 CONTRACT §6「tarot」最小集：deck / spread / cards[]/
    warnings[]，另加 relations[] / summary / positions[] 便于交叉解读。

口径来源（对应 references/tarot.md）
    · 图像与牌义基座：Rider-Waite-Smith 1909（Pamela Colman Smith 绘），已入公共领域  pub
    · 大阿卡纳行星/元素对应：Golden Dawn 通行体系  school
    · 小牌花色元素：权杖火、圣杯水、宝剑风、星币土  pub
    · 牌义为本脚本自撰中文关键词，不引用任何第三方牌义文本

已知局限
    · 只内置 RWS 一副牌（--deck rws）；其他牌系（Thoth、马赛）未收录，会明确报错
    · 正逆位按 50/50 抽取；部分流派用全正位，本脚本不提供该开关
    · 牌间关系只做结构层提示（花色/元素/大小牌/数字/正逆），不作吉凶裁决
    · 不做时间推断、不预测生死病灾（红线见 references/safety-ethics.md）
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

ENGINE = "qintianjian 1.0.0"
SCHEMA_VERSION = 1
CMD = "tarot"

SUITS: Tuple[str, ...] = ("权杖", "圣杯", "宝剑", "星币")
SUIT_ELEMENT: Dict[str, str] = {"权杖": "火", "圣杯": "水", "宝剑": "风", "星币": "土"}
ELEMENT_SHENG: Dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}

#: 大阿卡纳：(序号, 中文名, 英文名, 元素, 正位关键词, 逆位关键词)  school 元素对应
MAJOR_DATA: Tuple[Tuple[int, str, str, str, str, str], ...] = (
    (0, "愚者", "The Fool", "风",
     "新的开端、纯真、跃入未知、自由自在", "轻率、逃避责任、方向不明、鲁莽"),
    (1, "魔术师", "The Magician", "风",
     "创造力、资源齐备、意志专注、善于沟通", "操弄、才具虚耗、自欺、空谈"),
    (2, "女祭司", "The High Priestess", "水",
     "直觉、隐秘知识、内省、静待时机", "忽视直觉、秘密外泄、迷惘、self-doubt"),
    (3, "皇后", "The Empress", "土",
     "丰饶、滋养、母性、创意生长", "依赖、怠惰、创造力受阻、过度保护"),
    (4, "皇帝", "The Emperor", "火",
     "秩序、权威、结构、掌控局面", "专断、僵化、失序、抗拒约束"),
    (5, "教皇", "The Hierophant", "土",
     "传统、制度、指引、共同信念", "反叛、形式主义、教条、脱离体制"),
    (6, "恋人", "The Lovers", "风",
     "结合、抉择、吸引、价值一致", "犹豫、失和、错误选择、貌合神离"),
    (7, "战车", "The Chariot", "水",
     "前进、意志驾驭、克服、胜利", "失控、方向不明、蛮干、内耗"),
    (8, "力量", "Strength", "火",
     "耐心、柔性之力、驯服本能、勇气", "自我怀疑、暴躁、力不从心、逞强"),
    (9, "隐士", "The Hermit", "土",
     "独处、内省、求真、明师引路", "孤立、固执、逃避人群、闭门造车"),
    (10, "命运之轮", "Wheel of Fortune", "火",
     "转机、循环、机遇、无常中的定数", "逆势、重复旧局、抗拒变化、时机未到"),
    (11, "正义", "Justice", "风",
     "公正、因果、权衡、契约精神", "偏颇、逃避责任、失衡、执法不公"),
    (12, "倒吊人", "The Hanged Man", "水",
     "暂停、换位视角、牺牲、必要等待", "无谓拖延、僵持、抗拒转变、自伤"),
    (13, "死神", "Death", "水",
     "终结、蜕变、断舍、旧我谢幕", "抗拒结束、拖泥带水、停滞不前、藕断丝连"),
    (14, "节制", "Temperance", "火",
     "调和、节律、耐心、整合资源", "失衡、过度、躁进、难以整合"),
    (15, "恶魔", "The Devil", "土",
     "束缚、欲望、执念、诱人的交易", "觉察、松绑、戒断、挣脱控制"),
    (16, "塔", "The Tower", "火",
     "突变、崩解、意外、真相冲击", "延迟的崩塌、勉强维持、恐惧改变、内爆"),
    (17, "星星", "The Star", "风",
     "希望、疗愈、灵感、信心复原", "失望、信心低落、灵感枯竭、疗愈受阻"),
    (18, "月亮", "The Moon", "水",
     "幻象、潜意识、不安、暧昧未明", "迷雾渐散、真相浮现、焦虑退去、看清"),
    (19, "太阳", "The Sun", "火",
     "明朗、成功、童真、活力充沛", "暂时的阴影、过度乐观、成果迟到、虚火"),
    (20, "审判", "Judgement", "火",
     "觉醒、召唤、清算、复起", "自责、回避召唤、悬而未决、旧案重提"),
    (21, "世界", "The World", "土",
     "完成、整合、圆满、旅程抵达", "未竟、拖延、功亏一篑、闭环缺失"),
)

#: 小阿卡纳牌名英文（数字与宫廷牌）
RANK_EN: Dict[str, str] = {
    "A": "Ace", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
    "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine", "10": "Ten",
    "Page": "Page", "Knight": "Knight", "Queen": "Queen", "King": "King",
}

#: 小阿卡纳牌序与花色义基座
MINOR_RANKS: Tuple[Tuple[str, str], ...] = (
    ("A", "一"), ("2", "二"), ("3", "三"), ("4", "四"), ("5", "五"),
    ("6", "六"), ("7", "七"), ("8", "八"), ("9", "九"), ("10", "十"),
    ("Page", "侍从"), ("Knight", "骑士"), ("Queen", "王后"), ("King", "国王"),
)

#: 小阿卡纳：(花色, 牌序键) → (正位关键词, 逆位关键词)  自撰
MINOR_DATA: Dict[str, Dict[str, Tuple[str, str]]] = {
    "权杖": {
        "A": ("行动的新火种、契机上手、敢开头", "起步迟滞、热情受挫、空有想法"),
        "2": ("远景规划、握着选择、等待决断", "犹豫不决、计划悬空、不敢落子"),
        "3": ("拓展视野、远景成形、等回音", "延误、格局受限、合作未到位"),
        "4": ("阶段性稳定、庆典、安身之所", "根基未稳、不安全感、庆祝缺席"),
        "5": ("竞争、摩擦、混战、各执一词", "化解冲突、避战、内耗结束"),
        "6": ("胜利、公开认可、凯旋", "荣耀落空、认可迟到、名不副实"),
        "7": ("据守、抗压、以少敌多", "力不从心、弃守阵地、疲于应付"),
        "8": ("迅速推进、消息飞来、节奏加快", "迟滞、消息延误、节奏被打乱"),
        "9": ("疲惫未退、最后坚持、带伤守望", "透支、多疑、放下防备"),
        "10": ("重担在肩、超负荷、责任压身", "卸下负担、分摊、或不肯放手"),
        "Page": ("热切探索、新点子、跃跃欲试", "三分钟热度、方向散乱、欠缺准备"),
        "Knight": ("冲劲足、冒险、速行", "鲁莽、反复、半途而废"),
        "Queen": ("自信、热情、有感染力", "嫉妒、消耗、自我怀疑"),
        "King": ("领导力、远见、开创新局", "专横、独断、好大喜功"),
    },
    "圣杯": {
        "A": ("情感萌发、爱意流动、心的机会", "情感封闭、失落、错过示好"),
        "2": ("互许、结合、平等相待", "失衡、误会、貌合神离"),
        "3": ("欢庆、友谊、群体之乐", "人际疏离、过度放纵、塑料情谊"),
        "4": ("倦怠、视而不见、内向收缩", "重拾兴味、接受邀请、走出闷局"),
        "5": ("失落、遗憾、只盯着损失", "走出伤痛、接受现实、回望余温"),
        "6": ("回忆、旧情、纯真善意", "沉溺过去、旧事重提、无法向前"),
        "7": ("幻想、选项太多、看不清", "拨云见日、落到实处、拒绝空想"),
        "8": ("离开、舍弃、去寻更深的意义", "徘徊不去、割舍不下、去而复返"),
        "9": ("满足、愿望达成、享受当下", "贪求、虚满、奢望难填"),
        "10": ("圆满、家庭和睦、情感归宿", "表面和谐、关系裂痕、顾此失彼"),
        "Page": ("心动的消息、敏感初心、试探", "情绪化、幼稚、过度敏感"),
        "Knight": ("带着诚意而来、浪漫追求", "空口承诺、易变心、情绪化行事"),
        "Queen": ("共情、包容、温柔的洞察", "情绪淹没、过度依附、牺牲自己"),
        "King": ("情感成熟、有担当、外柔内定", "情感操控、压抑、冷处理"),
    },
    "宝剑": {
        "A": ("思路清明、真相、突破关卡", "混乱、误判、言语伤人"),
        "2": ("僵局、回避抉择、蒙眼平衡", "打破僵持、面对真相、被迫选择"),
        "3": ("心痛、决裂、创伤之刺", "疗愈开始、释怀、疼痛减轻"),
        "4": ("休整、静养、暂离战场", "无法休息、倦怠累积、强撑"),
        "5": ("争执、胜之不武、双输", "和解、放下胜负、退出无益之争"),
        "6": ("过渡、离开风暴、缓慢愈合", "被拉回旧境、难以抽身、复发"),
        "7": ("策略、取巧、暗中行事", "坦白、计谋败露、改为直取"),
        "8": ("自缚、限制、看不见出口", "松绑、找到出口、解除自我设限"),
        "9": ("焦虑、失眠、忧惧放大", "走出阴影、说出来、恐惧退潮"),
        "10": ("终结、谷底、无可再坏", "触底回升、余波未平、勉强收尾"),
        "Page": ("探问、警觉、心直口快", "口无遮拦、流言、轻率发言"),
        "Knight": ("直进、辩才、果断行动", "鲁莽、争强、冲撞他人"),
        "Queen": ("理性、独立、边界清楚", "冷峻、苛刻、受伤后的防卫"),
        "King": ("判断力、法度、专业权威", "严苛、滥用权威、冷酷裁决"),
    },
    "星币": {
        "A": ("机会落地、资源到位、可实操", "机会流失、投机、基础不牢"),
        "2": ("兼顾、平衡、弹性调度", "失衡、顾此失彼、周转不灵"),
        "3": ("协作、技艺、初具成果", "配合不良、做工粗疏、返工"),
        "4": ("保守、掌控、囤积自保", "松手、开放、或失守"),
        "5": ("匮乏、被排除在外、求助", "度过难关、接受援手、境况好转"),
        "6": ("给予与接受、分配公平", "施受失衡、施恩图报、救济不公"),
        "7": ("评估投入、耐心等收成", "焦躁、投入无果、方向要改"),
        "8": ("精进、反复练习、专注打磨", "敷衍、倦怠、匠气、停止学习"),
        "9": ("自立、丰足、享受经营成果", "过度依赖、虚有其表、焦虑失据"),
        "10": ("家业、传承、长远成果", "家事纠纷、短视、结构松动"),
        "Page": ("务实学习、小机会、勤勉起步", "拖延、眼高手低、纸上谈兵"),
        "Knight": ("稳步、勤勉、可靠守时", "僵化、停滞、枯燥无趣"),
        "Queen": ("务实的照料、安稳、丰足", "过度操劳、物质焦虑、掏空自己"),
        "King": ("成就、经营有道、稳定富足", "固执、贪利、掌控欲过强"),
    },
}

SPREADS: Dict[str, Dict[str, Any]] = {
    "single": {
        "name": "单张牌",
        "positions": [
            {"pos": 1, "name": "指引", "hint": "当下最需要看见的一件事"},
        ],
    },
    "three": {
        "name": "三张牌（时间流）",
        "positions": [
            {"pos": 1, "name": "过去", "hint": "已成形的原因与累积"},
            {"pos": 2, "name": "现在", "hint": "此刻的处境与心态"},
            {"pos": 3, "name": "未来", "hint": "趋势走向（非宿命）"},
        ],
    },
    "celtic": {
        "name": "凯尔特十字",
        "positions": [
            {"pos": 1, "name": "现状", "hint": "核心处境"},
            {"pos": 2, "name": "阻碍", "hint": "横在面前的力"},
            {"pos": 3, "name": "根基", "hint": "潜意识与根源"},
            {"pos": 4, "name": "过去", "hint": "刚过去的因"},
            {"pos": 5, "name": "目标", "hint": "显意识所求或理想"},
            {"pos": 6, "name": "未来", "hint": "近期走向"},
            {"pos": 7, "name": "自我", "hint": "你的态度与位置"},
            {"pos": 8, "name": "环境", "hint": "他人与外部条件"},
            {"pos": 9, "name": "希望与恐惧", "hint": "心之所系的两端"},
            {"pos": 10, "name": "结果", "hint": "综合后的落点"},
        ],
    },
}


# ===========================================================================
# 一、牌库
# ===========================================================================

def build_deck() -> List[Dict[str, Any]]:
    """构造 RWS 78 张牌。"""
    deck: List[Dict[str, Any]] = []
    for num, zh, en, elem, up, rev in MAJOR_DATA:
        deck.append({
            "id": "major-%02d" % num,
            "num": num,
            "name": zh,
            "name_en": en,
            "arcana": "major",
            "suit": None,
            "rank": None,
            "element": elem,
            "upright": up,
            "reversed": rev,
        })
    for suit in SUITS:
        for key, rank_zh in MINOR_RANKS:
            up, rev = MINOR_DATA[suit][key]
            label = "%s%s" % (suit, rank_zh)
            deck.append({
                "id": "minor-%s-%s" % (suit, key),
                "num": None,
                "name": label,
                "name_en": "%s of %s" % (
                    RANK_EN[key], {"权杖": "Wands", "圣杯": "Cups", "宝剑": "Swords", "星币": "Pentacles"}[suit]),
                "arcana": "minor",
                "suit": suit,
                "rank": key,
                "element": SUIT_ELEMENT[suit],
                "upright": up,
                "reversed": rev,
            })
    return deck


DECK_RWS: List[Dict[str, Any]] = build_deck()
if len(DECK_RWS) != 78:
    raise AssertionError("RWS 牌库应为 78 张，实得 %d" % len(DECK_RWS))


def _ensure_full_coverage() -> None:
    suits = {c["suit"] for c in DECK_RWS if c["arcana"] == "minor"}
    if suits != set(SUITS):
        raise AssertionError("花色不全：%s" % (suits,))
    for suit in SUITS:
        n = len([c for c in DECK_RWS if c["suit"] == suit])
        if n != 14:
            raise AssertionError("%s 花色的牌数应为 14，实得 %d" % (suit, n))
    if len([c for c in DECK_RWS if c["arcana"] == "major"]) != 22:
        raise AssertionError("大阿卡纳应为 22 张")


_ensure_full_coverage()


# ===========================================================================
# 二、抽牌
# ===========================================================================

def draw(spread: str, seed: Optional[int]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], int, List[int]]:
    """按牌阵抽牌，返回 (牌位结果, warnings, 实际使用的 seed, 抽到的牌索引)。"""
    if spread not in SPREADS:
        raise ValueError("未知牌阵 %r，可选：%s" % (spread, " / ".join(SPREADS)))
    n = len(SPREADS[spread]["positions"])
    warnings: List[Dict[str, str]] = []
    if seed is None:
        seed = random.SystemRandom().randrange(1, 10 ** 9)
        warnings.append({
            "code": "SEED_GENERATED",
            "message": "未给 --seed，已随机生成 %d 并写入信封，可用于回放" % seed,
        })
    rng = random.Random(seed)
    idxs = list(range(len(DECK_RWS)))
    rng.shuffle(idxs)                 # 洗牌（无放回）
    picked = idxs[:n]
    orientations = [rng.random() < 0.5 for _ in range(n)]  # 正逆位与洗牌共用同一随机流

    cards: List[Dict[str, Any]] = []
    for i, ci in enumerate(picked):
        card = DECK_RWS[ci]
        upright = orientations[i]
        pos_meta = SPREADS[spread]["positions"][i]
        cards.append({
            "pos": pos_meta["pos"],
            "position": pos_meta["name"],
            "position_hint": pos_meta["hint"],
            "name": card["name"],
            "name_en": card["name_en"],
            "card_id": card["id"],
            "arcana": card["arcana"],
            "suit": card["suit"],
            "rank": card["rank"],
            "orientation": "正位" if upright else "逆位",
            "upright": upright,
            "element": card["element"],
            "keywords": _split_keywords(card["upright"] if upright else card["reversed"]),
            "meaning": card["upright"] if upright else card["reversed"],
        })
    return cards, warnings, seed, picked


def _split_keywords(text: str) -> List[str]:
    return [part.strip() for part in text.split("、") if part.strip()]


# ===========================================================================
# 三、牌间关系与全局统计
# ===========================================================================

def _rel(a: Dict[str, Any], b: Dict[str, Any]) -> List[Dict[str, Any]]:
    """两张牌之间的结构关系（不作吉凶裁决）。"""
    out: List[Dict[str, Any]] = []
    pair = [a["pos"], b["pos"]]
    if a["arcana"] == "major" and b["arcana"] == "major":
        out.append({"between": pair, "type": "双大牌", "detail": "两处都是大阿卡纳，议题落在人生主线而非琐事"})
    if a["suit"] and a["suit"] == b["suit"]:
        out.append({"between": pair, "type": "同花色", "detail": "%s同属%s，同一领域的连续性" % (a["suit"], a["element"])})
    if a["element"] == b["element"]:
        out.append({"between": pair, "type": "同元素", "detail": "同属%s，能量单调，需外来元素破局" % a["element"]})
    elif ELEMENT_SHENG.get(a["element"]) == b["element"]:
        out.append({"between": pair, "type": "相生", "detail": "%s生%s，前位滋养后位" % (a["element"], b["element"])})
    elif ELEMENT_SHENG.get(b["element"]) == a["element"]:
        out.append({"between": pair, "type": "相生(逆)", "detail": "%s生%s，后位反过来滋养前位" % (b["element"], a["element"])})
    if a["rank"] and a["rank"] == b["rank"]:
        out.append({"between": pair, "type": "同点数", "detail": "同为%s，同一议题在两层重复出现" % a["rank"]})
    if a["upright"] != b["upright"]:
        out.append({"between": pair, "type": "正逆相对", "detail": "一正一逆，同一股力量一收一放"})
    return out


def analyze_relations(cards: Sequence[Dict[str, Any]], spread: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(len(cards) - 1):
        out.extend(_rel(cards[i], cards[i + 1]))
    if spread == "celtic" and len(cards) >= 10:
        for a, b, label, detail in (
            (cards[0], cards[1], "现状与阻碍", "第1、2张是正面冲突的一对，先看谁压住谁"),
            (cards[0], cards[9], "起点与结果", "第1张与第10张对看，判断是否同一议题的闭环"),
            (cards[5], cards[9], "走势与结果", "第6张与第10张对看，看趋势有没有被中途改写"),
        ):
            pair = sorted([a["pos"], b["pos"]])
            out.append({"between": pair, "type": label, "detail": detail,
                        "cards": [a["name"], b["name"]]})
    return out


def summarize(cards: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(cards)
    major = len([c for c in cards if c["arcana"] == "major"])
    rev = len([c for c in cards if not c["upright"]])
    elem_count: Dict[str, int] = {}
    suit_count: Dict[str, int] = {}
    for c in cards:
        elem_count[c["element"]] = elem_count.get(c["element"], 0) + 1
        if c["suit"]:
            suit_count[c["suit"]] = suit_count.get(c["suit"], 0) + 1
    notes: List[str] = []
    if n and major * 2 >= n:
        notes.append("大阿卡纳占 %d/%d，这次问的偏人生主线，不是一时一事" % (major, n))
    if n and rev * 2 > n:
        notes.append("逆位 %d/%d 偏多，多为主观阻滞或内化未发作" % (rev, n))
    if len(elem_count) == 1 and n > 1:
        notes.append("单一元素（%s），视角偏窄，容易被一种逻辑绑架" % list(elem_count)[0])
    for suit, cnt in suit_count.items():
        if cnt >= 3:
            notes.append("%s出现 %d 张，主题集中在这个领域" % (suit, cnt))
    return {
        "count": n,
        "major_count": major,
        "minor_count": n - major,
        "upright_count": n - rev,
        "reversed_count": rev,
        "element_count": elem_count,
        "suit_count": suit_count,
        "notes": notes,
    }


# ===========================================================================
# 四、人类可读输出
# ===========================================================================

def render_text(result: Dict[str, Any]) -> str:
    out: List[str] = []
    out.append("塔罗 · %s" % result["spread_name"])
    out.append("牌库：%s" % result["deck_name"])
    if result.get("question"):
        out.append("所问：%s" % result["question"])
    out.append("")
    out.append("| 位 | 牌位 | 牌名 | 正逆 | 元素 | 关键词 |")
    out.append("|---|---|---|---|---|---|")
    for c in result["cards"]:
        out.append("| %d | %s | %s | %s | %s | %s |" % (
            c["pos"], c["position"], c["name"], c["orientation"], c["element"],
            "、".join(c["keywords"])))
    out.append("")
    out.append("牌位含义：")
    for c in result["cards"]:
        out.append("- 第%d张 %s：%s —— %s" % (c["pos"], c["position"], c["position_hint"], c["meaning"]))
    if result["relations"]:
        out.append("")
        out.append("牌间关系：")
        for r in result["relations"]:
            out.append("- 第%d↔第%d张 %s：%s" % (r["between"][0], r["between"][1], r["type"], r["detail"]))
    s = result["summary"]
    out.append("")
    out.append("整体：大牌 %d / 小牌 %d；正位 %d / 逆位 %d" % (
        s["major_count"], s["minor_count"], s["upright_count"], s["reversed_count"]))
    for note in s["notes"]:
        out.append("- %s" % note)
    if result["warnings"]:
        out.append("")
        out.append("提示：")
        for w in result["warnings"]:
            out.append("- [%s] %s" % (w["code"], w["message"]))
    return "\n".join(out)


# ===========================================================================
# 五、组装与 CLI
# ===========================================================================

def analyze(spread: str, question: Optional[str], deck: str, seed: Optional[int],
            drawn_by: str = "ai") -> Dict[str, Any]:
    if deck != "rws":
        raise ValueError("只内置 rws（Rider-Waite-Smith）牌库，收到 %r" % deck)
    if drawn_by not in ("user", "ai"):
        raise ValueError("--drawn-by 只能是 user 或 ai，收到 %r" % (drawn_by,))
    cards, warnings, used_seed, _picked = draw(spread, seed)
    if not question:
        warnings.append({
            "code": "LOW_CONFIDENCE",
            "message": "未给 --question，解读只能按牌阵通用含义走，易发散射箭",
        })
    if drawn_by == "ai":
        # 诚信披露：牌是脚本洗出来抽的，不是当事人亲手抽的。
        warnings.append({
            "code": "AI_DRAWN",
            "message": "牌由脚本随机抽取，不是用户亲手抽的；"
                       "塔罗的传统做法是当事人抽牌，AI 抽牌只作反思素材",
        })
    result = {
        "deck": deck,
        "deck_name": "Rider-Waite-Smith 1909（公共领域）",
        "spread": spread,
        "spread_name": SPREADS[spread]["name"],
        "question": question,
        "drawn_by": drawn_by,
        "positions": SPREADS[spread]["positions"],
        "cards": cards,
        "relations": analyze_relations(cards, spread),
        "summary": summarize(cards),
        "warnings": warnings,
    }
    return {"result": result, "warnings": warnings, "seed": used_seed}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tarot.py",
        description="塔罗 RWS 78 张：单张 / 三张 / 凯尔特十字，带 seed 可回放")
    p.add_argument("--spread", default="three", choices=sorted(SPREADS.keys()),
                   help="牌阵：single / three / celtic（默认 three）")
    p.add_argument("--question", help="所问事由")
    p.add_argument("--deck", default="rws", help="牌库，仅支持 rws")
    p.add_argument("--drawn-by", default="ai", choices=["user", "ai"],
                   help="谁抽的牌：ai=脚本代抽（默认，会发 AI_DRAWN）；user=当事人亲手抽")
    p.add_argument("--seed", type=int, help="随机种子，便于回放")
    p.add_argument("--json", action="store_true", help="输出 JSON（默认人类可读）")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload_input = {
        "spread": args.spread,
        "question": args.question,
        "deck": args.deck,
        "drawn_by": args.drawn_by,
    }
    try:
        out = analyze(args.spread, args.question, args.deck, args.seed, args.drawn_by)
    except Exception as exc:  # 统一转信封 error + exit 2（契约 §9）
        if args.json:
            sys.stdout.write(json.dumps({
                "ok": False,
                "schema_version": SCHEMA_VERSION,
                "cmd": CMD,
                "engine": ENGINE,
                "input": payload_input,
                "error": {"code": "BAD_INPUT", "message": str(exc)},
            }, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stderr.write("错误：%s\n" % exc)
        return 2
    envelope = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "cmd": CMD,
        "engine": ENGINE,
        "input": payload_input,
        "result": out["result"],
        "warnings": out["warnings"],
        "seed": out["seed"],
    }
    if args.json:
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_text(out["result"]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
