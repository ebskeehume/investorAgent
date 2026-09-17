"""
KLSE AI Agent - 全局配置与参数定义
"""
from typing import Dict, List

CONFIG = {
    # 账户与资金配置
    "initial_capital_myr": 100000.00,  # 初始虚拟本金 RM 100,000
    "max_position_weight": 0.20,       # 单股最大持仓上限 20% (RM 20,000)
    "min_cash_reserve": 0.10,          # 现金底仓储备不低于 10%
    "lot_size": 100,                   # 马股强制 100 股（1手）整数倍
    "stop_loss_pct": 0.07,             # 7% 硬止损
    "take_profit_pct": 0.15,           # 15% 目标止盈
    
    # 规费模型 (Bursa Malaysia 真实标准)
    "brokerage_rate": 0.0008,          # 佣金 0.08%
    "min_brokerage_fee": 8.00,         # 最低佣金 RM 8.00
    "sst_rate": 0.08,                  # 佣金服务税 8% SST
    "clearing_fee_rate": 0.0003,       # 结算费 0.03%
    "max_clearing_fee": 1000.00,       # 结算费上限 RM 1000.00
    "stamp_duty_unit": 1.50,           # 每 RM 1,000 征收 RM 1.50 印花税
    "max_stamp_duty": 1000.00,         # 印花税上限 RM 1000.00

    # 数据库路径
    "db_path": "klse_paper_trade.db",

    # 基准指数代码
    "benchmark_ticker": "^KLSE",

    # 投资标的池：富时隆综指核心成分股 (FBMKLCI 30 + 优质中盘)
    "watchlist": [
        "1155",  # Maybank (马来亚银行)
        "1295",  # Public Bank (大众银行)
        "1023",  # CIMB Group (联昌国际)
        "5347",  # Tenaga Nasional (国家能源)
        "5225",  # IHH Healthcare (IHH医疗)
        "5183",  # Petronas Chemicals (国油化学)
        "6033",  # Petronas Gas (国油气体)
        "6947",  # CelcomDigi (天地通数码)
        "4707",  # Nestlé (Malaysia) (雀巢马)
        "4197",  # Sime Darby (森那美)
        "1961",  # IOI Corporation (IOI集团)
        "2445",  # Kuala Lumpur Kepong (吉隆坡甲洞)
        "5819",  # Hong Leong Bank (丰隆银行)
        "1066",  # RHB Bank (兴业银行)
        "8869",  # Press Metal Aluminium (齐力工业)
    ],

    # 宏观监测标的
    "macro_tickers": {
        "brent_crude": "BZ=F",       # 布伦特原油期货
        "sp500": "^GSPC",            # 美股标普 500
        "klci_index": "^KLSE",       # 富时隆综指
        "usd_myr": "MYR=X",          # 美元兑马币汇率
    }
}
