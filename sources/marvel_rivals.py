# -*- coding: utf-8 -*-
"""
Marvel Rivals 数据源配置（迁移示范）
====================================

本文件用于演示「数据源抽象」的可迁移性：只需继承 `DataSourceConfig`
并覆盖字段/解析方法，即可把同一套爬虫框架复用到另一个游戏的数据源，
而无需修改 crawler.py 中的任何爬取逻辑。

说明：
    Marvel Rivals（漫威争锋）是 NetEase 出品的同类英雄竞技游戏，
    竞技段位体系与守望先锋不同（见下方 `tiers`）。
    下面以「假想的数据接口」为例，重点展示两点差异如何被配置类吸收：
      1. 接口地址、段位参数名、固定请求参数不同；
      2. 接口返回的 JSON 结构与字段命名不同（如 win_rate / pick_rate）。

    实际接入时，只需把 `api_url` 换成真实可用的接口、按真实返回结构
    调整 `parse_heroes`，其余保持不变。
"""

from sources.base_source import DataSourceConfig


class MarvelRivalsConfig(DataSourceConfig):
    """漫威争锋（Marvel Rivals）数据源配置（示范）。"""

    name = "Marvel Rivals"

    # 假想的数据接口（接入时替换为真实接口地址）
    api_url = "https://api.example.com/marvel-rivals/hero-stats/"

    # 固定请求参数：竞技模式
    query_params = {"mode": "competitive"}

    # 段位参数名（与守望先锋的 "tier" 不同，这里叫 "rank"）
    tier_param = "rank"

    # Marvel Rivals 竞技段位（与守望先锋不同：无翡翠、新增天体/永恒/至高一等）
    tiers = [
        "All",            # 全段位汇总
        "Bronze",         # 青铜
        "Silver",         # 白银
        "Gold",           # 黄金
        "Platinum",       # 铂金
        "Diamond",        # 钻石
        "Grandmaster",    # 大师
        "Celestial",      # 天体
        "Eternity",       # 永恒
        "One Above All",  # 至高一等
    ]

    # 当前赛季（Marvel Rivals 的赛季命名习惯不同，例如 "Season 2"）
    season = "Season 2"

    # 假想接口返回结构（与守望先锋的 { rates: { rates: [...] } } 完全不同）：
    #   { "data": { "heroes": [
    #       { "hero_id": "spider_man", "hero_name": "Spider-Man",
    #         "role_name": "Duelist", "win_rate": 51.2, "pick_rate": 18.4 }
    #   ] } }
    def parse_heroes(self, payload):
        """解析 Marvel Rivals 接口 JSON -> 标准英雄数据列表。

        注意字段命名差异：hero_name / role_name / win_rate / pick_rate，
        且数据路径为 data.heroes，与守望先锋的 rates.rates 不同。
        """
        heroes = []
        for h in payload.get("data", {}).get("heroes", []):
            heroes.append({
                "id": h.get("hero_id", ""),
                "name": h.get("hero_name", ""),
                "role": h.get("role_name", ""),
                # Marvel Rivals 无「子职责」概念，留空即可
                "subrole": "",
                "winrate": h.get("win_rate", 0),
                "pickrate": h.get("pick_rate", 0),
                "banrate": h.get("ban_rate", 0),
            })
        return heroes
