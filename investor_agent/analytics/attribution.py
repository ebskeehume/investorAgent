"""
投资绩效评估与归因分析引擎 (Performance & Attribution)
包含 Alpha 超额收益、夏普比率、最大回撤计算以及交易失误归因
"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from investor_agent.config import CONFIG
from investor_agent.ledger.engine import KLSELedgerEngine

class PortfolioAnalytics:
    def __init__(self, engine: Optional[KLSELedgerEngine] = None):
        self.engine = engine or KLSELedgerEngine()

    def generate_performance_metrics(self) -> Dict:
        """
        计算完整的投资组合风险调整收益与基准对比指标
        """
        nav_df = self.engine.get_nav_history()
        trades_df = self.engine.get_trade_history()
        summary = self.engine.get_account_summary()

        if nav_df.empty:
            return {
                "total_days": 0,
                "cumulative_return_pct": 0.0,
                "benchmark_cumulative_return_pct": 0.0,
                "alpha_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "annualized_volatility_pct": 0.0,
                "total_trades": len(trades_df),
                "total_fees_paid": trades_df["total_fees"].sum() if not trades_df.empty else 0.0,
                "top_losses": [],
            }

        # 1. 累计收益率
        initial_equity = float(nav_df["total_equity"].iloc[0])
        current_equity = float(nav_df["total_equity"].iloc[-1])
        cumulative_return = ((current_equity - initial_equity) / initial_equity) * 100

        # 2. 基准收益率 (^KLSE)
        benchmark_cum_return = 0.0
        if "benchmark_price" in nav_df.columns and not nav_df["benchmark_price"].dropna().empty:
            valid_bench = nav_df["benchmark_price"].dropna()
            if len(valid_bench) >= 2:
                b_init = valid_bench.iloc[0]
                b_last = valid_bench.iloc[-1]
                benchmark_cum_return = ((b_last - b_init) / b_init) * 100

        alpha = cumulative_return - benchmark_cum_return

        # 3. 最大回撤 (Max Drawdown)
        equity_series = nav_df["total_equity"]
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        max_drawdown = float(drawdown.min()) * 100 if not drawdown.empty else 0.0

        # 4. 年化波动率与夏普比率 (无风险利率设定为马来西亚隔夜政策利率 OPR = 3.0%)
        risk_free_rate = 0.03
        daily_returns = nav_df["daily_return_pct"] / 100.0
        n_days = len(nav_df)

        if n_days > 1 and daily_returns.std() > 0:
            annualized_vol = float(daily_returns.std() * np.sqrt(252)) * 100
            # 年化收益
            annualized_ret = float(((1 + cumulative_return / 100.0) ** (252 / max(1, n_days)) - 1)) * 100
            sharpe = (annualized_ret / 100.0 - risk_free_rate) / (annualized_vol / 100.0) if annualized_vol > 0 else 0.0
        else:
            annualized_vol = 0.0
            annualized_ret = cumulative_return
            sharpe = 0.0

        # 5. 交易统计与失误归因 (寻找亏损最大的 3 笔平仓)
        total_trades = len(trades_df)
        total_fees = float(trades_df["total_fees"].sum()) if not trades_df.empty else 0.0
        
        top_losses = []
        if not trades_df.empty:
            sell_trades = trades_df[trades_df["action"] == "SELL"].copy()
            if not sell_trades.empty:
                # 简单计算每笔卖单相比历史均价或规费的净亏损
                # 按净收益升序排序
                loss_candidates = sell_trades.sort_values(by="net_amount", ascending=True).head(3)
                for _, t in loss_candidates.iterrows():
                    top_losses.append({
                        "date": t["date"],
                        "ticker": t["ticker"],
                        "shares": t["shares"],
                        "price": t["price"],
                        "fees": t["total_fees"],
                        "net_amount": t["net_amount"],
                        "reason": t["reason"],
                    })

        return {
            "total_days": n_days,
            "total_equity": current_equity,
            "cash": summary["cash"],
            "portfolio_value": summary["portfolio_value"],
            "cumulative_return_pct": round(cumulative_return, 2),
            "benchmark_cumulative_return_pct": round(benchmark_cum_return, 2),
            "alpha_pct": round(alpha, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "annualized_volatility_pct": round(annualized_vol, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": total_trades,
            "total_fees_paid": round(total_fees, 2),
            "top_losses": top_losses,
        }

    def generate_markdown_report(self) -> str:
        """生成格式优美的量化归因与复盘总结 Markdown 报告"""
        metrics = self.generate_performance_metrics()
        nav_df = self.engine.get_nav_history()
        summary = self.engine.get_account_summary()

        report = f"""# 🇲🇾 KLSE 投资 AI Agent 运行与量化归因报告

- **报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
- **累计运行天数**: {metrics['total_days']} 天
- **基准标的**: 富时隆综指 (^KLSE)
- **无风险利率基准**: 3.0% (Bank Negara Malaysia OPR)

---

## 📊 一、 核心绩效与风险调整指标

| 指标维度 | Agent 实际表现 | 基准 (^KLSE) | 超额收益 (Alpha) / 评价 |
| :--- | :---: | :---: | :---: |
| **资产总值 (Total Equity)** | RM {metrics['total_equity']:,.2f} | - | 本金 RM 100,000.00 |
| **累计回报率 (Cumulative Return)** | **{metrics['cumulative_return_pct']}%** | {metrics['benchmark_cumulative_return_pct']}% | **{'+' if metrics['alpha_pct'] >= 0 else ''}{metrics['alpha_pct']}%** |
| **最大回撤 (Max Drawdown)** | **{metrics['max_drawdown_pct']}%** | - | 风控阈值: 7% 硬止损 |
| **年化夏普比率 (Sharpe Ratio)** | **{metrics['sharpe_ratio']}** | - | 风险补偿能力评价 |
| **年化波动率 (Volatility)** | {metrics['annualized_volatility_pct']}% | - | 稳健型投资组合 |
| **总计摩擦成本 (Trading Fees)** | RM {metrics['total_fees_paid']:.2f} | - | 包含佣金、SST、印花税及清算费 |

---

## 💼 二、 当前持仓与资产分布

- **可用现金**: RM {metrics['cash']:,.2f} (占比: {metrics['cash']/max(1, metrics['total_equity'])*100:.1f}%)
- **股票持仓市值**: RM {metrics['portfolio_value']:,.2f} (占比: {metrics['portfolio_value']/max(1, metrics['total_equity'])*100:.1f}%)

"""
        positions = summary["positions"]
        if positions:
            report += "| 股票代码 | 持仓股数 | 手数(Lots) | 成本均价 (RM) | 最新市价 (RM) | 持仓市值 (RM) | 浮动盈亏 (RM) | 浮动盈亏率 |\n"
            report += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
            for p in positions:
                pnl_color = "+" if p["unrealized_pnl"] >= 0 else ""
                report += f"| **{p['ticker']}** | {p['shares']:,} | {p['lots']} | {p['avg_cost']:.3f} | {p['current_price']:.3f} | {p['market_value']:,.2f} | {pnl_color}{p['unrealized_pnl']:.2f} | {pnl_color}{p['unrealized_pnl_pct']:.2f}% |\n"
        else:
            report += "> *当前无隔夜持仓，全仓保持现金观望状态。*\n"

        report += "\n---\n\n## 🔍 三、 决策失误与反思归因 (Top Losses Reflection)\n\n"
        if metrics["top_losses"]:
            report += "针对回撤最大的平仓交易，提取当时的决策依据并形成经验防范闭环：\n\n"
            for i, loss in enumerate(metrics["top_losses"], 1):
                report += f"### {i}. 标的 `{loss['ticker']}` 平仓复盘\n"
                report += f"- **交易日期**: {loss['date']} | **成交股数**: {loss['shares']} 股 | **价格**: RM {loss['price']}\n"
                report += f"- **总手续费**: RM {loss['fees']:.2f} | **净结转资金**: RM {loss['net_amount']:,.2f}\n"
                report += f"- **平仓原因与反思**: *{loss['reason']}*\n\n"
        else:
            report += "> *目前暂无实质性平仓亏损记录，风控纪律执行良好。*\n"

        return report
