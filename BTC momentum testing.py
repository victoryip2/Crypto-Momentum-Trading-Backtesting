# Import libraries
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import datetime

# Define variables
symbols = ["ETH-USD"]
systems = ["Reversal", "Down_Reversal", "Momentum", "BuyHold"]
starting_balance = 10000

start = datetime.datetime(2022, 1, 1)
end = datetime.datetime(2025, 4, 4)
years = (end - start).days / 365.25

def backtest(symbol):
    # Load data from CSV
    price = pd.read_csv('C:/Users/victo/OneDrive/文件/Trading Bot/ETH_binance_data.csv')  # Adjust path if needed
    
    # Ensure Date column is in datetime format
    price['Date'] = pd.to_datetime(price['Date'])
    
    # Filter data within the specified date range
    price = price[(price['Date'] >= start) & (price['Date'] <= end)]
    
    # Set Date as index
    price = price.set_index('Date')
    
    # Drop unnecessary columns (Volume, Adj Close) and ensure correct column names
    price = price.drop(['Volume', 'Adj Close'], axis=1)
    
    # Ensure column names are as expected
    price.columns = ['Open', 'High', 'Low', 'Close']
    
    print(price)
    
    # Calculate inputs for strategy
    price['Reversal'] = (price.High < price.High.shift(1)) & (price.Low < price.Low.shift(1))
    price['Down_Reversal'] = (price.High < price.High.shift(1)) & (price.Low < price.Low.shift(1)) & (price.Close < price.Open)
    price['Momentum'] = (price.High > price.High.shift(1)) & (price.Low > price.Low.shift(1))
    price["BuyHold"] = True
    
    price['Reversal_Trade'] = (price.Reversal.shift(1) == True) & (price.High > price.High.shift(1))
    price['Down_Reversal_Trade'] = (price.Down_Reversal.shift(1) == True) & (price.High > price.High.shift(1))
    price['Momentum_Trade'] = (price.Momentum.shift(1) == True) & (price.High > price.High.shift(1))
    price["BuyHold_Trade"] = True
    
    for s in systems:
        if s == "BuyHold":
            price[f"{s}_Entry_Price"] = price.Close.shift(1)
        else:
            price[f"{s}_Entry_Price"] = np.where(price[f"{s}_Trade"] == True,
                                                np.where(price.Open > price.High.shift(1), price.Open, price.High.shift(1)), False)
        
        price[f"{s}_Ret"] = np.where(price[f"{s}_Trade"] == True, price.Close / price[f"{s}_Entry_Price"], 1)
        if s == "BuyHold":
            price[f"{s}_Ret"].iat[0] = 1
        price[f"{s}_Bal"] = starting_balance * price[f"{s}_Ret"].cumprod()
        
        price[f"{s}_Peak"] = price[f"{s}_Bal"].cummax()
        price[f"{s}_DD"] = price[f"{s}_Bal"] - price[f"{s}_Peak"]

    return price

results = []
for sym in symbols:
    result = backtest(sym)
    results.append(result)

plt.style.use('dark_background')
plt.rcParams["figure.figsize"] = (16,8)
plt.rcParams.update({'font.size': 18})

colours = ["tab:olive", "tab:blue", "tab:purple", "tab:orange"]

for c, s in enumerate(systems):
    plt.plot(results[0][f"{s}_Bal"], colours[c])

plt.legend(systems)

def get_metrics(system, data):
    metrics = {}
    sys_return = round(((data[f"{system}_Bal"].iloc[-1]/data[f"{system}_Bal"].iloc[0]) - 1) * 100, 2)
    sys_cagr = round(((((data[f"{system}_Bal"].iloc[-1]/data[f"{system}_Bal"].iloc[0])**(1/years))-1)*100), 2)
    sys_peak = data[f"{system}_Bal"].cummax()
    sys_dd = round(((data[f"{system}_DD"] / data[f"{system}_Peak"]).min()) * 100, 2)
    rod = sys_cagr / abs(sys_dd)
 
    win = (data.Close > data[f"{system}_Entry_Price"]) & (data[f"{system}_Trade"] == True)
    loss = (data.Close < data[f'{system}_Entry_Price']) & (data[f"{system}_Trade"] == True)
    signals = data[system].sum()
    trades_triggered = data[f"{system}_Trade"].sum()
    tim = round((trades_triggered / len(data)) * 100)
    rbe = round((sys_cagr / tim) * 100, 2)
    rbeod = rbe / abs(sys_dd)
    gaps = ((data[f"{system}_Trade"] == True) & (data.Open > data.High.shift(1))).sum()
    non_gaps = ((data[f"{system}_Trade"] == True) & (data.Open <= data.High.shift(1))).sum()
    wins = win.sum()
    losses = loss.sum()
    winrate = round(wins / (wins + losses) * 100, 2)
    
    move_size = np.where(data[f"{system}_Trade"] == True, data.Close - data[f"{system}_Entry_Price"], 0)
    avg_up_move = round(move_size[move_size > 0].mean(), 2)
    max_up_move = move_size.max()
    avg_down_move = round(abs(move_size[move_size < 0].mean()), 2)
    max_down_move = move_size.min()
    avg_rr = round(avg_up_move / avg_down_move, 2)

    metrics["Start_Balance"] = round(data[f"{system}_Bal"].iat[0], 2)
    metrics["Final_Balance"] = round(data[f"{system}_Bal"].iat[-1], 2)
    metrics["Total_Return"] = round(sys_return, 2)
    metrics["Annual_Return"] = round(sys_cagr, 2)
    metrics["Time_in_Market"] = round(tim, 2)
    metrics["Return_By_Exposure"] = rbe
    metrics["Max_Drawdown"] = round(sys_dd, 2)
    metrics["Return_Over_Drawdown"] = round(rod, 2)
    metrics["RBE_Over_Drawdown"] = round(rbeod, 2)
    metrics["Signals"] = round(signals, 2)
    metrics["Trades"] = round(trades_triggered, 2)
    metrics["Gap"] = round(gaps, 2)
    metrics["No_Gap"] = round(non_gaps, 2)
    metrics["Wins"] = round(wins, 2)
    metrics["Losses"] = round(losses, 2)
    metrics["Winrate"] = round(winrate, 2)
    metrics["Max_Win"] = round(max_up_move, 2)
    metrics["Max_Loss"] = round(max_down_move, 2)
    metrics["Avg_up_move"] = round(avg_up_move, 2)
    metrics["Avg_down_move"] = round(avg_down_move, 2)
    metrics["Avg_RR"] = avg_rr
    
    return metrics

full_metrics = {}
for count, res in enumerate(results):
    sys_metrics = {}
    for s in systems:
        sys_metrics.update({s: get_metrics(s, res)})
    sys_metrics_df = pd.DataFrame.from_dict(sys_metrics)
    full_metrics.update({symbols[count]: sys_metrics_df})

for m in full_metrics:
    print(m)
    print(full_metrics[m])

plt.show()