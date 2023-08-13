from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas_ta as ta
import pandas as pd
import numpy as np
from datetime import time, timedelta, datetime
import ccxt
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Fetch data from Binance
exchange = ccxt.binance({
    'options': {
        'defaultType': 'future'
    }
})

pair = 'DODOX/USDT'
candles= '5m'
starts_from='2023-01-01 00:00:00'

from_ts = exchange.parse8601(starts_from)
ohlcv = exchange.fetch_ohlcv(pair, timeframe=candles, since = from_ts,  limit = 1000)
ohlcv_list=[]
ohlcv_list.append(ohlcv)

while True:
    from_ts = ohlcv[-1][0]
    new_ohlcv = exchange.fetch_ohlcv(pair, candles, since=from_ts, limit=1000)
    ohlcv.extend(new_ohlcv)
    if len(new_ohlcv) != 1000:
        break

df = pd.DataFrame(ohlcv[:-1], columns= ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
data = df
data = data.set_index('timestamp')
print(data)
# Calculate SuperTrend
def superTrendDir(df, length=10, multiplier=3):
    return ta.supertrend(df["High"], df["Low"], df["Close"], length, multiplier)[f"SUPERTd_{length}_{multiplier}.0"]

def superTrendLabel(df, length=10, multiplier=3):
    return ta.supertrend(df["High"], df["Low"], df["Close"], length, multiplier)[f"SUPERT_{length}_{multiplier}.0"]

# Define Strategy
class SuperTrend(Strategy):
    st_length = 10
    st_multiplier = 3

    def init(self):
        self.supertrenddir = self.I(superTrendDir, self.data.df, length=self.st_length, multiplier=self.st_multiplier)
        self.supertrendLabel = self.I(superTrendLabel, self.data.df, length=self.st_length, multiplier=self.st_multiplier, overlay=True)

    def next(self):
        if not self.position.is_long and self.supertrenddir[-1] == 1:
            self.position.close()
            self.buy()
    
        elif not self.position.is_short and self.supertrenddir[-1] == -1:
            self.position.close()
            self.sell()

bt = Backtest(data, SuperTrend, cash=10000, commission=0, trade_on_close=True)
results = bt.run()
trades = results._trades

# Initialize variables
consecutive_losses = 0
losses_positions = {}
losses_dates = {}
consecutive_gains = {}

# Iterate through trades DataFrame
for i in range(1, len(trades)):
    if trades.iloc[i]['PnL'] < 0:
        consecutive_losses += 1
        if consecutive_losses == 1:  # first loss in a streak
            start_index = i
    else:
        if consecutive_losses > 1:  # if there was a streak of losses
            losses_positions[(start_index, i-1)] = consecutive_losses
            losses_dates[(trades.iloc[start_index]['EntryTime'], trades.iloc[i-1]['ExitTime'])] = consecutive_losses
            # Check if the trade's PnL is greater than 1.8R
            if trades.iloc[i]['PnL'] > 1.8 * trades.iloc[i]['ExitPrice'] - trades.iloc[i]['EntryPrice']:
                consecutive_gains[(start_index, i-1)] = consecutive_losses
        consecutive_losses = 0

# Add final streak of losses if it ended on the last trade and was more than one loss
if consecutive_losses > 1:
    losses_positions[(start_index, i)] = consecutive_losses
    losses_dates[(trades.iloc[start_index]['EntryTime'], trades.iloc[i]['ExitTime'])] = consecutive_losses
    if trades.iloc[i]['PnL'] > 1.8 * trades.iloc[i]['ExitPrice'] - trades.iloc[i]['EntryPrice']:
        consecutive_gains[(start_index, i)] = consecutive_losses

# Calculate the average and maximum number of consecutive losses
avg_consecutive_losses = sum(losses_positions.values()) / len(losses_positions) if losses_positions else 0
max_consecutive_losses = max(losses_positions.values()) if losses_positions else 0
total_consecutive_loss_instances = len(losses_positions)
consecutive_gains_count = len(consecutive_gains)

print(f"Consecutive loss positions: {losses_positions}")
print(f"Consecutive loss dates and counts: {losses_dates}")
print(f"Average consecutive losses: {avg_consecutive_losses}")
print(f"Maximum consecutive losses: {max_consecutive_losses}")
print(f"Total number of instances of consecutive losses: {total_consecutive_loss_instances}")
print(f"Number of times 1.8R was achieved after consecutive losses: {consecutive_gains_count}")
