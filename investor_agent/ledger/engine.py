"""
KLSE 模拟账本与撮合执行引擎（含代码级硬性风控守卫）
"""
import datetime
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple
import pandas as pd
from investor_agent.config import CONFIG
from investor_agent.ledger.fees import KLSEFeeCalculator

class KLSELedgerEngine:
    def __init__(self, db_path: Optional[str] = None, initial_capital: Optional[float] = None):
        self.db_path = db_path or CONFIG["db_path"]
        self.initial_capital = initial_capital or CONFIG["initial_capital_myr"]
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash REAL NOT NULL,
                    initial_capital REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    ticker TEXT PRIMARY KEY,
                    shares INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    lots INTEGER NOT NULL,
                    shares INTEGER NOT NULL,
                    price REAL NOT NULL,
                    contract_val REAL NOT NULL,
                    total_fees REAL NOT NULL,
                    net_amount REAL NOT NULL,
                    confidence REAL,
                    reason TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nav_history (
                    date TEXT PRIMARY KEY,
                    cash REAL NOT NULL,
                    portfolio_value REAL NOT NULL,
                    total_equity REAL NOT NULL,
                    daily_return_pct REAL NOT NULL,
                    benchmark_price REAL,
                    benchmark_return_pct REAL
                )
            """)
            cur.execute("SELECT COUNT(*) FROM account")
            if cur.fetchone()[0] == 0:
                now = datetime.datetime.now().isoformat()
                cur.execute(
                    "INSERT INTO account VALUES (1, ?, ?, ?)",
                    (self.initial_capital, self.initial_capital, now)
                )
            conn.commit()

    def get_account_summary(self, price_map: Optional[Dict[str, float]] = None) -> Dict:
        """获取账户最新净值、现金及持仓详情"""
        price_map = price_map or {}
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT cash, initial_capital FROM account WHERE id = 1")
            cash, initial = cur.fetchone()
            positions_df = pd.read_sql_query("SELECT * FROM positions", conn)
            
            positions = []
            portfolio_val = 0.0
            for _, row in positions_df.iterrows():
                ticker = row["ticker"]
                shares = int(row["shares"])
                avg_cost = float(row["avg_cost"])
                current_price = price_map.get(ticker, avg_cost)
                market_val = shares * current_price
                unrealized_pnl = (current_price - avg_cost) * shares
                unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
                portfolio_val += market_val
                
                positions.append({
                    "ticker": ticker,
                    "shares": shares,
                    "lots": shares // CONFIG["lot_size"],
                    "avg_cost": round(avg_cost, 4),
                    "current_price": round(current_price, 3),
                    "market_value": round(market_val, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                    "updated_at": row["updated_at"]
                })
            
            total_equity = cash + portfolio_val
            return {
                "cash": round(cash, 2),
                "portfolio_value": round(portfolio_val, 2),
                "total_equity": round(total_equity, 2),
                "initial_capital": round(initial, 2),
                "positions": positions,
            }

    def execute_order(
        self,
        ticker: str,
        action: str,
        lots: int,
        price: float,
        reason: str = "",
        confidence: float = 0.0
    ) -> Dict:
        """
        带代码级硬性风控守卫的订单撮合执行引擎
        风控规则：
        1. 必须为 100 股整数倍 (1 Lot = 100 股)
        2. 买入后单只标的总市值不得超过总资产的 20%
        3. 买入后剩余现金不得低于总资产的 10%
        """
        action = action.upper()
        if action not in ["BUY", "SELL"]:
            return {"success": False, "msg": f"无效动作: {action}"}
        if lots <= 0 or price <= 0:
            return {"success": False, "msg": f"无效交易参数: lots={lots}, price={price}"}
        
        shares = lots * CONFIG["lot_size"]
        contract_val = shares * price
        fees = KLSEFeeCalculator.calculate_fees(contract_val)
        now_str = datetime.date.today().isoformat()

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT cash FROM account WHERE id = 1")
            cash = cur.fetchone()[0]
            
            # 实时计算当前总资产
            positions_df = pd.read_sql_query("SELECT * FROM positions", conn)
            current_portfolio_val = sum(r["shares"] * r["avg_cost"] for _, r in positions_df.iterrows())
            total_equity = cash + current_portfolio_val

            if action == "BUY":
                total_required = contract_val + fees["total_fee"]
                
                # --- 硬风控 1: 可用资金检查 ---
                if cash < total_required:
                    return {
                        "success": False,
                        "msg": f"【风控拦截】可用现金不足！需 RM {total_required:.2f}，当前仅有 RM {cash:.2f}"
                    }

                # --- 硬风控 2: 现金储备底线 (10%) 检查 ---
                remaining_cash = cash - total_required
                min_cash_required = total_equity * CONFIG["min_cash_reserve"]
                if remaining_cash < min_cash_required:
                    return {
                        "success": False,
                        "msg": f"【风控拦截】买入后现金 RM {remaining_cash:.2f} 低于 10% 底线 (需保留 RM {min_cash_required:.2f})"
                    }

                # --- 硬风控 3: 单股持仓限额 (20%) 检查 ---
                cur.execute("SELECT shares, avg_cost FROM positions WHERE ticker = ?", (ticker,))
                row = cur.fetchone()
                existing_shares = row[0] if row else 0
                new_shares = existing_shares + shares
                new_stock_val = new_shares * price
                max_stock_allowed = total_equity * CONFIG["max_position_weight"]
                if new_stock_val > max_stock_allowed:
                    return {
                        "success": False,
                        "msg": f"【风控拦截】买入后标的 {ticker} 仓位 RM {new_stock_val:.2f} 超过总资产 20% 限额 (上限 RM {max_stock_allowed:.2f})"
                    }

                # 执行买入扣款与持仓更新 (平均成本法)
                new_cash = cash - total_required
                cur.execute("UPDATE account SET cash = ?, updated_at = ? WHERE id = 1", (new_cash, now_str))
                
                if row:
                    new_cost = ((existing_shares * row[1]) + total_required) / new_shares
                    cur.execute(
                        "UPDATE positions SET shares = ?, avg_cost = ?, updated_at = ? WHERE ticker = ?",
                        (new_shares, new_cost, now_str, ticker)
                    )
                else:
                    cur.execute(
                        "INSERT INTO positions VALUES (?, ?, ?, ?)",
                        (ticker, shares, total_required / shares, now_str)
                    )
                net_amount = -total_required

            elif action == "SELL":
                cur.execute("SELECT shares, avg_cost FROM positions WHERE ticker = ?", (ticker,))
                row = cur.fetchone()
                if not row or row[0] < shares:
                    return {
                        "success": False,
                        "msg": f"【风控拦截】持仓不足无法卖出！当前持仓 {row[0] if row else 0} 股，拟卖出 {shares} 股"
                    }
                
                proceeds = contract_val - fees["total_fee"]
                new_cash = cash + proceeds
                cur.execute("UPDATE account SET cash = ?, updated_at = ? WHERE id = 1", (new_cash, now_str))
                
                remaining = row[0] - shares
                if remaining == 0:
                    cur.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
                else:
                    cur.execute(
                        "UPDATE positions SET shares = ?, updated_at = ? WHERE ticker = ?",
                        (remaining, now_str, ticker)
                    )
                net_amount = proceeds

            cur.execute("""
                INSERT INTO trades (date, ticker, action, lots, shares, price, contract_val, total_fees, net_amount, confidence, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_str, ticker, action, lots, shares, price, contract_val, fees["total_fee"], net_amount, confidence, reason))
            conn.commit()

        return {
            "success": True,
            "ticker": ticker,
            "action": action,
            "lots": lots,
            "shares": shares,
            "price": price,
            "contract_val": round(contract_val, 2),
            "fees": fees["total_fee"],
            "net_amount": round(net_amount, 2),
        }

    def scan_and_enforce_stop_loss_take_profit(self, price_map: Dict[str, float]) -> List[Dict]:
        """
        开盘/撮合前全局扫描持仓，自动触发硬性止损 (7%) 与止盈 (15%)
        """
        triggered_orders = []
        with self._get_conn() as conn:
            positions_df = pd.read_sql_query("SELECT * FROM positions", conn)
        
        for _, row in positions_df.iterrows():
            ticker = row["ticker"]
            shares = int(row["shares"])
            avg_cost = float(row["avg_cost"])
            current_price = price_map.get(ticker)
            
            if not current_price or avg_cost <= 0 or shares <= 0:
                continue
            
            pnl_pct = (current_price - avg_cost) / avg_cost
            lots = shares // CONFIG["lot_size"]
            
            # 1. 触发 7% 硬止损
            if pnl_pct <= -CONFIG["stop_loss_pct"]:
                reason = f"【硬风控触发】标的 {ticker} 跌幅达 {pnl_pct*100:.2f}%，触发 7% 硬止损纪律，强制平仓"
                res = self.execute_order(ticker, "SELL", lots, current_price, reason=reason, confidence=100.0)
                triggered_orders.append(res)
            
            # 2. 触发 15% 目标止盈
            elif pnl_pct >= CONFIG["take_profit_pct"]:
                reason = f"【止盈触发】标的 {ticker} 盈利达 {pnl_pct*100:.2f}%，达到 15% 目标止盈位，自动落袋为安"
                res = self.execute_order(ticker, "SELL", lots, current_price, reason=reason, confidence=90.0)
                triggered_orders.append(res)

        return triggered_orders

    def record_daily_snapshot(
        self,
        price_map: Dict[str, float],
        benchmark_price: Optional[float] = None,
        date_str: Optional[str] = None
    ) -> Dict:
        """记录每日资产净值 (NAV) 与基准回报快照"""
        now_str = date_str or datetime.date.today().isoformat()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT cash FROM account WHERE id = 1")
            cash = cur.fetchone()[0]
            positions = pd.read_sql_query("SELECT * FROM positions", conn)
            portfolio_val = sum(
                row["shares"] * price_map.get(row["ticker"], row["avg_cost"])
                for _, row in positions.iterrows()
            ) if not positions.empty else 0.0
            total_equity = cash + portfolio_val

            cur.execute("SELECT total_equity, benchmark_price FROM nav_history ORDER BY date DESC LIMIT 1")
            prev = cur.fetchone()
            prev_equity = prev[0] if prev else self.initial_capital
            prev_benchmark = prev[1] if (prev and prev[1]) else benchmark_price
            
            daily_return = (((total_equity - prev_equity) / prev_equity) * 100) if prev_equity > 0 else 0.0
            benchmark_return = 0.0
            if benchmark_price and prev_benchmark and prev_benchmark > 0:
                benchmark_return = ((benchmark_price - prev_benchmark) / prev_benchmark) * 100

            cur.execute("""
                INSERT OR REPLACE INTO nav_history (
                    date, cash, portfolio_value, total_equity, daily_return_pct, benchmark_price, benchmark_return_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                now_str,
                round(cash, 2),
                round(portfolio_val, 2),
                round(total_equity, 2),
                round(daily_return, 4),
                benchmark_price,
                round(benchmark_return, 4) if benchmark_price else None
            ))
            conn.commit()
            return {
                "date": now_str,
                "total_equity": round(total_equity, 2),
                "cash": round(cash, 2),
                "portfolio_value": round(portfolio_val, 2),
                "daily_return_pct": round(daily_return, 2),
                "benchmark_return_pct": round(benchmark_return, 2) if benchmark_price else 0.0,
            }

    def get_trade_history(self) -> pd.DataFrame:
        with self._get_conn() as conn:
            return pd.read_sql_query("SELECT * FROM trades ORDER BY id ASC", conn)

    def get_nav_history(self) -> pd.DataFrame:
        with self._get_conn() as conn:
            return pd.read_sql_query("SELECT * FROM nav_history ORDER BY date ASC", conn)
