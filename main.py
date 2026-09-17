"""
KLSE AI Agent - 马来西亚股票市场自动化虚拟投资主流程
包含四层闭环：数据获取 -> 分析决策 -> 模拟记账 -> 复盘归因
"""
import datetime
import os
import sys
from typing import Dict

# 兼容 Windows 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from investor_agent.config import CONFIG
from investor_agent.data.market import KLSEMarketData
from investor_agent.data.macro import MacroEnvironment
from investor_agent.ledger.engine import KLSELedgerEngine
from investor_agent.agent.decision import TradingAgent
from investor_agent.analytics.attribution import PortfolioAnalytics

def run_daily_pipeline():
    print("=" * 60)
    print(f"🚀 启动 KLSE AI Agent 每日交易与投研工作流 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("=" * 60)

    # 1. 初始化模拟账本引擎
    engine = KLSELedgerEngine()
    
    # 2. 宏观环境扫描
    print("\n[Step 1/5] 正在拉取宏观与大宗商品市场快照...")
    macro_data = MacroEnvironment.get_macro_snapshot()
    for k, v in macro_data.items():
        print(f"  - {k} ({v['ticker']}): RM {v['price']} (1D: {v['change_1d_pct']}%)")

    # 3. 股票池行情与技术指标获取
    print("\n[Step 2/5] 正在批量获取马股标的池行情与技术指标 (SMA20, RSI, MACD, ATR)...")
    market_data = KLSEMarketData.get_batch_market_data(CONFIG["watchlist"])
    if not market_data:
        print("⚠️ 今日未能获取有效马股行情数据（可能为公假、休市或数据源异常），跳过交易。")
        return

    price_map = {k: v["price"] for k, v in market_data.items()}
    print(f"  已成功获取 {len(market_data)} 只成分股行情指标。")

    # 4. 硬风控防线：扫描全持仓执行 7% 硬止损与 15% 止盈
    print("\n[Step 3/5] 执行前置硬风控扫描（7% 硬止损 / 15% 目标止盈）...")
    triggered_orders = engine.scan_and_enforce_stop_loss_take_profit(price_map)
    if triggered_orders:
        for order in triggered_orders:
            print(f"  🚨 风控触发订单: {order}")
    else:
        print("  ✅ 全持仓风控指标正常，无标的触发硬止损。")

    # 5. 调用 LLM Core 生成结构化决策
    print("\n[Step 4/5] 正在调用 Gemini 生成今日投资决策...")
    account_info = engine.get_account_summary(price_map)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 未配置 GEMINI_API_KEY 环境变量！请在环境变量或 GitHub Secrets 中配置。")
        sys.exit(1)

    agent = TradingAgent(api_key=api_key)
    decisions = agent.generate_decisions(account_info, market_data, macro_data)
    
    print("\n--- AI 今日决策建议列表 ---")
    for d in decisions:
        ticker = d.get("ticker")
        action = d.get("action")
        lots = d.get("lots", 0)
        confidence = d.get("confidence", 0)
        reasons = d.get("reasons", [])
        print(f"  [{ticker}] 建议: {action} | 手数: {lots} | 置信度: {confidence}%")
        for r in reasons:
            print(f"     * {r}")

        # 模拟撮合成交（含 20% 仓位与 10% 现金硬风控校验）
        if action in ["BUY", "SELL"] and lots > 0 and ticker in market_data:
            price = market_data[ticker]["price"]
            combined_reason = " | ".join(reasons)
            res = engine.execute_order(
                ticker=ticker,
                action=action,
                lots=lots,
                price=price,
                reason=combined_reason,
                confidence=float(confidence)
            )
            print(f"     => 撮合结果: {res}")

    # 6. 盘后结算与 NAV 快照记录
    print("\n[Step 5/5] 盘后清算与资产净值 (NAV) 快照归档...")
    benchmark_price = macro_data.get("klci_index", {}).get("price")
    snapshot = engine.record_daily_snapshot(price_map, benchmark_price=benchmark_price)
    print(f"  清算成功: 总资产 RM {snapshot['total_equity']:,.2f} | 现金 RM {snapshot['cash']:,.2f} | 今日回报 {snapshot['daily_return_pct']}%")

    # 7. 打印快速绩效简报
    analytics = PortfolioAnalytics(engine)
    perf = analytics.generate_performance_metrics()
    print(f"  📈 累计超额回报 (Alpha): {perf['alpha_pct']}% | 最大回撤: {perf['max_drawdown_pct']}% | 夏普比率: {perf['sharpe_ratio']}")
    print("\n✅ 今日自动化投资流程全部执行完毕！")

if __name__ == "__main__":
    run_daily_pipeline()
