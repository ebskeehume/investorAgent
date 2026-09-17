"""
KLSE 市场行情与技术指标计算模块
"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import yfinance as yf
from investor_agent.config import CONFIG

class KLSEMarketData:
    @staticmethod
    def format_ticker(code: str) -> str:
        code = code.strip().upper()
        return code if code.endswith(".KL") else f"{code}.KL"

    @classmethod
    def calculate_technical_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        基于纯 Pandas/NumPy 计算核心量化指标：SMA20, RSI(14), MACD(12,26,9), ATR(14)
        """
        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # 1. 20日均线 (SMA20)
        df["SMA20"] = close.rolling(window=20).mean()

        # 2. 相对强弱指标 (RSI 14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI14"] = 100 - (100 / (1 + rs))

        # 3. 异同移动平均线 (MACD 12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # 4. 真实波幅 (ATR 14)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR14"] = tr.rolling(window=14).mean()

        return df

    @classmethod
    def get_batch_market_data(cls, codes: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        批量获取股票最新量化行情指标，过滤流动性陷阱
        """
        codes = codes or CONFIG["watchlist"]
        if not codes:
            return {}

        formatted_codes = [cls.format_ticker(c) for c in codes]
        try:
            # 下载近 3 个月的日 K 线，确保有足够数据计算 26日 EMA 和 20日均线
            data = yf.download(
                formatted_codes,
                period="3mo",
                interval="1d",
                group_by="ticker",
                progress=False,
                auto_adjust=False
            )
        except Exception as e:
            print(f"行情下载网络异常: {e}")
            return {}

        results = {}
        is_multi = isinstance(data.columns, pd.MultiIndex)

        for code in codes:
            t = cls.format_ticker(code)
            try:
                if is_multi:
                    if t not in data.columns.levels[0]:
                        continue
                    sub_df = data[t].dropna(subset=["Close", "Volume"])
                else:
                    sub_df = data.dropna(subset=["Close", "Volume"])

                if len(sub_df) < 26:
                    continue  # 数据长度不足以计算指标则跳过

                # 计算技术指标
                ind_df = cls.calculate_technical_indicators(sub_df)
                latest = ind_df.iloc[-1]
                prev_5d = ind_df.iloc[-5] if len(ind_df) >= 5 else ind_df.iloc[0]

                latest_close = float(latest["Close"])
                sma20 = float(latest["SMA20"]) if not pd.isna(latest["SMA20"]) else latest_close
                rsi14 = float(latest["RSI14"]) if not pd.isna(latest["RSI14"]) else 50.0
                macd = float(latest["MACD"]) if not pd.isna(latest["MACD"]) else 0.0
                macd_hist = float(latest["MACD_Hist"]) if not pd.isna(latest["MACD_Hist"]) else 0.0
                atr14 = float(latest["ATR14"]) if not pd.isna(latest["ATR14"]) else 0.05
                change_5d = float((latest_close - prev_5d["Close"]) / prev_5d["Close"] * 100)
                vol = int(latest["Volume"]) if not pd.isna(latest["Volume"]) else 0
                avg_vol_20 = int(sub_df["Volume"].tail(20).mean()) if len(sub_df) >= 20 else vol

                # 趋势判断
                trend = "BULLISH" if latest_close > sma20 and macd_hist > 0 else (
                    "BEARISH" if latest_close < sma20 and macd_hist < 0 else "NEUTRAL"
                )

                results[code] = {
                    "price": round(latest_close, 3),
                    "sma20": round(sma20, 3),
                    "rsi14": round(rsi14, 2),
                    "macd": round(macd, 4),
                    "macd_hist": round(macd_hist, 4),
                    "atr14": round(atr14, 3),
                    "change_5d_pct": round(change_5d, 2),
                    "volume": vol,
                    "avg_vol_20": avg_vol_20,
                    "trend": trend,
                }
            except Exception as e:
                print(f"处理股票 {code} 技术指标异常: {e}")
                continue

        return results
