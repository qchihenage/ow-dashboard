#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Overwatch 英雄数据分析
========================

读取爬虫产出的 CSV（data/hero_stats.csv），计算：

1. 当前赛季各英雄的「综合强度评分」：
       综合强度 = 0.6 × 胜率得分 + 0.4 × 出场率得分
   其中胜率 / 出场率都先做 min-max 归一化（0~100 分），
   以消除两者量纲不同带来的影响。

2. 按综合强度生成「强度梯度排行」（S / A / B / C / D）：
   在选定的段位内，把所有英雄按综合强度从高到低排序，
   按排名百分位分档：前 20% 为 S，20%~40% 为 A，40%~60% 为 B，
   60%~80% 为 C，后 20% 为 D。

3. 汇总成 JSON（data/dashboard_data.json），供 HTML 看板直接读取。

设计说明：
   不同段位的英雄强弱不同（例如高分段与低分段打法差异很大），
   因此「强度评分与梯度」在每个段位内独立计算，看板切换段位时排行联动更新。
   「All」段位即全段位汇总视图，作为看板默认展示。

用法：
    python analysis.py
"""

import csv
import json
import os
import sys
from collections import defaultdict

# Windows 控制台统一 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# 路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_CSV = os.path.join(DATA_DIR, "hero_stats.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "dashboard_data.json")

# 综合强度评分权重（胜率更能直接反映强度，故权重更高）
WINRATE_WEIGHT = 0.6
PICKRATE_WEIGHT = 0.4

# 梯度分档的边界（按排名百分位，从上到下）
GRADE_BOUNDS = [
    ("S", 0.20),
    ("A", 0.40),
    ("B", 0.60),
    ("C", 0.80),
    ("D", 1.00),
]


def load_rows():
    """读取 CSV，返回数据行列表（不含表头）与表头。"""
    with open(INPUT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))
    header, rows = reader[0], reader[1:]
    return header, rows


def to_float(value, default=0.0):
    """安全地把字符串转成 float，空值或异常时返回默认值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def minmax(values):
    """对一列数值做 min-max 归一化到 0~100，全相同则返回全 0。"""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) * 100.0 for v in values]


def assign_grades(scores):
    """按分数从高到低排序，用排名百分位分档 S/A/B/C/D。

    参数:
        scores -- dict { hero_id: 综合强度分 }
    返回:
        dict { hero_id: 梯度字母 }
    """
    # 分数降序排列：rank=0 是最强英雄
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    n = len(ranked)
    grades = {}
    for rank, (hero_id, _score) in enumerate(ranked):
        pct = rank / n  # 排名百分位（0~1）
        grade = "D"
        for g, bound in GRADE_BOUNDS:
            if pct < bound:
                grade = g
                break
        grades[hero_id] = grade
    return grades


def analyze():
    """主分析流程，返回准备写入 JSON 的完整字典。"""
    header, rows = load_rows()
    idx = {name: i for i, name in enumerate(header)}

    def col(row, name):
        return row[idx[name]]

    # 收集所有快照日期、赛季、段位
    snapshots = sorted({col(r, "snapshot_date") for r in rows})
    seasons = sorted({col(r, "season") for r in rows})
    tiers = sorted({col(r, "tier") for r in rows})
    current_season = seasons[-1]      # 当前赛季（最新）
    current_snapshot = snapshots[-1]  # 当前快照（最新日期）

    # 英雄元信息（id -> 名称/职责/子职责），取最新快照的任意一条即可
    heroes = {}
    for r in rows:
        if col(r, "snapshot_date") == current_snapshot:
            heroes[col(r, "hero_id")] = {
                "name": col(r, "hero_name"),
                "role": col(r, "role"),
                "subrole": col(r, "subrole"),
            }

    # 当前赛季按段位组织的数据，用于计算评分与梯度
    tier_data = {}
    for tier in tiers:
        # 取「当前赛季 + 当前快照 + 该段位」的行
        tier_rows = [
            r for r in rows
            if col(r, "season") == current_season
            and col(r, "snapshot_date") == current_snapshot
            and col(r, "tier") == tier
        ]
        if not tier_rows:
            continue

        hero_ids = [col(r, "hero_id") for r in tier_rows]
        winrates = [to_float(col(r, "winrate")) for r in tier_rows]
        pickrates = [to_float(col(r, "pickrate")) for r in tier_rows]
        banrates = [to_float(col(r, "banrate")) for r in tier_rows]

        # 归一化
        wr_norm = minmax(winrates)
        pr_norm = minmax(pickrates)

        # 综合强度评分
        scores = {
            hid: WINRATE_WEIGHT * wr + PICKRATE_WEIGHT * pr
            for hid, wr, pr in zip(hero_ids, wr_norm, pr_norm)
        }
        grades = assign_grades(scores)

        # 组装该段位的英雄列表，按综合强度降序，方便看板直接渲染排行
        entries = []
        for r, wr, pr in zip(tier_rows, wr_norm, pr_norm):
            hid = col(r, "hero_id")
            entries.append({
                "hero_id": hid,
                "name": heroes[hid]["name"],
                "role": heroes[hid]["role"],
                "subrole": heroes[hid]["subrole"],
                "winrate": to_float(col(r, "winrate")),
                "pickrate": to_float(col(r, "pickrate")),
                "banrate": to_float(col(r, "banrate")),
                "score": round(scores[hid], 2),
                "grade": grades[hid],
            })
        entries.sort(key=lambda e: -e["score"])
        tier_data[tier] = entries

    # 历史趋势：hero_id -> tier -> [ {date, winrate, pickrate, banrate} ]（按日期升序）
    history = defaultdict(lambda: defaultdict(list))
    for r in rows:
        hid, tier = col(r, "hero_id"), col(r, "tier")
        history[hid][tier].append({
            "date": col(r, "snapshot_date"),
            "winrate": to_float(col(r, "winrate")),
            "pickrate": to_float(col(r, "pickrate")),
            "banrate": to_float(col(r, "banrate")),
        })
    # 每个序列按日期排序
    for hid in history:
        for tier in history[hid]:
            history[hid][tier].sort(key=lambda d: d["date"])

    return {
        "meta": {
            "season": current_season,
            "current_snapshot": current_snapshot,
            "snapshots": snapshots,
            "seasons": seasons,
            "tiers": tiers,
            "generated_at": current_snapshot,
        },
        "heroes": heroes,
        "tier_data": tier_data,
        "history": history,
    }


def main():
    print("开始分析数据 ...")
    result = analyze()
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    meta = result["meta"]
    n_tiers = len(result["tier_data"])
    print(f"完成！赛季={meta['season']} | 快照={meta['current_snapshot']} "
          f"| 段位数={n_tiers} | 英雄数={len(result['heroes'])}")
    print(f"输出文件: {OUTPUT_JSON}")

    # 打印一段简要排行，便于快速核对
    if "All" in result["tier_data"]:
        print("\n全段位（All）强度排行 Top 10：")
        for e in result["tier_data"]["All"][:10]:
            print(f"  [{e['grade']}] {e['name']:<14} 评分 {e['score']:5.2f}  "
                  f"胜率 {e['winrate']:5.1f}%  出场 {e['pickrate']:5.1f}%")


if __name__ == "__main__":
    main()
