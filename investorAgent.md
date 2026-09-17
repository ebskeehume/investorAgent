# 马来西亚股票市场（KLSE）虚拟投资 AI Agent 架构规范

本项目为专注于马来西亚吉隆坡证券交易所（Bursa Malaysia / KLSE）的虚拟投资 AI Agent，整体架构解耦为**数据获取、分析决策、模拟记账、复盘归因**四个核心模块。

---

### 一、 系统整体架构与技术选型

| 模块 | 功能 | 推荐工具 / 数据源 |
| --- | --- | --- |
| **Orchestrator** | 协调工作流与定时调度 | GitHub Actions / 本地 Python 调度器 (`main.py`) |
| **LLM Core** | 行业与基本面分析、决策生成 | Google Gemini（默认支持 `gemini-flash-lite-latest` / `gemini-3.6-flash`，带 503 指数退避重试与模型自愈探测） |
| **KLSE 数据源** | 股价、成交量、大宗商品、宏观基准 | Yahoo Finance (`.KL` 后缀，如 `1155.KL`，原油 `BZ=F`，基准 `^KLSE`) |
| **Ledger 账本** | 现金与持仓状态、真实规费撮合 | SQLite + Pandas 计算每日资产净值 (NAV) |
| **Analytics 归因** | 绩效评估、超额收益 (Alpha)、夏普比率、最大回撤 | Python NumPy/Pandas 归因计算器 (`investor_agent.analytics`) |

---

### 二、 投资准则与风控配置字典 (`investor_agent/config.py`)

```python
CONFIG = {
    "initial_capital_myr": 100000.00,  # 初始虚拟本金 RM 100,000
    "max_position_weight": 0.20,       # 单股最大权重 20% (RM 20,000)
    "min_cash_reserve": 0.10,          # 永远保留 10% 现金应对波动
    "lot_size": 100,                   # 马股强制 100 股整数倍
    "stop_loss_pct": 0.07,             # 7% 硬止损
    "take_profit_pct": 0.15,           # 15% 目标止盈
    "brokerage_rate": 0.0008,          # 佣金 0.08% (最低 RM 8.00)
    "sst_rate": 0.08,                  # 佣金服务税 8% SST
    "clearing_fee_rate": 0.0003,       # 结算费 0.03% (上限 RM 1000.00)
    "stamp_duty_unit": 1.50,           # 每 RM 1,000 计 RM 1.50 印花税 (上限 RM 1000.00)
}
```

---

### 三、 模块设计与职责

#### 1. 模块 A：数据获取 (`investor_agent/data/`)
- `market.py`: 抓取 KLSE 核心成分股日 K 线，计算 20日均线、RSI(14)、MACD(12,26,9)、ATR(14)。
- `macro.py`: 抓取布伦特原油、美股标普500、美元兑马币汇率及大马综指。

#### 2. 模块 B：分析决策 (`investor_agent/agent/`)
- `prompts.py`: 设定大马资深对冲基金经理 Persona，注入账户状态、宏观快照与技术面指标，输出严格 JSON 决策数组。
- `decision.py`: 自动处理大模型调用，具备 503 拥塞重试与动态 API 模型探测。

#### 3. 模块 C：模拟记账与硬风控 (`investor_agent/ledger/`)
- `fees.py`: 精准计算马股经纪佣金、SST、结算费和印花税。
- `engine.py`: 管理 SQLite 账本，并在撮合前强制执行 100 股手数、20% 仓位限额、10% 现金底仓拦截，以及 7% 强制止损执行。

#### 4. 模块 D：复盘与归因 (`investor_agent/analytics/`)
- `attribution.py`: 自动计算相对 `^KLSE` 基准超额收益 (Alpha)、年化夏普比率、最大回撤及最大亏损交易反思。
- `generate_report.py`: 随时生成高规格 Markdown 绩效复盘报告。

---

### 四、 GitHub Actions 调度工作流

文件位置：`.github/workflows/daily_trade.yml`
- **运行时间**：每周一至周五 17:30 MYT（09:30 UTC）
- **持久化**：自动将更新后的 SQLite 数据库与量化报告 `performance_report.md` 自动提回仓库。