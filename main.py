import datetime
import json
import math
import os
import sqlite3
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf

# 1. KLSE 费用计算器
class KLSEFeeCalculator:
  @staticmethod
  def calculate_fees(contract_value: float) -> Dict[str, float]:
    if contract_value <= 0:
      return {
          "brokerage": 0.0,
          "sst": 0.0,
          "clearing_fee": 0.0,
          "stamp_duty": 0.0,
          "total_fee": 0.0,
      }
    # 最低 RM 8.00 或 0.08%
    brokerage = max(8.00, contract_value * 0.0008)
    # 经纪佣金服务税 8% SST
    sst = brokerage * 0.08
    # 结算费 0.03%（最高 RM 1000.00）
    clearing_fee = min(1000.00, contract_value * 0.0003)
    # 印花税：每 RM 1000 计 RM 1.50（最高 RM 1000.00）
    stamp_duty = min(1000.00, math.ceil(contract_value / 1000.00) * 1.50)
    total_fee = brokerage + sst + clearing_fee + stamp_duty
    return {
        "brokerage": round(brokerage, 2),
        "sst": round(sst, 2),
        "clearing_fee": round(clearing_fee, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_fee": round(total_fee, 2),
    }

# 2. 行情抓取
class KLSEMarketData:
  @staticmethod
  def format_ticker(code: str) -> str:
    code = code.strip().upper()
    return code if code.endswith(".KL") else f"{code}.KL"

  @classmethod
  def get_batch_market_data(cls, codes: List[str]) -> Dict[str, Dict]:
    if not codes:
      return {}
    formatted = [cls.format_ticker(c) for c in codes]
    try:
      data = yf.download(formatted, period="1mo", interval="1d", group_by="ticker", progress=False)
    except Exception as e:
      print(f"行情下载异常: {e}")
      return {}

    results = {}
    is_multi = isinstance(data.columns, pd.MultiIndex)

    for code in codes:
      t = cls.format_ticker(code)
      try:
        if is_multi:
          if t not in data.columns.levels[0]:
            continue
          sub_df = data[t].dropna(subset=["Close"])
        else:
          sub_df = data.dropna(subset=["Close"])

        if len(sub_df) < 5:
          continue

        close_series = sub_df["Close"]
        latest_close = float(close_series.iloc[-1])
        sma20 = float(close_series.rolling(20).mean().iloc[-1]) if len(close_series) >= 20 else latest_close
        change_5d = float((latest_close - close_series.iloc[-5]) / close_series.iloc[-5]) * 100
        vol = sub_df["Volume"].iloc[-1] if "Volume" in sub_df.columns else 0
        volume = int(vol) if not pd.isna(vol) else 0

        results[code] = {
            "price": round(latest_close, 3),
            "sma20": round(sma20, 3),
            "change_5d_pct": round(change_5d, 2),
            "volume": volume,
        }
      except Exception as e:
        print(f"处理股票 {code} 行情异常: {e}")
        continue
    return results

# 3. 模拟账本
class KLSELedgerEngine:
  def __init__(self, db_path: str = "klse_paper_trade.db", initial_capital: float = 100000.00):
    self.db_path = db_path
    self.initial_capital = initial_capital
    self._init_db()

  def _get_conn(self) -> sqlite3.Connection:
    return sqlite3.connect(self.db_path)

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
            reason TEXT
        )
      """)
      cur.execute("""
        CREATE TABLE IF NOT EXISTS nav_history (
            date TEXT PRIMARY KEY,
            cash REAL NOT NULL,
            portfolio_value REAL NOT NULL,
            total_equity REAL NOT NULL,
            daily_return_pct REAL NOT NULL
        )
      """)
      cur.execute("SELECT COUNT(*) FROM account")
      if cur.fetchone()[0] == 0:
        now = datetime.datetime.now().isoformat()
        cur.execute("INSERT INTO account VALUES (1, ?, ?, ?)", (self.initial_capital, self.initial_capital, now))
      conn.commit()

  def get_account_summary(self) -> Dict:
    with self._get_conn() as conn:
      cur = conn.cursor()
      cur.execute("SELECT cash, initial_capital FROM account WHERE id = 1")
      cash, initial = cur.fetchone()
      positions = pd.read_sql_query("SELECT * FROM positions", conn)
      return {
          "cash": cash,
          "initial_capital": initial,
          "positions": positions.to_dict(orient="records"),
      }

  def execute_order(self, ticker: str, action: str, lots: int, price: float, reason: str = "") -> Dict:
    action = action.upper()
    if action not in ["BUY", "SELL"] or lots <= 0 or price <= 0:
      return {"success": False, "msg": "无效参数"}
    shares = lots * 100
    contract_val = shares * price
    fees = KLSEFeeCalculator.calculate_fees(contract_val)
    now_str = datetime.date.today().isoformat()

    with self._get_conn() as conn:
      cur = conn.cursor()
      cur.execute("SELECT cash FROM account WHERE id = 1")
      cash = cur.fetchone()[0]

      if action == "BUY":
        total_required = contract_val + fees["total_fee"]
        if cash < total_required:
          return {"success": False, "msg": f"资金不足，需 RM {total_required:.2f}，当前可用 RM {cash:.2f}"}
        new_cash = cash - total_required
        cur.execute("UPDATE account SET cash = ?, updated_at = ? WHERE id = 1", (new_cash, now_str))
        cur.execute("SELECT shares, avg_cost FROM positions WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        if row:
          new_shares = row[0] + shares
          new_cost = ((row[0] * row[1]) + total_required) / new_shares
          cur.execute("UPDATE positions SET shares = ?, avg_cost = ?, updated_at = ? WHERE ticker = ?", (new_shares, new_cost, now_str, ticker))
        else:
          cur.execute("INSERT INTO positions VALUES (?, ?, ?, ?)", (ticker, shares, total_required / shares, now_str))
        net_amount = -total_required

      elif action == "SELL":
        cur.execute("SELECT shares, avg_cost FROM positions WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        if not row or row[0] < shares:
          return {"success": False, "msg": f"持仓不足，当前持仓 {row[0] if row else 0} 股"}
        proceeds = contract_val - fees["total_fee"]
        new_cash = cash + proceeds
        cur.execute("UPDATE account SET cash = ?, updated_at = ? WHERE id = 1", (new_cash, now_str))
        remaining = row[0] - shares
        if remaining == 0:
          cur.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
        else:
          cur.execute("UPDATE positions SET shares = ?, updated_at = ? WHERE ticker = ?", (remaining, now_str, ticker))
        net_amount = proceeds

      cur.execute("""
        INSERT INTO trades (date, ticker, action, lots, shares, price, contract_val, total_fees, net_amount, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """, (now_str, ticker, action, lots, shares, price, contract_val, fees["total_fee"], net_amount, reason))
      conn.commit()

    return {"success": True, "ticker": ticker, "action": action, "lots": lots}

  def record_daily_snapshot(self, price_map: Dict[str, float]) -> Dict:
    now_str = datetime.date.today().isoformat()
    with self._get_conn() as conn:
      cur = conn.cursor()
      cur.execute("SELECT cash FROM account WHERE id = 1")
      cash = cur.fetchone()[0]
      positions = pd.read_sql_query("SELECT * FROM positions", conn)
      portfolio_val = sum(row["shares"] * price_map.get(row["ticker"], row["avg_cost"]) for _, row in positions.iterrows()) if not positions.empty else 0.0
      total_equity = cash + portfolio_val

      cur.execute("SELECT total_equity FROM nav_history ORDER BY date DESC LIMIT 1")
      prev = cur.fetchone()
      prev_equity = prev[0] if prev else self.initial_capital
      daily_return = (((total_equity - prev_equity) / prev_equity) * 100) if prev_equity > 0 else 0.0

      cur.execute("""
        INSERT OR REPLACE INTO nav_history (date, cash, portfolio_value, total_equity, daily_return_pct)
        VALUES (?, ?, ?, ?, ?)
      """, (now_str, round(cash, 2), round(portfolio_val, 2), round(total_equity, 2), round(daily_return, 4)))
      conn.commit()
      return {"total_equity": round(total_equity, 2), "cash": round(cash, 2), "daily_return": round(daily_return, 2)}

# 4. Agent 决策入口
def run_agent_trading():
  api_key = os.environ.get("GEMINI_API_KEY")
  if not api_key:
    print("错误: 未配置 GEMINI_API_KEY 环境变量！")
    return

  try:
    from google import genai
    from google.genai import types
  except ImportError:
    print("错误: 请先安装 google-genai 依赖 (pip install google-genai)")
    return

  model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
  watchlist = ["1155", "1295", "5347", "1023", "5225"]
  engine = KLSELedgerEngine(db_path="klse_paper_trade.db", initial_capital=100000.0)
  
  market_data = KLSEMarketData.get_batch_market_data(watchlist)
  if not market_data:
    print("今日未能获取有效行情数据（可能为公假、周末或网络故障），跳过 AI 决策执行。")
    return

  account_info = engine.get_account_summary()

  system_prompt = f"""
    你是一名专注马来西亚吉隆坡证券交易所（KLSE）的理智量化与价值投资分析师。
    当前账户资金状态：
    - 可用现金：RM {account_info['cash']:.2f}
    - 当前持仓：{json.dumps(account_info['positions'], ensure_ascii=False)}

    今日市场行情快照：
    {json.dumps(market_data, ensure_ascii=False)}

    【投资与风控规则】：
    1. 每次交易单位必须为 1 Lot = 100 股。
    2. 单只股票总持仓不得超过总资产的 25%。现金储备必须保留不少于 10%。
    3. 如果没有明显胜率，保持持有（HOLD），不用每天都交易。
    4. 严格输出合规的 JSON 数组，严禁附带额外文字。
    格式示例：
    [
      {{"ticker": "1155", "action": "BUY", "lots": 5, "reason": "突破20日均线且估值具备吸引力"}},
      {{"ticker": "5347", "action": "HOLD", "lots": 0, "reason": "短期震荡，维持观望"}}
    ]
  """

  client = genai.Client(api_key=api_key)
  try:
    response = client.models.generate_content(
        model=model_name,
        contents=system_prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
  except Exception as e:
    print(f"Gemini API 调用异常: {e}")
    return

  print("AI 今日决策输出：\n", response.text)

  raw_text = response.text.strip()
  if raw_text.startswith("```"):
    raw_text = raw_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

  try:
    decisions = json.loads(raw_text)
  except json.JSONDecodeError as e:
    print(f"解析 AI 决策 JSON 失败: {e}\n原始内容: {response.text}")
    return

  for dec in decisions:
    action = dec.get("action", "").upper()
    ticker = str(dec.get("ticker", ""))
    lots = int(dec.get("lots", 0))
    reason = dec.get("reason", "")
    if action in ["BUY", "SELL"] and lots > 0 and ticker in market_data:
      price = market_data[ticker]["price"]
      result = engine.execute_order(ticker, action, lots, price, reason)
      print(f"执行订单结果 [{ticker}]:", result)

  price_map = {k: v["price"] for k, v in market_data.items()}
  summary = engine.record_daily_snapshot(price_map)
  print("\n今日资产清算完毕：", summary)

if __name__ == "__main__":
  run_agent_trading()
