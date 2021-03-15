import time
from utils import average, round_up, is_date

import pandas
import pyupbit
from tqdm import tqdm


def correct_price(price):
    if price >= 2000000:
        return price - (price % 1000)
    elif price >= 1000000:
        return price - (price % 500)
    elif price >= 500000:
        return price - (price % 100)
    elif price >= 100000:
        return price - (price % 50)
    elif price >= 10000:
        return price - (price % 10)
    elif price >= 1000:
        return price - (price % 5)
    elif price >= 100:
        return price - (price % 1)
    elif price >= 10:
        return price - (price % 0.1)
    elif price >= 0:
        return price - (price % 0.01)


class VBS(object):
    def __init__(self, ticker, start_time=None, end_time=None, interval='day', scope=20):
        today = pandas.Timestamp.today().normalize() + pandas.Timedelta(hours=9)
        if start_time is None:
            start_time = (today - pandas.Timedelta(days=scope+1)).strftime('%Y-%m-%d %H:%M:%S')
        if end_time is None:
            end_time = today.strftime('%Y-%m-%d %H:%M:%S')

        self._validate_params(ticker, start_time, end_time, interval)
        self.ticker = ticker
        self.start_time = pandas.Timestamp(start_time)
        self.end_time = pandas.Timestamp(end_time)
        self.interval = interval
        self.scope = scope
        self.df = self._load_dataframe()
        self._validate_self()
    
    def _validate_index(self, idx):
        if idx > len(self.df) - 1 or idx < 0:
            raise IndexError(F'idx {idx} is greater than {len(self.df) - 1} or less than 0')

    def _validate_params(self, ticker, start_time, end_time, interval):
        if not is_date(start_time) or not is_date(end_time):
            raise ValueError(F'start_time {start_time} or end_time {end_time} is not a valid datestring')
        if not interval in ['day', 'week', 'minute1', 'minute3', 'minute5', 'minute30', 'minute60', 'minute240']:
            raise ValueError(F'Interval {interval} is not a valid interval')
    
    def _validate_self(self):
        if self.start_time > self.start_time:
            raise ValueError(F'start_time {self.start_time} is later than end_time {self.end_time}')
        if self.end_time > pandas.Timestamp.today():
            raise ValueError(F'end_time cannot be later than {pandas.Timestamp.today()}')
        if len(self.df) < self.scope:
            raise Exception(F'Not enough market data for {self.ticker}, {len(self.df)} < {self.scope}')

    def _load_dataframe(self, count=200):
        final_df = None
        continuation_time = self.end_time
        while True:
            result = pyupbit.get_ohlcv(ticker=self.ticker, interval=self.interval, count=count, to=continuation_time)
            try:
                first_row = result.iloc[0]
            except:
                break
            continuation_time = first_row.name - pandas.Timedelta(days=1)
            final_df = result if final_df is None else pandas.concat([result, final_df])
            if self.start_time in result.index.values or len(result) < count:
                final_df = final_df.loc[self.start_time:]
                break
            time.sleep(0.1)
        final_df.index.rename('timestamp', inplace=True)
        return final_df
    
    def get_idx_by_date(self, datestring):
        if not is_date(datestring):
            raise ValueError(F'datestring {datestring} is not a valid datestring')
        return self.df.index.get_loc(pandas.Timestamp(datestring))

    def get_moving_average(self, interval, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        if idx < interval:
            raise ValueError(F'Moving average interval is greater than the given subset; idx:{idx}')
        last = idx - 1
        first = last - interval
        close_prices = [self.df.iloc[i].close for i in range(last, first, -1)]
        return average(close_prices)

    def get_moving_average_score(self, reference_price, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        if self.scope <= 3:
            raise Exception(F'scope {self.scope} is too small for moving average score calcuation')
        score = 0
        moving_averages = [self.get_moving_average(i, idx) for i in range(3, self.scope+1)]
        for ma in moving_averages:
            if reference_price > ma:
                score += 1/len(moving_averages)
        return score

    def get_volatility_control_ratio(self, portfolio_size, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        target_volatility = 0.02
        prev_day = self.df.iloc[idx - 1]
        curr_day = self.df.iloc[idx]
        prev_volatility = ((prev_day.high - prev_day.low) / curr_day.close)
        return target_volatility/prev_volatility/portfolio_size

    def get_noise_ratio(self, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        day = self.df.iloc[idx]
        open_close = day.open - day.close
        high_low = day.high - day.low
        if high_low == 0 or open_close == 0:
            return 1
        return 1 - (abs(open_close/high_low))

    def get_k_value(self, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        if idx < self.scope:
            raise ValueError(F'K value calculation requires at least {self.scope} candles; idx:{idx}, self.scope:{self.scope}')
        last = idx - 1
        first = last - self.scope
        noise_ratios = [self.get_noise_ratio(i) for i in range(last, first, -1)]
        return average(noise_ratios)
    
    def get_target_price(self, idx=None):
        if idx is None:
            idx = len(self.df) - 1
        self._validate_index(idx)
        curr_day = self.df.iloc[idx]
        prev_day = self.df.iloc[idx-1]
        prev_day_range = prev_day.high - prev_day.low
        k_value = self.get_k_value(idx)
        return correct_price(curr_day.open + (prev_day_range * k_value))
    
    def simple_yield(self):
        x = []
        y = []
        start_price = self.df.iloc[0].close
        for idx in range(0, len(self.df)):
            today = self.df.iloc[idx]
            y.append(round_up((today.close/start_price)*100, 2))
            x.append(today.name)
        return x, y

    def backtest(self):
        x = []
        y = []
        buy = False
        buy_price = 0
        acc_yield_rate = 1
        print(F'Running backtest for {self.ticker} from {self.start_time} to {self.end_time}')
        for idx in tqdm(range(self.scope, len(self.df)), bar_format='{l_bar}{bar:20}{r_bar}{bar:-10b}'):
            today = self.df.iloc[idx]

            ### DIVERSIFIED INVESTMENT LOGIC ###
            """
            ma_score = self.get_moving_average_score(today.open, idx)
            vc_ratio = self.get_volatility_control_ratio(1, idx)
            betting_ratio = ma_score * vc_ratio
            """
            ####################################

            ######### BUY / SELL LOGIC #########
            target_price = self.get_target_price(idx)
            if buy == True:
                buy = False
                sell_price = today.open
                yield_rate = (sell_price/buy_price) * 0.9990
                acc_yield_rate *= yield_rate
            if buy == False and today.high >= target_price:
                buy = True
                buy_price = target_price
            x.append(today.name)
            y.append((acc_yield_rate)*100)
            ####################################

        print(F'{round_up(acc_yield_rate*100, 2)}% yield')
        return x, y


if __name__ == '__main__':
    # Get today's target KRW price for Bitcoin
    vbs = VBS('KRW-BTC')
    print(F'Today\'s KRW-BTC target price = {vbs.get_target_price()}')

    # Backtesting Example
    import matplotlib.pyplot as plt

    start_time = '2021-02-24 09:00:00'
    end_time = '2021-03-15 09:00:00'
    tickers = ['KRW-XRP'] # ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-NPXS', 'KRW-BORA']

    for ticker in tickers:
        vbs = VBS(ticker, start_time=start_time, end_time=end_time, interval='day', scope=20)
        # result = vbs.backtest()
        simple = vbs.simple_yield()
        plt.clf()
        # plt.plot(result[0], result[1], label=F'{ticker}, 20')
        plt.plot(simple[0], simple[1], label=F'{ticker}, simple')
        plt.xticks(rotation='45')
        plt.legend()
        plt.grid()
        plt.xlabel('Date')
        plt.ylabel('Total Yield (%)')
        plt.savefig(F'{ticker}.png', dpi=200, bbox_inches='tight')
