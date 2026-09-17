# KLSE AI Agent - 马股自动化虚拟交易与投研分析系统

基于 Google Gemini 大模型与 GitHub Actions 的马股（Bursa Malaysia / KLSE）自动化日频虚拟交易与投研 Agent。

---

## 🌟 核心特性

- **马股规费精密撮合**：内置 Bursa Malaysia 标准印花税、SST（8%）、经纪佣金（最低 RM 8 或 0.08%）、结算费等完整费用计算模型。
- **Gemini 大模型决策**：接入 Google GenAI SDK，结合最新市场技术指标（SMA20、5日涨跌幅、成交量）与持仓结构自主生成配置决策。
- **自包含 SQLite 账本**：完整记录现金、持仓成本（平均成本法）、交易日志流水及每日净值曲线（NAV）。
- **零服务器 Serverless 部署**：利用 GitHub Actions Cron 定时调度（工作日盘后 17:30 MYT），自动化完成决策、模拟撮合并将数据库变更推回仓库。

---

## 📁 目录结构

```text
├── .github/
│   └── workflows/
│       └── daily_trade.yml     # GitHub Actions 自动化调度工作流 (工作日 17:30 MYT)
├── main.py                     # 核心代码：费用引擎、行情抓取、SQLite账本与AI决策
├── requirements.txt            # Python 核心依赖
├── investorAgent.md            # 项目架构规范与 DevOps 文档
├── .gitignore                  # Git 忽略配置
└── README.md                   # 项目文档与快速上手指引
```

---

## 🚀 本地快速上手

### 1. 创建虚拟环境并安装依赖
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量并运行
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key"
python main.py

# Linux / macOS / Bash
export GEMINI_API_KEY="your-gemini-api-key"
python main.py
```

---

## ☁️ GitHub 部署与自动化运行

1. **推送代码至 GitHub 仓库**：
   ```bash
   git remote add origin <您的 GitHub 仓库 URL>
   git push -u origin main
   ```

2. **配置 GitHub Secrets**：
   - 打开 GitHub 仓库页面 -> **Settings** -> **Secrets and variables** -> **Actions**。
   - 点击 **New repository secret**：
     - **Name**: `GEMINI_API_KEY`
     - **Secret**: 填入您的 Google Gemini API Key。
   - *(可选)* 在 **Variables** 标签页中添加 `GEMINI_MODEL`（默认为 `gemini-2.5-flash`，亦可填 `gemini-2.0-flash`）。

3. **自动化执行机制**：
   - 工作流将在**每周一至周五 09:30 UTC（即马股收盘后 17:30 MYT）**自动触发。
   - 亦可在 GitHub 仓库的 **Actions** 页面手动点击 **Run workflow** 进行即时测试。
   - 交易结果与每日净值曲线将自动提交回写至 `klse_paper_trade.db`。
