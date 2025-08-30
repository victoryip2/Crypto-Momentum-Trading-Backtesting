
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from alpha_vantage.timeseries import TimeSeries
import yfinance as yf
import pandas as pd
##data=yfinance.download("TSLA", start="2025-7-30", end="2025-08-10",interval="1d",auto_adjust=False)


ticker = "TSLA"
data = yf.download(ticker, period="1y", interval="1d",auto_adjust=False)

# Ensure proper datetime index
data.index = pd.to_datetime(data.index)

# Drop multi-level column names (if present)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.droplevel(1)  # Drop ticker level

# Rename columns explicitly
#data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

#####data.index = pd.to_datetime(data.index).tz_convert('US/Eastern')

# ✅ Filter data to start at 9:30 AM
####data = data.between_time('09:30', '16:00')
####data.index = data.index.tz_localize(None)

""" # Fetch SPY data from Alpha Vantage
api_key = "R5VTN8QDRFPEDKGM"  # Replace with your Alpha Vantage API key
try:
    ts = TimeSeries(key=api_key, output_format="pandas")
    data, _ = ts.get_daily(symbol="SPY", outputsize="full")
except Exception as e:
    print(f"Error fetching data: {e}")
    exit()

# Rename columns to match original script
data = data.rename(columns={
    "1. open": "Open",
    "2. high": "High",
    "3. low": "Low",
    "4. close": "Close",
    "5. volume": "Volume"
})
 """
# Ensure index is datetime and sorted
""" data.index = pd.to_datetime(data.index) """
data = data.sort_index()

# Debug: Print available date range
print(f"Data available from {data.index.min()} to {data.index.max()}")

# Define desired date range
start_date = "2025-06-14"
end_date = data.index.max().strftime("%Y-%m-%d")  # Use latest available date
print(f"Filtering data from {start_date} to {end_date}")

# Filter data for the desired date range
try:
    data = data.loc[start_date:end_date][["Open", "High", "Low", "Close", "Volume"]].copy()
except KeyError as e:
    print(f"Error slicing data: {e}. Available dates may not include the requested range.")
    exit()

# Calculate indicators
data['SMA_200'] = data['Close'].rolling(window=200).mean()
data['SMA_5'] = data['Close'].rolling(window=5).mean()
data['Price_Change'] = data['Close'].diff()
data['SMA_200_Change'] = data['SMA_200'].diff()

# Identify three consecutive down days
data['Down_Day'] = data['Price_Change'] < 0
data['Three_Down_Days'] = (
    data['Down_Day'] & 
    data['Down_Day'].shift(1) & 
    data['Down_Day'].shift(2)
)

# Buy signal: Three down days AND 200-day SMA increasing
data['Buy_Signal'] = (data['Three_Down_Days'] == True) & (data['SMA_200_Change'] > 0)

# Sell signal: Close price > 5-day SMA
data['Sell_Signal'] = data['Close'] > data['SMA_5']

# Backtesting logic
capital = 10000  # Starting capital
position = 0  # Shares held
cash = capital  # Available cash
equity = []  # Track portfolio value
trades = []  # Store trade details

for i in range(1, len(data)):
    # Record equity each day
    portfolio_value = cash + position * data['Close'].iloc[i]
    equity.append(portfolio_value)
    
    # Check for buy signal
    if data['Buy_Signal'].iloc[i] and position == 0:
        shares_to_buy = cash // data['Close'].iloc[i]
        position += shares_to_buy
        cash -= shares_to_buy * data['Close'].iloc[i]
        trades.append({
            'Date': data.index[i],
            'Type': 'Buy',
            'Price': data['Close'].iloc[i],
            'Shares': shares_to_buy,
            'Portfolio_Value': portfolio_value
        })
    
    # Check for sell signal
    elif data['Sell_Signal'].iloc[i] and position > 0:
        cash += position * data['Close'].iloc[i]
        trades.append({
            'Date': data.index[i],
            'Type': 'Sell',
            'Price': data['Close'].iloc[i],
            'Shares': position,
            'Portfolio_Value': portfolio_value
        })
        position = 0

# Final portfolio value
final_value = cash + position * data['Close'].iloc[-1]
equity.append(final_value)

# Convert equity to DataFrame
equity_df = pd.DataFrame(equity, index=data.index[1:], columns=['Portfolio_Value'])

# Calculate performance metrics
returns = equity_df['Portfolio_Value'].pct_change().dropna()
total_return = (final_value - capital) / capital * 100
sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0
equity_df['Drawdown'] = (equity_df['Portfolio_Value'] / equity_df['Portfolio_Value'].cummax() - 1) * 100
max_drawdown = equity_df['Drawdown'].min()

# Trade statistics
trades_df = pd.DataFrame(trades)
if not trades_df.empty:
    sell_trades = trades_df[trades_df['Type'] == 'Sell']
    buy_trades = trades_df[trades_df['Type'] == 'Buy']
    win_trades = sell_trades['Price'].values > buy_trades['Price'].values[:len(sell_trades)]
    win_rate = win_trades.mean() * 100 if len(win_trades) > 0 else 0
    num_trades = len(sell_trades)
else:
    win_rate = 0
    num_trades = 0

# Print results
print(f"Starting Capital: ${capital:.2f}")
print(f"Final Portfolio Value: ${final_value:.2f}")
print(f"Total Return: {total_return:.2f}%")
print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
print(f"Maximum Drawdown: {max_drawdown:.2f}%")
print(f"Number of Trades: {num_trades}")
print(f"Win Rate: {win_rate:.2f}%")

# Plot equity curve and signals
plt.figure(figsize=(12, 6))
plt.plot(equity_df.index, equity_df['Portfolio_Value'], label='Portfolio Value', color='blue')
buy_dates = trades_df[trades_df['Type'] == 'Buy']['Date']
buy_prices = data.loc[buy_dates, 'Close']
sell_dates = trades_df[trades_df['Type'] == 'Sell']['Date']
sell_prices = data.loc[sell_dates, 'Close']
plt.scatter(buy_dates, data.loc[buy_dates, 'Close'], marker='^', color='green', label='Buy', s=100)
plt.scatter(sell_dates, data.loc[sell_dates, 'Close'], marker='v', color='red', label='Sell', s=100)
plt.title('Equity Curve with Buy/Sell Signals')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.legend()
plt.grid()
plt.show()
