"""
KLSE 规费精准计算模块
遵循 Bursa Malaysia（马来西亚吉隆坡证券交易所）最新交易成本规范
"""
import math
from typing import Dict
from investor_agent.config import CONFIG

class KLSEFeeCalculator:
    @staticmethod
    def calculate_fees(contract_value: float) -> Dict[str, float]:
        """
        计算马股单笔交易的全部规费成本
        :param contract_value: 合约总金额 (shares * price)
        :return: 包含各项明细及总规费的字典
        """
        if contract_value <= 0:
            return {
                "brokerage": 0.0,
                "sst": 0.0,
                "clearing_fee": 0.0,
                "stamp_duty": 0.0,
                "total_fee": 0.0,
            }
        
        # 1. 经纪佣金（最低 RM 8.00 或 0.08%）
        brokerage = max(CONFIG["min_brokerage_fee"], contract_value * CONFIG["brokerage_rate"])
        
        # 2. 经纪佣金服务税（8% SST）
        sst = brokerage * CONFIG["sst_rate"]
        
        # 3. 结算费（0.03%，上限 RM 1,000.00）
        clearing_fee = min(CONFIG["max_clearing_fee"], contract_value * CONFIG["clearing_fee_rate"])
        
        # 4. 印花税（每 RM 1,000 计 RM 1.50，不足 1,000 向上取整，上限 RM 1,000.00）
        stamp_duty = min(CONFIG["max_stamp_duty"], math.ceil(contract_value / 1000.00) * CONFIG["stamp_duty_unit"])
        
        total_fee = brokerage + sst + clearing_fee + stamp_duty
        
        return {
            "brokerage": round(brokerage, 2),
            "sst": round(sst, 2),
            "clearing_fee": round(clearing_fee, 2),
            "stamp_duty": round(stamp_duty, 2),
            "total_fee": round(total_fee, 2),
        }
