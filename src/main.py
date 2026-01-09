# main.py
import data_loader
import backtester
import config
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
from datetime import datetime

def main():
    # 1. Configuration & Argument Parsing
    parser = argparse.ArgumentParser(description="Qtrading Backtest System")
    parser.add_argument('--start', type=str, default='2021-01-01', help='Start Date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2021-06-01', help='End Date (YYYY-MM-DD)')
    args = parser.parse_args()

    start_date = args.start
    end_date = args.end
    
    print(f"--- Qtrading Backtest System ---")
    print(f"Strategy: {config.ACTIVE_STRATEGY}")
    print(f"Period: {start_date} to {end_date}")
    
    # 2. Data Preparation
    # This pulls from ClickHouse and merges 1H/15m/5m
    try:
        df = data_loader.prepare_strategy_data(start_date, end_date)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # 3. Run Backtest
    bt = backtester.Backtester(df)
    equity_df = bt.run()
    
    # 4. Results
    stats = bt.get_stats()
    
    # Calculate additional metrics for display
    if not equity_df.empty:
        peak = equity_df['equity'].max()
        current_equity = equity_df['equity'].iloc[-1]
        drawdown = (equity_df['equity'] - equity_df['equity'].cummax()) / equity_df['equity'].cummax()
        max_drawdown = drawdown.min()
        total_pnl = current_equity - config.INITIAL_CAPITAL
        
        # Calculate win/loss details
        trades_df = pd.DataFrame([vars(t) for t in bt.trades]) if bt.trades else pd.DataFrame()
        total_wins = len(trades_df[trades_df['pnl'] > 0]) if not trades_df.empty else 0
        total_losses = len(trades_df[trades_df['pnl'] < 0]) if not trades_df.empty else 0
    else:
        peak = max_drawdown = total_pnl = total_wins = total_losses = 0

    print("\n--- Results ---")
    for k, v in stats.items():
        print(f"{k}: {v}")
        
    # 5. Save Trades Log
    # ... (existing code)

    # 6. Plot HTML Report (Equity vs BTC Price)
    if not equity_df.empty:
        print("Generating HTML report...")
        # (Prepare data)
        temp_equity_df = equity_df.copy().set_index('time')
        result_df = temp_equity_df.join(df['close'])
        
        # Create Figure with Subplots (One for summary, one for chart)
        # We removed the top row 'Indicators' from the Plotly figure because we are using custom HTML cards now.
        # So we only need the chart (Equity + BTC).
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # --- Add Main Charts ---
        # Equity Trace
        fig.add_trace(
            go.Scatter(x=result_df.index, y=result_df['equity'], name="权益曲线 (USDT)", line=dict(color='blue', width=2)),
            secondary_y=False
        )
        # BTC Price Trace
        fig.add_trace(
            go.Scatter(x=result_df.index, y=result_df['close'], name="BTC 价格", line=dict(color='gray', width=1, dash='dot'), opacity=0.3),
            secondary_y=True
        )

        # --- Add Trade Annotations ---
        if bt.trades:
            # Entry Markers
            entry_x = [t.entry_time for t in bt.trades]
            entry_y = [t.entry_price for t in bt.trades]
            fig.add_trace(go.Scatter(
                x=entry_x, y=entry_y, mode='markers', name='买入',
                marker=dict(symbol='triangle-up', size=10, color='green'),
                showlegend=True
            ), secondary_y=True)

            # Exit Markers & Labels
            for t in bt.trades:
                color = 'red' if t.pnl < 0 else 'blue'
                label = f"{'+' if t.pnl > 0 else ''}${t.pnl:.2f}"
                fig.add_trace(go.Scatter(
                    x=[t.exit_time], y=[t.exit_price], mode='markers+text',
                    text=[label], textposition="top center",
                    marker=dict(symbol='triangle-down', size=10, color=color),
                    showlegend=False
                ), secondary_y=True)

        # Update Layout
        fig.update_layout(
            height=800,
            title_text=f"账户权益 vs BTC 价格趋势",
            xaxis_title="日期",
            yaxis_title="账户权益 (USDT)",
            yaxis2_title="BTC 价格 (USDT)",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)')
        )
        
        # Save to HTML with Chinese localization and EMBEDDED JS (Offline)
        output_file = "backtest_report.html"
        
        # Generate the Plotly div with embedded JavaScript (approx 3MB, but works offline)
        plot_div = fig.to_html(full_html=False, include_plotlyjs=True, config={'displayModeBar': True, 'responsive': True})
        
        # Determine PnL Label and Class
        pnl_label = "总收益" if total_pnl >= 0 else "总亏损"
        pnl_class = "positive" if total_pnl >= 0 else "negative"
        
        # Calculate ROI
        roi_pct = (total_pnl / config.INITIAL_CAPITAL) * 100

        # Custom HTML template for better layout
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Qtrading 量化回测报告</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ text-align: center; color: #333; margin-bottom: 5px; }}
                .subtitle {{ text-align: center; color: #666; margin-bottom: 30px; font-size: 0.9em; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #e9ecef; }}
                .metric-value {{ font-size: 20px; font-weight: bold; color: #2c3e50; margin: 5px 0; }}
                .metric-label {{ font-size: 13px; color: #7f8c8d; }}
                .metric-value.positive {{ color: #27ae60; }}
                .metric-value.negative {{ color: #c0392b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Qtrading 回测报告</h1>
                <div class="subtitle">周期: {start_date} 至 {end_date}</div>
                
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label">当前权益</div>
                        <div class="metric-value {'positive' if current_equity >= config.INITIAL_CAPITAL else 'negative'}">${current_equity:.2f}</div>
                        <div class="metric-label">初始: ${config.INITIAL_CAPITAL:.2f}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">{pnl_label}</div>
                        <div class="metric-value {pnl_class}">${total_pnl:.2f}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">总盈亏%</div>
                        <div class="metric-value {pnl_class}">{roi_pct:+.2f}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">总盈利次数</div>
                        <div class="metric-value positive">{total_wins}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">总亏损次数</div>
                        <div class="metric-value negative">{total_losses}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">最大回撤</div>
                        <div class="metric-value negative">{max_drawdown*100:.2f}%</div>
                    </div>
                </div>

                <!-- Plotly Chart -->
                {plot_div}
            </div>
        </body>
        </html>
        """
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"✅ Enhanced report saved to '{output_file}'")

if __name__ == "__main__":
    main()
