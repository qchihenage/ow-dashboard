# -*- coding: utf-8 -*-
"""
数据源配置抽象基类
====================

爬虫逻辑里「会随数据源变化」的部分，全部集中到这个配置类里：

- 接口地址、固定请求参数
- 段位列表、当前赛季
- 请求头（反爬相关）
- 接口响应 -> 标准化英雄数据 的解析规则

切换到一个新游戏的数据源（例如 Marvel Rivals）时，只需继承本类、
覆盖相应字段/方法即可，爬虫主流程（遍历段位、随机延时、失败重试、
写 CSV）完全复用，无需改动一行爬虫代码。
"""


class DataSourceConfig:
    """数据源配置基类。子类必须覆盖以下字段与方法。"""

    # ---- 基本信息 ----
    name = "base"                 # 数据源显示名（用于日志输出）
    api_url = ""                  # 数据接口地址（GET，返回 JSON）
    query_params = {}             # 固定请求参数（如模式、平台等）
    tier_param = "tier"           # 段位对应的查询参数名（不同游戏可能不同）

    # ---- 段位与赛季 ----
    tiers = []                    # 要抓取的段位列表（第一项建议为「全段位汇总」）
    season = ""                   # 当前赛季编号

    # ---- 请求头（反爬：伪装浏览器 / 接口要求的标识） ----
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }

    # ------------------------------------------------------------------
    # 解析方法：把接口返回的 JSON 解析成标准化英雄数据列表。
    # 这是唯一需要按数据源定制逻辑的地方。
    #
    # 返回 list[dict]，每个 dict 含以下标准键（爬虫据此写 CSV）：
    #   id / name / role / subrole / winrate / pickrate / banrate
    # ------------------------------------------------------------------
    def parse_heroes(self, payload):
        """由子类实现：解析接口 JSON -> 标准英雄数据列表。"""
        raise NotImplementedError("子类必须实现 parse_heroes()")
