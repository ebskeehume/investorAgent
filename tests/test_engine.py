"""
单元测试与核心风控引擎验证
"""
import os
import unittest
import pandas as pd
import numpy as np
from investor_agent.config import CONFIG
from investor_agent.ledger.fees import KLSEFeeCalculator
from investor_agent.ledger.engine import KLSELedgerEngine
from investor_agent.data.market import KLSEMarketData
from investor_agent.analytics.attribution import PortfolioAnalytics

class TestKLSEAgent(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_klse_unit.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.engine = KLSELedgerEngine(db_path=self.test_db, initial_capital=100000.0)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_fee_calculator(self):
        """测试马股规费计算模型"""
        # RM 10,000 买单
        fees = KLSEFeeCalculator.calculate_fees(10000.0)
        self.assertEqual(fees["brokerage"], 8.0)       # 0.08% = 8.0 (最低 RM 8)
        self.assertEqual(fees["sst"], 0.64)            # 8.0 * 0.08 = 0.64
        self.assertEqual(fees["clearing_fee"], 3.0)    # 10,000 * 0.0003 = 3.0
        self.assertEqual(fees["stamp_duty"], 15.0)     # ceil(10,000/1000) * 1.5 = 15.0
        self.assertEqual(fees["total_fee"], 26.64)

    def test_order_execution_and_guardrails(self):
        """测试订单撮合与前置硬风控守卫"""
        # 1. 正常买入：买入 10 手 (1000股) @ RM 10.00 = RM 10,000 市值 (占 10% 资产，合规)
        res = self.engine.execute_order("1155", "BUY", 10, 10.0, "Test normal buy")
        self.assertTrue(res["success"])
        self.assertEqual(res["shares"], 1000)

        # 2. 尝试买入超过 20% 仓位限额：再买入 25 手 (2500股) @ RM 10.00 = 累计 RM 35,000 (占 35% 资产，应被拦截)
        res_overweight = self.engine.execute_order("1155", "BUY", 25, 10.0, "Test overweight buy")
        self.assertFalse(res_overweight["success"])
        self.assertIn("超过总资产 20% 限额", res_overweight["msg"])

        # 3. 正常卖出 5 手
        res_sell = self.engine.execute_order("1155", "SELL", 5, 10.5, "Test partial sell")
        self.assertTrue(res_sell["success"])
        summary = self.engine.get_account_summary()
        self.assertEqual(summary["positions"][0]["shares"], 500)

    def test_stop_loss_enforcement(self):
        """测试 7% 硬止损触发逻辑"""
        # 买入成本均价 RM 10.00
        self.engine.execute_order("1155", "BUY", 5, 10.0, "Initial buy")
        
        # 标的大跌 8% 到 RM 9.20 (低于 7% 止损线)
        triggered = self.engine.scan_and_enforce_stop_loss_take_profit({"1155": 9.20})
        self.assertEqual(len(triggered), 1)
        self.assertTrue(triggered[0]["success"])
        self.assertEqual(triggered[0]["action"], "SELL")
        
        # 验证持仓已被彻底清空
        summary = self.engine.get_account_summary()
        self.assertEqual(len(summary["positions"]), 0)

    def test_portfolio_analytics(self):
        """测试投资组合绩效指标与归因计算"""
        # 记录两天快照 (传入不同日期)
        self.engine.record_daily_snapshot({}, benchmark_price=1600.0, date_str="2026-09-01")
        self.engine.record_daily_snapshot({}, benchmark_price=1616.0, date_str="2026-09-02") # 基准上涨 1%
        
        analytics = PortfolioAnalytics(self.engine)
        metrics = analytics.generate_performance_metrics()
        self.assertEqual(metrics["total_days"], 2)
        self.assertIn("alpha_pct", metrics)
        self.assertIn("max_drawdown_pct", metrics)

if __name__ == "__main__":
    unittest.main()
