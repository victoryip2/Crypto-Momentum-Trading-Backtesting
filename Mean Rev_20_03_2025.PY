import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ib_insync import *
import pytz
""" import yfinance as yf
data = yf.download(sp500_tickers, start='2020-01-01', end='2020-12-31', group_by='ticker')
close_df = data.xs('Close', level=1, axis=1)
open_df = data.xs('Open', level=1, axis=1) """
# Connect to Interactive Brokers
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2)  # 7497 = Paper Trading, 7496 = Live Trading

# Fetch S&P 500 tickers from Wikipedia
url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
table = pd.read_html(url)[0]
sp500_tickers = table['Symbol'].tolist()

# For this example, use a subset of 50 tickers to speed up data fetching
sp500_tickers = sp500_tickers[:50]  # Remove this line to use all 500 tickers

# Fetch daily historical data from IB
all_data = []
for ticker in sp500_tickers:
    contract = Stock(ticker, 'SMART', 'USD')
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='20221231 23:59:00 US/Eastern',  # End of backtest period
        durationStr='255 D',  # One year of data
        barSizeSetting='1 day',  # Daily bars
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )
    df = pd.DataFrame(bars)
    df['ticker'] = ticker
    all_data.append(df)

# Disconnect from IB after fetching data
ib.disconnect()

# Combine all data into a single DataFrame
all_data_df = pd.concat(all_data)
all_data_df.set_index(['date', 'ticker'], inplace=True)
all_data_df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)

# Pivot data to have tickers as columns
close_df = all_data_df['Close'].unstack(level='ticker')
open_df = all_data_df['Open'].unstack(level='ticker')

# Ensure the index is datetime
close_df.index = pd.to_datetime(close_df.index)
open_df.index = pd.to_datetime(open_df.index)

# Calculate daily returns based on close-to-close prices
returns_df = close_df.pct_change()

# Initialize portfolio with $10,000
portfolio_value = 10000
portfolio_values = [portfolio_value]

# Define trading days (start from the second day since we need previous day's data)
trading_days = close_df.index[1:]

# Backtest the strategy
for t in trading_days:
    # Find the previous trading day
    prev_day = t - pd.Timedelta(days=1)
    while prev_day not in returns_df.index:  # Handle weekends/holidays
        prev_day -= pd.Timedelta(days=1)
    prev_returns = returns_df.loc[prev_day]
    
    # Select the top 10 stocks that dropped the most (most negative returns)
    selected_stocks = prev_returns.nsmallest(10).index
    
    # Get open and close prices for these stocks on the current day
    open_prices = open_df.loc[t, selected_stocks]
    close_prices = close_df.loc[t, selected_stocks]
    
    # Calculate individual trade returns: (close - open) / open
    trade_returns = (close_prices - open_prices) / open_prices
    
    # Portfolio return is the average of trade returns (equal weighting)
    portfolio_return = trade_returns.mean()
    
    # Update portfolio value
    portfolio_value *= (1 + portfolio_return)
    portfolio_values.append(portfolio_value)

# Create a Series for portfolio values
portfolio_series = pd.Series(portfolio_values, index=close_df.index[:len(portfolio_values)])

# Plot the equity curve
plt.figure(figsize=(12, 6))
plt.plot(portfolio_series)
plt.title('Portfolio Equity Curve')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.grid(True)
plt.show()

# Calculate and display total return
total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0] - 1) * 100
print(f'Total Return: {total_return:.2f}%')