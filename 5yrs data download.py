import datetime
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from ib_insync import *
import pytz
from dateutil.relativedelta import relativedelta

# ✅ Connect to Interactive Brokers
ib = IB()
ib.TimezoneTWS = pytz.timezone('US/Eastern')
ib.connect('127.0.0.1', 7497, clientId=1)  # 7497 = Paper Trading, 7496 = Live Trading

# ✅ Define Contract
contract = Stock("TQQQ", "SMART", "USD")
ib.qualifyContracts(contract)

# ✅ Function to Fetch Historical Data in Chunks
def fetch_historical_data_chunks(contract, end_date, years=5, chunk_days=365):
    all_data = []
    current_end_date = end_date

    for _ in range(years):
        # Calculate start date for the chunk
        start_date = current_end_date - relativedelta(days=chunk_days)

        # Fetch data for the chunk
        bars = ib.reqHistoricalData(
            contract,
            endDateTime=current_end_date.strftime('%Y%m%d %H:%M:%S US/Eastern'),
            durationStr=f'{chunk_days} D',
            barSizeSetting='15 mins',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        # Convert to DataFrame and append
        chunk_data = pd.DataFrame(bars)
        all_data.append(chunk_data)

        # Update end date for the next chunk
        current_end_date = start_date

        # Sleep to respect IB API rate limits (optional, adjust as needed)
        ib.sleep(10)  # 10 seconds delay between requests

    # Combine all chunks into a single DataFrame
    combined_data = pd.concat(all_data)
    combined_data.set_index("date", inplace=True)
    combined_data.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)

    # Ensure proper datetime index
    combined_data.index = pd.to_datetime(combined_data.index).tz_convert('US/Eastern')
    combined_data = combined_data.between_time('09:30', '16:00')  # Filter trading hours
    combined_data.index = combined_data.index.tz_localize(None)  # Remove timezone for backtesting

    return combined_data

# ✅ Fetch 5 Years of Data
end_date = datetime.datetime.now(pytz.timezone('US/Eastern'))  # Current date as end point
data = fetch_historical_data_chunks(contract, end_date, years=5)

# ✅ Save to CSV
csv_file = "TQQQ_15min_5yr_data.csv"
data.to_csv(csv_file)
print(f"Data saved to {csv_file}")
