#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英雄竞技数据爬虫（数据源可配置）
================================

数据源：默认使用暴雪官方英雄数据页  https://overwatch.blizzard.com/en-us/rates/
        （原任务指定的 overbuff.com 已于 2025 年永久关停，故改用官方替代源。）

抓取内容：
    - 竞技模式下，各段位（青铜~宗师）的英雄胜率 / 出场率
    - 输出为 CSV「长表」格式，带赛季与快照日期，供分析与看板使用

可迁移性：
    爬虫主流程（遍历段位、反爬、写 CSV）与具体数据源解耦，
    所有随数据源变化的参数集中在 sources/ 下的配置类中。
    切换数据源只需改命令行参数，例如：
        python crawler.py --source marvel_rivals   # 使用 Marvel Rivals 配置

反爬策略：
    1. 伪装浏览器 User-Agent，并带上接口要求的请求头
    2. 每次请求之间加入随机延时，避免高频访问
    3. 失败自动重试，指数退避，避免偶发网络波动中断整个任务

用法：
    python crawler.py                    # 抓取 Overwatch 全部段位
    python crawler.py --tier Gold        # 只抓取指定段位
    python crawler.py --source marvel_rivals   # 切换数据源（迁移示范）
"""

import argparse
import csv
import os
import random
import sys
import time
from datetime import datetime

import requests

# 数据源配置类
from sources.overwatch import OverwatchConfig
from sources.marvel_rivals import MarvelRivalsConfig

# Windows 控制台默认使用 GBK 编码，会导致中文输出乱码；
# 这里把标准输出/错误流统一成 UTF-8，保证中文提示正常显示。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 可用的数据源注册表（新增数据源时在这里登记即可）
# ---------------------------------------------------------------------------
SOURCES = {
    "overwatch": OverwatchConfig,
    "marvel_rivals": MarvelRivalsConfig,
}

# 反爬参数
DELAY_MIN = 1.0     # 每次请求间的最小随机延时（秒）
DELAY_MAX = 2.5     # 最大随机延时（秒）
MAX_RETRIES = 3     # 单个请求的最大重试次数

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# CSV 表头（长表格式，与具体数据源无关）
CSV_HEADER = [
    "season",       # 赛季
    "tier",         # 段位
    "hero_id",      # 英雄英文 id
    "hero_name",    # 英雄名称
    "role",         # 职责（如 TANK / DAMAGE / SUPPORT）
    "subrole",      # 子职责（若该游戏有）
    "winrate",      # 胜率（%）
    "pickrate",     # 出场率（%）
    "banrate",      # 禁用率（%，无禁用则为 0）
    "snapshot_date",  # 快照日期（用于累积历史趋势）
]


def get_output_csv(source):
    """根据数据源决定输出文件路径（Overwatch 沿用固定文件名）。"""
    if source.name == "Overwatch":
        return os.path.join(OUTPUT_DIR, "hero_stats.csv")
    safe = source.name.lower().replace(" ", "_")
    return os.path.join(OUTPUT_DIR, f"hero_stats_{safe}.csv")


# ---------------------------------------------------------------------------
# 网络请求：带重试与退避（与数据源无关的通用逻辑）
# ---------------------------------------------------------------------------
def fetch_json(source, tier, session):
    """请求指定段位的数据，返回解析后的 JSON 字典。"""
    params = dict(source.query_params)
    params[source.tier_param] = tier

    # 指数退避重试：第 1 次失败等 2s，第 2 次等 4s，第 3 次等 8s
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(source.api_url, params=params,
                               headers=source.headers, timeout=20)
            resp.raise_for_status()  # 非 2xx 状态码会抛出异常
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  [警告] 段位 {tier} 第 {attempt}/{MAX_RETRIES} 次请求失败: {exc}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"段位 {tier} 重试 {MAX_RETRIES} 次后仍失败") from exc
            time.sleep(2 ** attempt)  # 退避：2s、4s


def fetch_tier_data(source, tier, session, snapshot_date):
    """把单个段位的接口数据，通过配置类解析成若干行 CSV 记录。"""
    payload = fetch_json(source, tier, session)
    heroes = source.parse_heroes(payload)  # 关键：解析规则来自配置类
    if not heroes:
        raise RuntimeError(f"段位 {tier} 返回的数据解析后为空")

    rows = []
    for h in heroes:
        rows.append([
            source.season,
            tier,
            h["id"],
            h["name"],
            h["role"],
            h["subrole"],
            h["winrate"],
            h["pickrate"],
            h["banrate"],
            snapshot_date,
        ])
    return rows


# ---------------------------------------------------------------------------
# CSV 读写：累积历史快照，且对同一天重复运行保持幂等
# ---------------------------------------------------------------------------
def load_existing_rows(path):
    """读取已有 CSV（若有），返回数据行列表（跳过表头）。"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))
    if not reader:
        return []
    return reader[1:] if reader[0][:2] == ["season", "tier"] else reader


def save_rows(path, rows):
    """把全部行写回 CSV（覆盖写，保证结构一致）。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="抓取英雄竞技数据（数据源可配置）")
    parser.add_argument("--source", choices=list(SOURCES.keys()), default="overwatch",
                        help="数据源（默认 overwatch）")
    parser.add_argument("--tier", help="只抓取指定段位（默认抓取全部段位）")
    args = parser.parse_args()

    # 通过配置类实例化数据源（换数据源 = 换这里的类）
    source = SOURCES[args.source]()
    tiers = [args.tier] if args.tier else source.tiers

    # 本次运行使用统一的快照日期（避免不同段位日期不一致）
    snapshot_date = datetime.now().strftime("%Y-%m-%d")

    print(f"开始抓取 | 数据源={source.name} | 赛季={source.season} "
          f"| 段位={tiers} | 快照日期={snapshot_date}")

    # 复用 Session，减少 TCP 握手开销
    session = requests.Session()
    session.headers.update(source.headers)

    all_new_rows = []
    for tier in tiers:
        print(f"正在抓取段位: {tier}")
        rows = fetch_tier_data(source, tier, session, snapshot_date)
        all_new_rows.extend(rows)
        print(f"  完成，共 {len(rows)} 个英雄")
        # 段位之间随机延时，降低被限流的概率
        if tier != tiers[-1]:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # 读取历史数据，去掉「今天」的旧快照（保证重复运行幂等），再拼上新数据
    output_csv = get_output_csv(source)
    existing = load_existing_rows(output_csv)
    kept = [r for r in existing if len(r) > 9 and r[9] != snapshot_date]
    final_rows = kept + all_new_rows
    final_rows.sort(key=lambda r: (r[9], r[1]))  # 按 快照日期、段位 排序

    save_rows(output_csv, final_rows)
    print(f"\n完成！本次新增 {len(all_new_rows)} 行，累计 {len(final_rows)} 行。")
    print(f"输出文件: {output_csv}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[错误] 爬虫异常终止: {exc}", file=sys.stderr)
        sys.exit(1)
