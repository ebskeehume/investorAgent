"""
KLSE 投资绩效与归因报告生成脚本
运行命令: python generate_report.py
"""
import sys
from investor_agent.analytics.attribution import PortfolioAnalytics
from investor_agent.ledger.engine import KLSELedgerEngine

# 兼容 Windows 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    engine = KLSELedgerEngine()
    analytics = PortfolioAnalytics(engine)
    
    report = analytics.generate_markdown_report()
    print("\n" + report + "\n")

    # 同时将报告保存在当前目录
    with open("performance_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("报告已自动保存至: performance_report.md")

if __name__ == "__main__":
    main()
