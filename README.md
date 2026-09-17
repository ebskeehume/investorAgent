# 🇲🇾 KLSE AI Agent - 马来西亚股票市场自动化虚拟投资系统

基于 Google Gemini 大模型与 GitHub Actions 的马股（Bursa Malaysia / KLSE）自动化日频虚拟交易、智能投研与量化归因系统。

---

## 🌟 核心架构与四大模块

系统严格解耦为工业级四大核心模块：

```text
investor_agent/
├── config.py                 # 全局配置：本金、标的池、20%仓位/10%现金/7%止损硬风控参数
├── data/
│   ├── market.py             # 数据获取：KLSE 标的池日 K 线与技术指标 (SMA20, RSI, MACD, ATR)
│   └── macro.py              # 宏观监测：布伦特原油 (BZ=F)、美股标普500、大马综指 (^KLSE)
├── ledger/
│   ├── fees.py               # 规费模型：Bursa Malaysia 真实印花税、SST (8%)、佣金与清算费
│   └── engine.py             # 模拟账本：SQLite 持久化 + 代码层硬性风控守卫 (7%止损 / 20%仓位拦截)
├── agent/
│   ├── prompts.py            # 分析决策：大马对冲基金分析师 Persona 与严格 JSON 结构化输出
│   └── decision.py           # LLM 核心：Gemini 模型调度、503 拥塞重试与动态自愈模型探测
└── analytics/
    └── attribution.py        # 复盘归因：Alpha 超额收益、夏普比率、最大回撤与交易失误反思
```

---

## 🛡️ 严格风控底线（Hard Guardrails）

代码撮合引擎内置前置硬性拦截器，彻底杜绝大模型幻觉与乱买微型仙股：
- **投资标的池**：聚焦富时隆综指核心成分股（FBMKLCI 30），自动过滤无流动性股票。
- **交易手数规范**：马股强制 `1 Lot = 100 股` 整数倍。
- **单股持仓限额**：单只股票市值严禁超过总资产的 **20%**。
- **强制现金底仓**：账户必须永久保留不少于 **10%** 的现金抵御系统性波动。
- **7% 硬止损纪律**：开盘前自动对全持仓进行止损扫描，亏损达 **7%** 强制自动平仓。
- **15% 目标止盈**：达到目标盈利位提示或落袋为安。

---

## 📈 自动化日常流程（Daily Pipeline）

1. **宏观与外盘扫描**：拉取布伦特原油、美股标普500及马币汇率走势。
2. **标的量化指标计算**：下载候选成分股近 3 个月日 K 线，计算 20日均线、RSI、MACD 柱图及真实波幅 ATR。
3. **开盘硬风控扫描**：遍历持仓，一旦触发 7% 止损直接市价平仓。
4. **AI 决策与风控校验**：Gemini 生成交易建议，经 20% 仓位与 10% 现金硬风控校验后执行撮合。
5. **盘后结算与净值归档**：按当日收盘价清算 NAV，记录基准对比数据。
6. **自动生成量化归因报告**：生成并自动更新 `performance_report.md`。

---

## 🚀 本地运行与自检

### 1. 运行核心交易主流程
```bash
# Windows
.venv\Scripts\python.exe main.py

# Linux / macOS
python3 main.py
```

### 2. 生成量化复盘报告
```bash
python generate_report.py
```

### 3. 执行单元测试
```bash
python -m unittest discover tests
```

---

## ☁️ GitHub Actions 自动化部署

工作流配置在 [`.github/workflows/daily_trade.yml`](.github/workflows/daily_trade.yml)：
- **定时触发**：每周一至周五马股收盘后（**17:30 MYT / 09:30 UTC**）全自动运行。
- **状态持久化**：每次运行后自动将更新的数据库 `klse_paper_trade.db` 与最新报告 `performance_report.md` 推回仓库。
- **环境变量配置**：
  在仓库 **Settings -> Secrets and variables -> Actions** 中配置 `GEMINI_API_KEY`。
