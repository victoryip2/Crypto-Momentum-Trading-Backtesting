#import libraries
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import datetime
from ib_insync import *
import logging
import pytz

# Set up logging
logging.basicConfig(
    filename='bnb_backtest.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

#define variables
symbols = ["BTC-USD"]
systems = ["Reversal", "Down_Reversal", "Momentum", "BuyHold"]
starting_balance = 10000

start = datetime.datetime(2020, 1, 1)
end = datetime.datetime(2025, 4, 4)
years = (end - start).days / 365.25

# Connect to IBKR paper trading account
ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
    logging.info("Connected to IBKR paper trading account")
    print("Connected to IBKR paper trading account")
except Exception as e:
    print(f"Failed to connect to IBKR: {e}")
    logging.error(f"Failed to connect to IBKR: {e}")
    exit(1)

def backtest(symbol):
    # Define crypto contract for BNB-USD
    contract = Crypto(symbol.replace("-USD", ""), "PAXOS", "USD")
    contracts = ib.qualifyContracts(contract)
    if not contracts:
        print(f"Failed to qualify contract for {symbol}")
        logging.error(f"Failed to qualify contract for {symbol}")
        exit(1)
    logging.info(f"Qualified contract: {contracts}")

    # Fetch historical data
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='20221231 23:59:00 US/Eastern',
        durationStr='1 Y',  # Cover 2020-01-01 to 2025-04-04
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,  # Crypto trades 24/7
        formatDate=1
    )
    if not bars:
        print(f"No historical data returned for {symbol}")
        logging.error(f"No historical data returned for {symbol}")
        exit(1)
    logging.info(f"Retrieved {len(bars)} bars for {symbol}")

    # Convert to DataFrame
    price = pd.DataFrame(bars)
    if price.empty:
        print(f"DataFrame is empty after conversion for {symbol}")
        logging.error(f"DataFrame is empty after conversion for {symbol}")
        exit(1)
    
    # Format data
    price.set_index("date", inplace=True)
    price.index = pd.to_datetime(price.index)
    price.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
    price = price[["Open", "High", "Low", "Close"]]  # Drop Volume as in original
    price = price.reset_index()  # Match original code's reset_index

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

# Disconnect from IBKR
ib.disconnect()
logging.info("Disconnected from IBKR")

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