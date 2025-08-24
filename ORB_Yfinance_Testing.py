# Roadmap
# Use IB API (Replace yfinance)
# Fix Backtest Sell on next day
# Try VWAP+Volume

#Fixed last 3 and open 3 candlesticks
import yfinance as yf
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from ib_insync import *
import pytz

ticker = "SQQQ"
data = yf.download(ticker, period="60d", interval="15m")

# Ensure proper datetime index
data.index = pd.to_datetime(data.index)

# Drop multi-level column names (if present)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.droplevel(0)  # Drop ticker level

# Rename columns explicitly
data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

data.index = pd.to_datetime(data.index).tz_convert('US/Eastern')

# ✅ Filter data to start at 9:30 AM
data = data.between_time('09:30', '16:00')
data.index = data.index.tz_localize(None)


# ✅ **VWAP Calculation**
def calculate_vwap(data):
    data = data.copy()
    data['Average Price'] = (data['High'] + data['Low'] + data['Close']) / 3
    daily_groups = data.index.floor('D')  # Groups by full trading days

    # Cumulative VWAP Calculation
    data['Cumulative Volume'] = data.groupby(daily_groups)['Volume'].cumsum()
    data['VWAP'] = (data['Volume'] * data['Average Price']).groupby(daily_groups).cumsum() / data.groupby(daily_groups)['Volume'].cumsum()
    
    return data

# ✅ Apply VWAP Calculation
data = calculate_vwap(data)
data.dropna(inplace=True)
print(data)
class ORBStrategy(Strategy):
    take_profit = 0.01  # 2% take profit
    stop_loss = 0.01    # 1% stop loss
    trade_size = 400

    def init(self):
        self.current_day = None
        self.orb_high = None  # Highest price in the first 15 minutes
        self.orb_low = None   # Lowest price in the first 15 minutes
        self.breakout_triggered = False  # Track if breakout trade is taken
        self.entry_prices = []  # Store multiple entry prices
        self.last_candle_per_day = {}
        self.position_count = 0
        self.position_opened_today = False
        index_dates = self.data.index.date
        index_times = self.data.index.time
        for date in np.unique(index_dates):
            mask = index_dates == date
            times_for_day = self.data.index[mask]  # ✅ Use full timestamps instead of time()
            times_for_day_stamp=index_times[mask]

            if len(times_for_day_stamp) > 1:
                self.last_candle_per_day[date] = times_for_day_stamp[-2] # ✅ Full timestamp
    def next(self):
        today = self.data.index[-1].date()
        current_time = self.data.index[-1].time()
        last_candle_time = self.last_candle_per_day.get(today, None)
        orb_highs = []
        orb_lows = []


        # ✅ Reset at the start of a new day
        if self.current_day != today:
            self.current_day = today
            self.breakout_triggered = False
            self.entry_prices = []
            self.position_opened_today = False
            self.position_count = 0
            print(f"🔹 New day: {today}, Position Count: {self.position_count}")

            orb_highs = []
            orb_lows = []

        for i in range(len(self.data)):
            row_time = self.data.index[i].time()
            row_date = self.data.index[i].date()
            # ✅ Collect data from 9:30 AM to 9:45 AM
            if row_date == today and datetime.time(9, 30) <= row_time <datetime.time(9, 45) :
                orb_highs.append(self.data.High[i])
                orb_lows.append(self.data.Low[i])


        # ✅ Set ORB High & Low using collected values
        if orb_highs and orb_lows:  # Ensure lists are not empty
            self.orb_high = max(orb_highs)
            self.orb_low = min(orb_lows)
            self.orb_half_range = (self.orb_high - self.orb_low)

        else:
            self.orb_high = None
            self.orb_low = None
            print(f"⚠️ No ORB data available for {today}")

        # ✅ Ensure ORB levels are set before proceeding
        if self.orb_high is None or self.orb_low is None:
            return


        # ✅ Check breakout conditions
        # ✅ Skip trading in the first 15 minutes
        if current_time < datetime.time(9, 45):
            return  # Exit early, no trades before 9:45 AM

        if current_time == datetime.time(9, 50):
            print(f"📈 ORB Set for {today}: High={self.orb_high:.2f}, Low={self.orb_low:.2f}")

        # ✅ Check breakout conditions (only after 9:45 AM)
        if not self.breakout_triggered:
            if self.data.High[-1] > self.orb_high:
                entry_price = self.data.High[-1]
                self.buy(size=self.trade_size,limit=entry_price)
                self.position_count += self.trade_size
                self.entry_prices.append(self.data.High[-1])
                self.breakout_triggered = True
                self.position_opened_today = True
                print(f"🚀 ORB Long Entry at {self.data.index[-1]} (Price: {self.data.High[-1]:.2f}), Position Count: {self.position_count}")

            elif self.data.Low[-1] < self.orb_low:
                entry_price = self.data.Low[-1]
                self.sell(size=self.trade_size,limit=entry_price)
                self.position_count -= self.trade_size
                self.entry_prices.append(self.data.Low[-1])
                self.breakout_triggered = True
                self.position_opened_today = True
                print(f"🔻 ORB Short Entry at {self.data.index[-1]} (Price: {self.data.Low[-1]:.2f}), Position Count: {self.position_count}")


        # ✅ Apply TP/SL logic to all trades
        if self.position:    
            for entry in self.entry_prices[:]:
                if self.position_count>0:
                    take_profit_price = entry + (self.orb_half_range *1)
                    stop_loss_price = entry - (self.orb_half_range)
                else:  # Short position
                    take_profit_price = entry - (self.orb_half_range *1)
                    stop_loss_price = entry + (self.orb_half_range)

                #print(f"📊 {self.data.index[-1]} | Entry: {entry:.2f}, TP: {take_profit_price:.2f}, SL: {stop_loss_price:.2f}")

                if (self.position_count>0 and self.data.High[-1] >= take_profit_price):
                    print(f"🚀 Take Profit Hit! Exited at {self.data.index[-1]} (Price: {self.data.High[-1]:.2f})")
                    self.sell(size=self.trade_size)
                    self.entry_prices.remove(entry)
                    self.position_count -= self.trade_size
                elif (self.position_count<0 and self.data.Low[-1] <= take_profit_price):
                    print(f"🚀 Take Profit Hit! Exited at {self.data.index[-1]} (Price: {self.data.Low[-1]:.2f})")
                    self.buy(size=self.trade_size)
                    self.entry_prices.remove(entry)
                    self.position_count += self.trade_size
                elif (self.position_count>0 and self.data.Low[-1] <= stop_loss_price):
                    print(f"🔻 Stop Loss Hit! Exited at {self.data.index[-1]} (Price: {self.data.Low[-1]:.2f})")
                    self.sell(size=self.trade_size)
                    self.entry_prices.remove(entry)
                    self.position_count -= self.trade_size
                elif (self.position_count<0 and self.data.High[-1] >= stop_loss_price):
                    print(f"🔻 Stop Loss Hit! Exited at {self.data.index[-1]} (Price: {self.data.High[-1]:.2f})")
                    self.buy(size=self.trade_size)
                    self.entry_prices.remove(entry)
                    self.position_count += self.trade_size
        if self.position and current_time == last_candle_time and self.position_opened_today:
            self.position.close()
            self.position_closed_today = True
            self.position_count = 0  # Decrement position count
            print(f"🔻 Forced close at end of day {self.data.index[-1]} (Price: {self.data.Close[-1]:.2f}), Position Count: {self.position_count}")
 


# ✅ **Run Backtest**
bt = Backtest(data, ORBStrategy, cash=10000)
results = bt.run()


# ✅ **Plot Backtest Results**
bt.plot(plot_volume=False)
plt.show()
print(results)



