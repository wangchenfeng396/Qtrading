from strategies.trend_mean_reversion import TrendMeanReversion
import config

def get_strategy(strategy_name):
    if strategy_name == 'TrendMeanReversion':
        return TrendMeanReversion(config)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
