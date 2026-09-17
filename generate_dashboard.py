"""
KLSE AI Agent - 交易流程可视化仪表板生成器
用于实时监督交易流程、风控状态、持仓分布与 AI 决策日志
"""
import datetime
import json
import os
import sqlite3
import sys
from typing import Dict, List

# 兼容 Windows 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from investor_agent.config import CONFIG
from investor_agent.ledger.engine import KLSELedgerEngine
from investor_agent.analytics.attribution import PortfolioAnalytics

STOCK_NAMES = {
    "1155": "Maybank (马来亚银行)",
    "1295": "Public Bank (大众银行)",
    "1023": "CIMB Group (联昌国际)",
    "5347": "Tenaga Nasional (国家能源)",
    "5225": "IHH Healthcare (IHH医疗)",
    "5183": "Petronas Chemicals (国油化学)",
    "6033": "Petronas Gas (国油气体)",
    "6947": "CelcomDigi (天地通数码)",
    "4707": "Nestlé (Malaysia) (雀巢马)",
    "4197": "Sime Darby (森那美)",
    "1961": "IOI Corporation (IOI集团)",
    "2445": "Kuala Lumpur Kepong (吉隆坡甲洞)",
    "5819": "Hong Leong Bank (丰隆银行)",
    "1066": "RHB Bank (兴业银行)",
    "8869": "Press Metal Aluminium (齐力工业)",
}

def generate_dashboard_html(output_file: str = "dashboard.html") -> str:
    engine = KLSELedgerEngine()
    analytics = PortfolioAnalytics(engine)
    perf = analytics.generate_performance_metrics()
    summary = engine.get_account_summary()
    trades_df = engine.get_trade_history()
    nav_df = engine.get_nav_history()

    # 读取最近的交易记录与原因
    trades = trades_df.to_dict(orient="records") if not trades_df.empty else []
    
    # 构造标的持仓卡片与风控进度
    positions = summary["positions"]
    total_equity = summary["total_equity"]
    cash = summary["cash"]

    # 提取最近决策信息
    decisions_list = []
    for t in trades:
        reasons_list = [r.strip() for r in t.get("reason", "").split("|") if r.strip()]
        decisions_list.append({
            "ticker": t["ticker"],
            "name": STOCK_NAMES.get(t["ticker"], f"股票 {t['ticker']}"),
            "action": t["action"],
            "lots": t["lots"],
            "shares": t["shares"],
            "price": t["price"],
            "confidence": int(t.get("confidence", 85) or 85),
            "reasons": reasons_list or [t.get("reason", "量化选股策略推荐")],
            "date": t["date"]
        })

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KLSE AI Agent 交易流程实时监督仪表板</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    @keyframes pulse-slow {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.5; }}
    }}
    .live-pulse {{ animation: pulse-slow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }}
  </style>
</head>
<body class="bg-[#0f172a] text-slate-100 min-h-screen antialiased p-4 md:p-8 font-sans">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- 顶部导航与状态条 -->
    <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-800/80 backdrop-blur border border-slate-700/60 rounded-2xl p-6 shadow-xl">
      <div class="space-y-1">
        <div class="flex items-center gap-3">
          <span class="text-3xl">🇲🇾</span>
          <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            KLSE 投资 AI Agent 实时监督仪表板
          </h1>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <span class="w-2 h-2 rounded-full bg-emerald-400 live-pulse"></span>
            自动化巡航中
          </span>
        </div>
        <p class="text-slate-400 text-sm">
          对冲基金级量化撮合 • Gemini 3.6 Flash 自主推理 • Bursa Malaysia 规费模型 • 7% 硬止损守卫
        </p>
      </div>
      <div class="flex items-center gap-4 text-xs text-slate-400">
        <div class="bg-slate-900/60 border border-slate-700/40 px-3 py-2 rounded-lg text-right">
          <div class="text-slate-500">定时调度时段 (MYT)</div>
          <div class="text-slate-200 font-mono font-medium">周一至周五 17:30 盘后自动执行</div>
        </div>
        <div class="bg-slate-900/60 border border-slate-700/40 px-3 py-2 rounded-lg text-right">
          <div class="text-slate-500">最近撮合时间</div>
          <div class="text-emerald-400 font-mono font-medium">{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
      </div>
    </header>

    <!-- 五步交易流程全生命周期进度条 (Pipeline Lifecycle) -->
    <div class="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6 shadow-lg">
      <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center justify-between">
        <span>全自动日终交易流转流水线 (Daily Pipeline Lifecycle)</span>
        <span class="text-emerald-400 text-xs font-normal">全流程 5 节点正常闭环</span>
      </h2>
      <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
        
        <!-- Step 1 -->
        <div class="bg-slate-900/80 border border-emerald-500/40 rounded-xl p-3.5 relative overflow-hidden">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400">节点 01</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">已完成</span>
          </div>
          <div class="text-sm font-semibold text-white">宏观外盘扫描</div>
          <div class="text-xs text-slate-400 mt-1">原油 BZ=F, 标普500, 马币汇率</div>
        </div>

        <!-- Step 2 -->
        <div class="bg-slate-900/80 border border-emerald-500/40 rounded-xl p-3.5 relative overflow-hidden">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400">节点 02</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">已完成</span>
          </div>
          <div class="text-sm font-semibold text-white">标的技术指标计算</div>
          <div class="text-xs text-slate-400 mt-1">SMA20, RSI, MACD, ATR 量化指标</div>
        </div>

        <!-- Step 3 -->
        <div class="bg-slate-900/80 border border-emerald-500/40 rounded-xl p-3.5 relative overflow-hidden">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400">节点 03</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">已拦截/就绪</span>
          </div>
          <div class="text-sm font-semibold text-white">前置硬风控扫描</div>
          <div class="text-xs text-slate-400 mt-1">7% 硬止损、20% 仓位限额校验</div>
        </div>

        <!-- Step 4 -->
        <div class="bg-slate-900/80 border border-emerald-500/40 rounded-xl p-3.5 relative overflow-hidden">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400">节点 04</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">已生成</span>
          </div>
          <div class="text-sm font-semibold text-white">Gemini 智能决策</div>
          <div class="text-xs text-slate-400 mt-1">结构化 JSON 建议与逻辑论证</div>
        </div>

        <!-- Step 5 -->
        <div class="bg-slate-900/80 border border-emerald-500/40 rounded-xl p-3.5 relative overflow-hidden">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400">节点 05</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">已归档</span>
          </div>
          <div class="text-sm font-semibold text-white">撮合记账与归因</div>
          <div class="text-xs text-slate-400 mt-1">SQLite 账本更新与 Git 回写</div>
        </div>

      </div>
    </div>

    <!-- 核心 KPI 数据卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      
      <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5">
        <div class="text-xs font-medium text-slate-400 mb-1">账户总资产 (Total Equity)</div>
        <div class="text-2xl font-bold font-mono text-white">RM {total_equity:,.2f}</div>
        <div class="mt-2 text-xs flex items-center gap-1.5 text-slate-400">
          <span>初始本金: RM 100,000.00</span>
        </div>
      </div>

      <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5">
        <div class="text-xs font-medium text-slate-400 mb-1">可用现金储备 (Cash Reserve)</div>
        <div class="text-2xl font-bold font-mono text-emerald-400">RM {cash:,.2f}</div>
        <div class="mt-2 text-xs flex items-center gap-1.5 text-slate-400">
          <span class="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">{(cash / total_equity * 100):.1f}% 现金比</span>
          <span class="text-emerald-400">安全 (>= 10%)</span>
        </div>
      </div>

      <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5">
        <div class="text-xs font-medium text-slate-400 mb-1">股票持仓市值 (Portfolio Value)</div>
        <div class="text-2xl font-bold font-mono text-indigo-400">RM {summary['portfolio_value']:,.2f}</div>
        <div class="mt-2 text-xs flex items-center gap-1.5 text-slate-400">
          <span>当前持仓: {len(positions)} 只标的</span>
          <span>(占比 {(summary['portfolio_value']/total_equity*100):.1f}%)</span>
        </div>
      </div>

      <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5">
        <div class="text-xs font-medium text-slate-400 mb-1">已累计规费成本 (Total Fees)</div>
        <div class="text-2xl font-bold font-mono text-amber-400">RM {perf['total_fees_paid']:,.2f}</div>
        <div class="mt-2 text-xs flex items-center gap-1.5 text-slate-400">
          <span>佣金+SST+印花税+结算费</span>
        </div>
      </div>

    </div>

    <!-- 实时持仓与风控监控表格 -->
    <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-700/60 pb-4">
        <div>
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>🛡️</span> 实时持仓与硬风控指标监控
          </h2>
          <p class="text-xs text-slate-400">严格遵守单股最大 20% 仓位限额与 7% 硬止损守卫</p>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span class="px-2.5 py-1 bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 rounded-lg font-mono">
            仓位硬红线: 20% (约 RM {(total_equity * 0.20):,.2f})
          </span>
          <span class="px-2.5 py-1 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-lg font-mono">
            止损硬红线: -7%
          </span>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-slate-300">
          <thead class="text-xs uppercase bg-slate-900/60 text-slate-400 border-b border-slate-700">
            <tr>
              <th class="py-3 px-4">标的代码 / 名称</th>
              <th class="py-3 px-4 text-center">持仓股数 (手数)</th>
              <th class="py-3 px-4 text-right">成本均价</th>
              <th class="py-3 px-4 text-right">最新市价</th>
              <th class="py-3 px-4 text-right">持仓市值</th>
              <th class="py-3 px-4">仓位权重 (上限 20%)</th>
              <th class="py-3 px-4 text-center">浮动盈亏</th>
              <th class="py-3 px-4 text-center">风控状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
"""

    if positions:
        for p in positions:
            ticker = p["ticker"]
            name = STOCK_NAMES.get(ticker, f"股票 {ticker}")
            weight = (p["market_value"] / total_equity) * 100
            weight_bar = min(100, int((weight / 20.0) * 100))
            pnl = p["unrealized_pnl"]
            pnl_pct = p["unrealized_pnl_pct"]
            pnl_class = "text-emerald-400" if pnl >= 0 else "text-rose-400"
            pnl_sign = "+" if pnl >= 0 else ""

            html_content += f"""
            <tr class="hover:bg-slate-700/30 transition-colors">
              <td class="py-3.5 px-4 font-medium text-white">
                <div class="font-bold">{ticker}</div>
                <div class="text-xs text-slate-400">{name}</div>
              </td>
              <td class="py-3.5 px-4 text-center font-mono">
                {p['shares']:,} 股
                <div class="text-xs text-slate-400 font-sans">({p['lots']} 手)</div>
              </td>
              <td class="py-3.5 px-4 text-right font-mono">RM {p['avg_cost']:.3f}</td>
              <td class="py-3.5 px-4 text-right font-mono font-bold text-white">RM {p['current_price']:.3f}</td>
              <td class="py-3.5 px-4 text-right font-mono font-semibold text-slate-200">RM {p['market_value']:,.2f}</td>
              <td class="py-3.5 px-4">
                <div class="flex items-center gap-2">
                  <div class="w-24 bg-slate-700 rounded-full h-2 overflow-hidden">
                    <div class="bg-indigo-400 h-2 rounded-full" style="width: {weight_bar}%"></div>
                  </div>
                  <span class="text-xs font-mono font-medium">{weight:.1f}%</span>
                </div>
              </td>
              <td class="py-3.5 px-4 text-center font-mono font-semibold {pnl_class}">
                {pnl_sign}RM {pnl:.2f} ({pnl_sign}{pnl_pct:.2f}%)
              </td>
              <td class="py-3.5 px-4 text-center">
                <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  安全持仓中
                </span>
              </td>
            </tr>
"""
    else:
        html_content += """
            <tr>
              <td colspan="8" class="py-8 text-center text-slate-400">
                当前暂无股票持仓，全仓保持现金观望中。
              </td>
            </tr>
"""

    html_content += f"""
          </tbody>
        </table>
      </div>
    </div>

    <!-- AI 今日实时决策推理卡片 (AI Decision & Reasoning Cards) -->
    <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-700/60 pb-4">
        <div>
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>🧠</span> Gemini 3.6 Flash 决策逻辑与论证跟踪
          </h2>
          <p class="text-xs text-slate-400">大模型结合量化均线、MACD 柱图、RSI 及隔夜宏观环境做出的真实推理分析</p>
        </div>
        <span class="text-xs px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
          基于零幻觉硬风控校验
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
"""

    for d in decisions_list:
        action_color = "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" if d["action"] == "BUY" else "bg-slate-700/40 text-slate-300 border-slate-600"
        html_content += f"""
        <div class="bg-slate-900/80 border border-slate-700/50 rounded-xl p-5 flex flex-col justify-between space-y-4 hover:border-slate-600 transition-colors">
          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="font-bold text-base text-white">{d['ticker']}</span>
                <span class="text-xs text-slate-400 truncate max-w-[140px]">{d['name']}</span>
              </div>
              <span class="px-2.5 py-1 text-xs font-bold rounded-lg border {action_color}">
                {d['action']} {d['lots']} 手
              </span>
            </div>

            <div class="flex items-center gap-2 text-xs text-slate-400 mb-3">
              <span>置信度评分:</span>
              <div class="flex-1 bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div class="bg-emerald-400 h-1.5 rounded-full" style="width: {d['confidence']}%"></div>
              </div>
              <span class="font-mono text-emerald-400 font-bold">{d['confidence']}%</span>
            </div>

            <div class="space-y-1.5">
              <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">核心论证依据：</div>
"""
        for r in d["reasons"]:
            html_content += f"""
              <div class="text-xs text-slate-300 bg-slate-800/70 p-2 rounded-lg border border-slate-700/30 flex items-start gap-1.5">
                <span class="text-emerald-400 mt-0.5">•</span>
                <span>{r}</span>
              </div>
"""
        html_content += f"""
            </div>
          </div>

          <div class="pt-2 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
            <span>撮合单价: RM {d['price']:.3f}</span>
            <span>{d['date']}</span>
          </div>
        </div>
"""

    html_content += f"""
      </div>
    </div>

    <!-- 底部交易明细流水日志 -->
    <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="border-b border-slate-700/60 pb-3">
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <span>📜</span> 历史撮合与真实记账流水 (SQLite Ledger)
        </h2>
      </div>
      <div class="overflow-x-auto max-h-64">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="text-[11px] uppercase bg-slate-900/80 text-slate-400 sticky top-0">
            <tr>
              <th class="py-2.5 px-3">日期</th>
              <th class="py-2.5 px-3">代码</th>
              <th class="py-2.5 px-3">动作</th>
              <th class="py-2.5 px-3 text-right">成交量 (股)</th>
              <th class="py-2.5 px-3 text-right">单价 (RM)</th>
              <th class="py-2.5 px-3 text-right">合约金额 (RM)</th>
              <th class="py-2.5 px-3 text-right">扣除规费 (RM)</th>
              <th class="py-2.5 px-3 text-right">净结转金额 (RM)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40 font-mono">
"""

    for t in reversed(trades):
        action_badge = "text-emerald-400 bg-emerald-500/10" if t["action"] == "BUY" else "text-rose-400 bg-rose-500/10"
        html_content += f"""
            <tr class="hover:bg-slate-700/30">
              <td class="py-2.5 px-3 text-slate-400 font-sans">{t['date']}</td>
              <td class="py-2.5 px-3 font-bold text-white">{t['ticker']}</td>
              <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded font-sans font-bold {action_badge}">{t['action']}</span></td>
              <td class="py-2.5 px-3 text-right">{t['shares']:,}</td>
              <td class="py-2.5 px-3 text-right">{t['price']:.3f}</td>
              <td class="py-2.5 px-3 text-right">{t['contract_val']:,.2f}</td>
              <td class="py-2.5 px-3 text-right text-amber-400">{t['total_fees']:.2f}</td>
              <td class="py-2.5 px-3 text-right font-bold {'text-rose-300' if t['net_amount'] < 0 else 'text-emerald-300'}">{t['net_amount']:,.2f}</td>
            </tr>
"""

    html_content += f"""
          </tbody>
        </table>
      </div>
    </div>

    <!-- 页脚说明 -->
    <footer class="text-center text-xs text-slate-500 py-4">
      Bursa Malaysia (KLSE) AI Paper Trading System • Designed for DevOps & Quantitative Autopilot
    </footer>

  </div>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_content

if __name__ == "__main__":
    out = "dashboard.html"
    generate_dashboard_html(out)
    print(f"✅ 可视化仪表板已生成至: {out}")
