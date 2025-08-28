from backtesting import Backtest, Strategy
import pandas as pd
import numpy as np
from backtesting.lib import crossover

# Define the multi-strategy class
class MultiStrategy(Strategy):
    system = "Reversal"  # Default system
    starting_balance = 1000000

    def init(self):
        self.high = self.data.High
        self.low = self.data.Low
        self.close = self.data.Close
        self.open = self.data.Open

        def shift(arr, n=1):
            result = np.empty_like(arr)
            result[:n] = np.nan
            result[n:] = arr[:-n]
            return result

        high_shifted = shift(self.high)
        low_shifted = shift(self.low)
        self.reversal = (self.high < high_shifted) & (self.low < low_shifted)
        self.down_reversal = (self.high < high_shifted) & (self.low < low_shifted) & (self.close < self.open)
        self.momentum = (self.high > high_shifted) & (self.low > high_shifted)
        self.buyhold = np.ones_like(self.high, dtype=bool)

        self.reversal_trade = shift(self.reversal) & (self.high > high_shifted)
        self.down_reversal_trade = shift(self.down_reversal) & (self.high > high_shifted)
        self.momentum_trade = shift(self.momentum) & (self.high > high_shifted)
        self.buyhold_trade = np.ones_like(self.high, dtype=bool)

    def next(self):
        if self.system == "Reversal":
            trade_signal = self.reversal_trade[-1]
        elif self.system == "Down_Reversal":
            trade_signal = self.down_reversal_trade[-1]
        elif self.system == "Momentum":
            trade_signal = self.momentum_trade[-1]
        elif self.system == "BuyHold":
            trade_signal = self.buyhold_trade[-1]
        else:
            return

        if trade_signal and not np.isnan(trade_signal):
            if self.system == "BuyHold":
                entry_price = self.close[-1]
            else:
                entry_price = self.open[-1] if self.open[-1] > self.high[-2] else self.high[-2]
            
            if not self.position:
                self.buy(size=1, limit=entry_price)

        if self.position and self.system != "BuyHold":
            self.position.close()

# Load and prepare data
symbol = "BTC-USD"
start = pd.to_datetime("2024-01-01")
end = pd.to_datetime("2025-01-01")
try:
    data = pd.read_csv('C:/Users/victo/OneDrive/文件/Trading Bot/BTC_binance_data.csv', 
                       parse_dates=['Date'], 
                       date_format='%m/%d/%Y')
except FileNotFoundError:
    print("Error: CSV file not found. Please check the file path.")
    exit()
except ValueError as e:
    print(f"Error parsing dates: {e}")
    print("Please check the 'Date' column format in your CSV.")
    exit()
except Exception as e:
    print(f"Error loading CSV: {e}")
    exit()

# Verify data
if data.empty:
    print("Error: CSV file is empty.")
    exit()

# Convert Date column to datetime (redundant if parse_dates worked, but ensures correctness)
data['Date'] = pd.to_datetime(data['Date'], errors='coerce')

# Check for invalid dates
if data['Date'].isna().any():
    print("Error: Some dates could not be parsed. Check the 'Date' column for invalid values.")
    print(data[data['Date'].isna()])
    exit()

# Filter data within the specified date range
data = data[(data['Date'] >= start) & (data['Date'] <= end)]

if data.empty:
    print(f"Error: No data available for the date range {start} to {end}.")
    print("Check the date range in your CSV.")
    exit()

# Set Date as index
data = data.set_index('Date')

# Drop unnecessary columns and ensure correct column names
try:
    data = data.drop(['Volume', 'Adj Close'], axis=1, errors='ignore')
    data.columns = ['Open', 'High', 'Low', 'Close']
except KeyError:
    print("Error: CSV does not contain expected columns (Open, High, Low, Close, Volume, Adj Close).")
    exit()

# Ensure numeric data
for col in ['Open', 'High', 'Low', 'Close']:
    data[col] = pd.to_numeric(data[col], errors='coerce')

# Check for NaN values
if data[['Open', 'High', 'Low', 'Close']].isna().any().any():
    print("Warning: NaN values detected in data. Filling with forward fill.")
    data = data.fillna(method='ffill')

# Ensure unique index
if not data.index.is_unique:
    print("Warning: Duplicate dates detected in index. Keeping first occurrence.")
    data = data[~data.index.duplicated(keep='first')]

# Debug: Print data summary
print("Data summary:")
print(data.head())
print(f"Date range: {data.index.min()} to {data.index.max()}")
print(f"Number of rows: {len(data)}")

# Run backtests for each system
systems = ["Reversal", "Down_Reversal", "Momentum", "BuyHold"]
results = {}
for system in systems:
    try:
        bt = Backtest(
            data,
            MultiStrategy,
            cash=1000000,
            commission=0.002,
            exclusive_orders=True
        )
        stats = bt.run(system=system)
        results[system] = stats
        # Print available stats keys for debugging
        print(f"\nStats keys for {system}:")
        print(list(stats.keys()))
    except Exception as e:
        print(f"Error running backtest for {system}: {e}")
        continue

# Print metrics for each system
for system, stats in results.items():
    print(f"\n{system} Metrics:")
    # Use initial cash for Start Balance since 'Equity Curve' is not available
    print(f"Start Balance: {1000000:.2f}")  # Use initial cash as fallback
    print(f"Final Balance: {stats['Equity Final [$]']:.2f}")
    print(f"Total Return: {stats['Return [%]']:.2f}%")
    print(f"Annual Return: {stats['Return (Ann.) [%]']:.2f}%")
    print(f"Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"Win Rate: {stats['Win Rate [%]']:.2f}%")
    print(f"Trades: {stats['# Trades']}")
    print(f"Avg Trade Duration: {stats['Avg. Trade Duration']}")

# Plot results
for system in systems:
    try:
        bt = Backtest(data, MultiStrategy, cash=1000000, commission=0.002, exclusive_orders=True)
        bt.run(system=system)
        bt.plot(filename=f"{system}_plot.html", open_browser=False)
    except Exception as e:
        print(f"Error plotting for {system}: {e}")