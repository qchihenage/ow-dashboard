# -*- coding: utf-8 -*-
"""
Overwatch 数据源配置
=====================

数据来自暴雪官方英雄数据页  https://overwatch.blizzard.com/en-us/rates/
（原 overbuff.com 已关停，改用其官方替代源。）

接口返回结构示例：
    {
      "rates": {
        "rates": [
          {
            "id": "ana",
            "cells": {"name": "Ana", "winrate": 48.3, "pickrate": 38.2, "banrate": 0},
            "hero": {"name": "Ana", "role": "SUPPORT", "subrole": "tactician"}
          }, ...
        ]
      }
    }
"""

from sources.base_source import DataSourceConfig


class OverwatchConfig(DataSourceConfig):
    """守望先锋（Overwatch）数据源配置。"""

    name = "Overwatch"

    # 数据接口（职责队列竞技模式下，段位筛选可用）
    api_url = "https://overwatch.blizzard.com/en-us/rates/data/"

    # rq=2 表示「职责队列竞技」（rq=0 为开放队列，无段位细分）
    query_params = {"rq": "2"}

    # 段位参数名
    tier_param = "tier"

    # 服务器列表（三个大区）
    regions = ["Asia", "Americas", "Europe"]

    # 段位列表（含全段位汇总 All）
    # 注：2026-08-11 补丁新增 Emerald（翡翠）段位
    tiers = [
        "All",          # 全段位汇总
        "Bronze",       # 青铜
        "Silver",       # 白银
        "Gold",         # 黄金
        "Platinum",     # 铂金
        "Emerald",      # 翡翠（2026 年新增）
        "Diamond",      # 钻石
        "Master",       # 大师
        "Grandmaster",  # 宗师
    ]

    # 当前赛季（Reign of Talon 第 4 赛季；新赛季到来时更新此值）
    season = "S4"

    # 请求头：带上接口要求的 AJAX 标识
    headers = {
        **DataSourceConfig.headers,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://overwatch.blizzard.com/en-us/rates/",
    }

    def parse_heroes(self, payload):
        """解析暴雪接口 JSON -> 标准英雄数据列表。"""
        heroes = []
        # 数据位于 payload.rates.rates
        for h in payload.get("rates", {}).get("rates", []):
            cells = h.get("cells", {})
            hero = h.get("hero", {})
            heroes.append({
                "id": h.get("id", ""),
                "name": cells.get("name", hero.get("name", "")),
                "role": hero.get("role", ""),
                "subrole": hero.get("subrole", ""),
                "winrate": cells.get("winrate", 0),
                "pickrate": cells.get("pickrate", 0),
                "banrate": cells.get("banrate", 0),
            })
        return heroes
