# backtester.py
import pandas as pd
from datetime import timedelta
import config
from strategy_factory import get_strategy

class Trade:
    def __init__(self, entry_time, entry_price, sl_price, size, sl_pct, side='LONG'):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.sl_price = sl_price
        self.size = size # Quantity in BTC
        self.sl_pct = sl_pct
        self.side = side # 'LONG' or 'SHORT'
        
        # Calculate Targets based on side
        risk_dist = abs(entry_price - sl_price)
        
        if self.side == 'LONG':
            self.tp1_price = entry_price + (risk_dist * config.TP1_RATIO)
            self.tp2_price = entry_price + (risk_dist * config.TP2_RATIO)
        else: # SHORT
            self.tp1_price = entry_price - (risk_dist * config.TP1_RATIO)
            self.tp2_price = entry_price - (risk_dist * config.TP2_RATIO)
        
        self.status = 'OPEN' # OPEN, TP1_HIT, CLOSED
        self.tp1_filled = False
        self.pnl = 0.0
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None

class Backtester:
    def __init__(self, df):
        self.df = df
        self.capital = config.INITIAL_CAPITAL
        self.equity_curve = []
        self.trades = []
        self.open_trades = [] # 支持多单
        
        # Load Strategy
        self.strategy = get_strategy(config.ACTIVE_STRATEGY)
        
        # Daily Constraints State
        self.current_date = None
        self.daily_trades_count = 0
        self.daily_realized_pnl = 0.0
        self.consecutive_losses = 0
        self.stop_trading_today = False

    def check_daily_reset(self, timestamp):
        date = timestamp.date()
        if self.current_date != date:
            self.current_date = date
            self.daily_trades_count = 0
            self.daily_realized_pnl = 0.0
            # Consecutive losses usually reset daily or persist? 
            # User said "连亏3单停手", usually implies session based. Let's reset daily.
            self.consecutive_losses = 0 
            self.stop_trading_today = False

    def calculate_position_size(self, entry_price, sl_price):
        # 1. 基于风险计算 (Risk Based - USDT)
        # 允许亏损的 USDT 金额
        risk_amount_usdt = self.capital * config.RISK_PER_TRADE_PCT
        
        # 每 1 BTC 的亏损 USDT (Diff)
        risk_per_btc_usdt = abs(entry_price - sl_price)
        
        if risk_per_btc_usdt <= 0: return 0
        
        # 风险限定的数量 (BTC)
        qty_by_risk = risk_amount_usdt / risk_per_btc_usdt
        
        # 2. 基于资金占用计算 (Capital Allocation Based - USDT)
        # 单笔最大投入 USDT = 本金 * 20%
        # 杠杆后最大可买 USDT 价值
        max_position_value_usdt = (self.capital * config.POSITION_SIZE_PCT) * config.LEVERAGE
        
        # 资金限定的数量 (BTC)
        qty_by_capital = max_position_value_usdt / entry_price
        
        # 取较小值，既满足风险控制，又满足资金分配
        return min(qty_by_risk, qty_by_capital)

    def close_trade(self, trade, price, reason, timestamp, pct=1.0):
        # Calculate PnL
        close_qty = trade.size * pct
        
        if trade.side == 'LONG':
            trade_pnl = (price - trade.entry_price) * close_qty
        else: # SHORT
            trade_pnl = (trade.entry_price - price) * close_qty
        
        # Commission
        commission = (trade.entry_price * close_qty * config.COMMISSION_RATE) + \
                     (price * close_qty * config.COMMISSION_RATE)
        
        net_pnl = trade_pnl - commission
        
        self.capital += net_pnl
        self.daily_realized_pnl += net_pnl
        
        # Update Trade Object
        if pct == 1.0:
            trade.status = 'CLOSED'
            trade.exit_time = timestamp
            trade.exit_price = price # Store exit price
            trade.exit_reason = reason
            trade.pnl += net_pnl
            self.trades.append(trade)
            
            # Remove from open trades
            if trade in self.open_trades:
                self.open_trades.remove(trade)
            
            if net_pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
        else:
            # Partial Close
            trade.size -= close_qty
            trade.pnl += net_pnl
            trade.exit_price = price 
    
    def run(self):
        print("Starting Backtest...")
        
        # Pre-calculate indicators first (safe)
        self.df = self.strategy.calculate_indicators(self.df)
        self.df.dropna(inplace=True)
        
        prev_row = None
        
        for timestamp, row in self.df.iterrows():
            self.check_daily_reset(timestamp)
            
            # Record Equity
            # Mark-to-market PnL for ALL open positions
            unrealized_pnl = 0
            for t in self.open_trades:
                if t.side == 'LONG':
                    unrealized_pnl += (row['close'] - t.entry_price) * t.size
                else:
                    unrealized_pnl += (t.entry_price - row['close']) * t.size
            
            self.equity_curve.append({'time': timestamp, 'equity': self.capital + unrealized_pnl})

            # Check Risk Stops (Daily)
            if self.stop_trading_today:
                # Still manage open trades even if stopped for new ones
                pass
            
            if self.daily_realized_pnl <= config.MAX_DAILY_LOSS:
                self.stop_trading_today = True
            
            if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS:
                self.stop_trading_today = True

            # --- Manage Open Positions (Loop over copy) ---
            for t in self.open_trades[:]:
                if t.side == 'LONG':
                    # Check SL (Low hits SL)
                    if row['low'] <= t.sl_price:
                        self.close_trade(t, t.sl_price, 'SL', timestamp)
                        continue
                    
                    # Check TP1 (High hits TP)
                    if not t.tp1_filled and row['high'] >= t.tp1_price:
                        self.close_trade(t, t.tp1_price, 'TP1', timestamp, pct=config.TP1_CLOSE_PCT)
                        t.tp1_filled = True
                        if config.MOVE_SL_TO_BE_AFTER_TP1:
                            t.sl_price = t.entry_price 
                    
                    # Check TP2
                    if t.tp1_filled and row['high'] >= t.tp2_price:
                        self.close_trade(t, t.tp2_price, 'TP2', timestamp, pct=1.0)
                        continue

                else: # SHORT
                    # Check SL (High hits SL)
                    if row['high'] >= t.sl_price:
                        self.close_trade(t, t.sl_price, 'SL', timestamp)
                        continue
                    
                    # Check TP1 (Low hits TP)
                    if not t.tp1_filled and row['low'] <= t.tp1_price:
                        self.close_trade(t, t.tp1_price, 'TP1', timestamp, pct=config.TP1_CLOSE_PCT)
                        t.tp1_filled = True
                        if config.MOVE_SL_TO_BE_AFTER_TP1:
                            t.sl_price = t.entry_price 
                    
                    # Check TP2
                    if t.tp1_filled and row['low'] <= t.tp2_price:
                        self.close_trade(t, t.tp2_price, 'TP2', timestamp, pct=1.0)
                        continue

            # --- Check Entry Signal ---
            # Condition: Not stopped today AND slots available
            if not self.stop_trading_today and \
               self.daily_trades_count < config.MAX_TRADES_PER_DAY and \
               len(self.open_trades) < config.MAX_OPEN_POSITIONS:
                
                signal = self.strategy.check_signal(row, prev_row)
                entry_price = row['close']
                
                # Check if we already have a position in this direction?
                # Usually grids/strategies might allow scaling in, but here "TrendMeanReversion" usually implies one entry per signal.
                # Let's simple check: Don't enter if we just entered (prev candle). 
                # But here we are iterating candles.
                # Strategy logic handles signal generation.
                
                if signal == 'LONG':
                    if config.USE_ATR_FOR_SL and not pd.isna(row['atr']):
                        sl_dist = row['atr'] * config.ATR_SL_MULTIPLIER
                    else:
                        sl_dist = entry_price * config.SL_PCT
                    
                    sl_price = entry_price - sl_dist
                    qty = self.calculate_position_size(entry_price, sl_price)
                    
                    if qty > 0:
                        new_trade = Trade(timestamp, entry_price, sl_price, qty, config.SL_PCT, side='LONG')
                        self.open_trades.append(new_trade)
                        self.daily_trades_count += 1
                
                elif signal == 'SHORT':
                    if config.USE_ATR_FOR_SL and not pd.isna(row['atr']):
                        sl_dist = row['atr'] * config.ATR_SL_MULTIPLIER
                    else:
                        sl_dist = entry_price * config.SL_PCT
                        
                    sl_price = entry_price + sl_dist 
                    qty = self.calculate_position_size(entry_price, sl_price)
                    
                    if qty > 0:
                        new_trade = Trade(timestamp, entry_price, sl_price, qty, config.SL_PCT, side='SHORT')
                        self.open_trades.append(new_trade)
                        self.daily_trades_count += 1

            prev_row = row

        print("Backtest Finished.")
        return pd.DataFrame(self.equity_curve)

    def get_stats(self):
        if not self.trades:
            return {
                'Final Capital': self.capital,
                'Total Trades': 0,
                'Win Rate': "0.00%",
                'Total PnL': "$0.00",
                'Max Drawdown': "0.00%"
            }
        
        df_t = pd.DataFrame([vars(t) for t in self.trades])
        total_trades = len(df_t)
        wins = len(df_t[df_t['pnl'] > 0])
        win_rate = wins / total_trades if total_trades > 0 else 0
        total_pnl = df_t['pnl'].sum()
        
        return {
            'Final Capital': self.capital,
            'Total Trades': total_trades,
            'Win Rate': f"{win_rate*100:.2f}%",
            'Total PnL': f"${total_pnl:.2f}",
            'Max Drawdown': "N/A (Calculated from equity curve)"
        }
