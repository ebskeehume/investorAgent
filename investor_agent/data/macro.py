"""
宏观市场与大宗商品环境抓取模块
用于盘前扫描美股外盘、布伦特原油、大马综指走势与汇率
"""
from typing import Dict
import pandas as pd
import yfinance as yf
from investor_agent.config import CONFIG

class MacroEnvironment:
    @staticmethod
    def get_macro_snapshot() -> Dict[str, Dict]:
        """
        获取宏观资产快照（原油、标普500、隆综指、汇率）
        """
        macro_tickers = CONFIG["macro_tickers"]
        tickers_list = list(macro_tickers.values())
        results = {}

        try:
            data = yf.download(
                tickers_list,
                period="5d",
                interval="1d",
                group_by="ticker",
                progress=False,
                auto_adjust=False
            )
        except Exception as e:
            print(f"宏观数据下载异常: {e}")
            return {}

        is_multi = isinstance(data.columns, pd.MultiIndex)

        for name, ticker in macro_tickers.items():
            try:
                if is_multi:
                    if ticker not in data.columns.levels[0]:
                        continue
                    sub = data[ticker].dropna(subset=["Close"])
                else:
                    sub = data.dropna(subset=["Close"])

                if len(sub) < 2:
                    continue

                latest_close = float(sub["Close"].iloc[-1])
                prev_close = float(sub["Close"].iloc[-2])
                change_pct = ((latest_close - prev_close) / prev_close) * 100

                results[name] = {
                    "ticker": ticker,
                    "price": round(latest_close, 3),
                    "change_1d_pct": round(change_pct, 2)
                }
            except Exception as e:
                print(f"解析宏观标的 {ticker} 异常: {e}")
                continue

        return results
