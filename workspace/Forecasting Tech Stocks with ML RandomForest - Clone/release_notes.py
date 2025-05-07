#region imports
from AlgorithmImports import *
#endregion
# 05/25/2023 -Set the universe data normalization mode to raw
#            -Added warm-up
#            -Made the following updates to the portfolio construction model:
#                - Added IsRebalanceDue to only rebalance after warm-up finishes and there is quote data
#                - Reset the MeanVarianceSymbolData indicator and window when corporate actions occur
#                - Changed the minimum portfolio weight to be algorithm.Settings.MinAbsolutePortfolioTargetPercentage*1.1 to avoid errors
#            -Adjusted the history requests to use scaled raw data normalization
#            https://www.quantconnect.com/terminal/processCache?request=embedded_backtest_587cc09bd82676a2ede5c88b100ef70b.html
#
# 07/13/2023: -Fixed warm-up logic to liquidate undesired portfolio holdings on re-deployment
#             -Set the MinimumOrderMarginPortfolioPercentage to 0
#             https://www.quantconnect.com/terminal/processCache?request=embedded_backtest_fa3146d7b1b299f4fc23ef0465540be0.html
