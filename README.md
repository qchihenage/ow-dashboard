# Overwatch 英雄强度看板

一个**全流程可复现**的英雄竞技数据看板项目：从数据采集 → 强度分析 → 可视化看板 → 每周自动更新部署，适合作为简历作品展示。

> **在线看板**：`https://<你的用户名>.github.io/<仓库名>/`（部署方法见文末）

---

## 项目做了什么

| 模块 | 说明 |
|------|------|
| **爬虫** | 抓取守望先锋各英雄竞技数据（胜率、出场率、禁用率），按**段位（青铜~宗师）**分别采集，含反爬与中文注释 |
| **数据分析** | 计算各英雄**综合强度评分**（胜率 + 出场率加权），生成 **S / A / B / C / D** 强度梯度排行 |
| **看板** | 基于 ECharts 的交互式 HTML 看板：赛季/段位筛选、胜率柱状图（颜色深浅=出场率）、单英雄历史趋势折线图、强度梯度排行侧边栏 |
| **部署** | GitHub Actions 每周自动抓取更新，部署到 GitHub Pages |
| **迁移示范** | 数据源抽象成配置类，附 Marvel Rivals 配置证明可迁移 |

### 数据源说明

原任务指定的数据源 **overbuff.com 已于 2025 年永久关停**（网站返回告别信，并引导用户前往暴雪官方数据页）。因此本项目改用其官方替代源：

- 数据接口：`https://overwatch.blizzard.com/en-us/rates/data/`
- 说明：暴雪官方接口不提供历史赛季数据，本项目按需求「**从当前赛季开始、不追溯历史**」，以每周快照的方式逐步累积出历史趋势。

---

## 技术栈

- **Python 3.12**：爬虫（`requests`）与数据分析（标准库 `csv` / `json`）
- **ECharts 5**：数据可视化
- **HTML / CSS / JavaScript**：看板前端
- **GitHub Actions + GitHub Pages**：自动化更新与部署

---

## 怎么跑

### 0. 环境要求

- Python 3.8+（推荐 3.12）
- 安装依赖：`pip install -r requirements.txt`

### 1. 抓取数据

```bash
python crawler.py                      # 抓取 Overwatch 全部段位
python crawler.py --tier Grandmaster   # 只抓取指定段位
python crawler.py --source marvel_rivals   # 切换数据源（迁移示范）
```

- 输出：`data/hero_stats.csv`（长表格式，含赛季/段位/胜率/出场率等字段）
- 每次运行追加当日快照；同一天重复运行会去重，保证幂等。

### 2. 生成看板数据

```bash
python analysis.py
```

- 输出：`data/dashboard_data.json`（含评分、梯度排行、历史趋势）

### 3. 本地预览看板

```bash
python -m http.server 8000
# 浏览器打开 http://localhost:8000/index.html
```

> 看板通过 `fetch` 加载数据，需经 HTTP 服务访问（直接双击打开 HTML 会因跨域限制无法加载数据）。

---

## 强度评分与梯度

- **综合强度评分** = `0.6 × 胜率得分 + 0.4 × 出场率得分`，胜率/出场率各自先做 min-max 归一化到 0~100 分，消除量纲差异。
- **梯度排行**：在选定段位内按综合强度排序，按排名百分位分档——前 20% 为 **S**，20%~40% 为 **A**，40%~60% 为 **B**，60%~80% 为 **C**，后 20% 为 **D**。
- 权重（0.6 / 0.4）与分档边界均为可调常量，见 `analysis.py`。

---

## 项目结构

```
ow-dashboard/
├── crawler.py                  # 爬虫主流程（数据源可配置）
├── analysis.py                 # 数据分析：评分 + 梯度 + 看板 JSON
├── index.html                  # ECharts 看板
├── requirements.txt            # 依赖
├── sources/                    # 数据源配置（迁移示范）
│   ├── base_source.py          #   抽象基类
│   ├── overwatch.py            #   Overwatch 配置
│   └── marvel_rivals.py        #   Marvel Rivals 配置（示范）
├── data/                       # 数据（爬虫与分析产物）
│   ├── hero_stats.csv          #   原始数据
│   └── dashboard_data.json     #   看板数据
└── .github/workflows/update.yml  # 每周自动更新 + 部署
```

---

## 部署到 GitHub Pages

1. **新建 GitHub 仓库**，把本项目代码推送到仓库：

   ```bash
   git init
   git add .
   git commit -m "init: OW hero dashboard"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```

2. **开启 Pages 的 Actions 部署**：仓库 `Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions**。

3. **触发首次部署**：`Actions` 标签页 → 左侧 `Weekly Data Update` → `Run workflow`。之后会**每周一自动**运行（也可随时手动触发）。

4. 部署完成后，作品链接为 `https://<你的用户名>.github.io/<仓库名>/`（首次部署约 1~2 分钟）。

> 新赛季到来时，记得更新 `sources/overwatch.py` 中的 `season` 常量。

---

## 补充说明

- 项目需求中「数据源用 overbuff.com」因站点关停而改用官方替代源，详见上文的「数据源说明」。
- 看板配色遵循色觉无障碍（CVD-safe）原则，采用单色顺序色阶编码数值。
