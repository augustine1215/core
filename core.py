import json
import time
from datetime import datetime, timedelta

from logger import get_logger
from utils import format_currency
from vbs import VBS

import pause
import pyupbit


logger = get_logger()
    

class Core(object):
    def __init__(self, ticker='KRW-BTC', access='', secret=''):
        self.exchange = pyupbit.Upbit(access=access, secret=secret)
        self.quotation = pyupbit
        self.ticker = ticker
        self.vbs = VBS(self.ticker)
        self.watch_count = 0
        try:
            self.load()
        except:
            # State
            self.phase = self.buy
            self.order_uuid = None
            self.acc_yield_rate = 1
            self.balance = self.exchange.get_balance('KRW')
            self.next_reset = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            self.save()

    def load(self):
        with open('core.json', 'r', encoding='utf-8') as jf:
            save = json.load(jf)
        for k, v in save.items():
            if k == 'phase':
                self.phase = getattr(self, v)
            elif k == 'next_reset':
                setattr(self, k, datetime.strptime(v, '%Y-%m-%d %H:%M:%S'))
            else:
                setattr(self, k, v)
        logger.info('LOAD - Core object loaded from core.json')

    def to_dict(self):
        return {
            'phase': self.phase.__name__,
            'order_uuid': self.order_uuid,
            'acc_yield_rate': self.acc_yield_rate,
            'balance': self.balance,
            'next_reset': self.next_reset.strftime('%Y-%m-%d %H:%M:%S')
        }

    def save(self):
        save = self.to_dict()
        with open('core.json', 'w', encoding='utf-8') as jf:
            jf.write(json.dumps(save, indent=4))
        logger.info('SAVE - Core object saved to core.json')

    def buy(self):
        if self.order_uuid is not None:
            raise Exception(F'An order is already processing, order_uuid:{self.uuid}')
        target_price = self.vbs.get_target_price()
        curr_price = self.quotation.get_current_price(self.ticker)
        balance = self.exchange.get_balance('KRW')
        volume = (0.9995 * balance) / target_price
        if curr_price >= target_price:
            logger.info(F'BUY - Buying {volume} amount of {self.ticker} at {format_currency(target_price)}')
            order = self.exchange.buy_limit_order(self.ticker, target_price, volume)
            if 'uuid' in order:
                self.watch_count = 0
                self.order_uuid = order['uuid']
                self.phase = self.confirm_buy
            else:
                logger.warning(F'BUY - Order failed, response: {order}')
        else:
            if self.watch_count % 300 == 0:
                logger.info(F'BUY - Waited {self.watch_count} iterations for {format_currency(target_price)}, curr_price:{format_currency(curr_price)}, diff:{format_currency(target_price - curr_price)}')
            self.watch_count += 1
        return None
            
    def confirm_buy(self):
        if self.order_uuid is not None:
            raise Exception('There is no buy order to confirm')
        order = self.exchange.get_order(self.order_uuid)
        if 'state' in order:
            state = order['state']
            if state == 'done':
                logger.info(F'CONFIRM BUY - order {self.order_uuid} has been closed')
                self.order_uuid = None
                self.phase = self.sleep
                return {
                    'phase': 'CONFIRM_BUY',
                    'order': order
                }
        return None

    def sleep(self):
        self.next_reset = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        logger.info(F'Pausing until {self.next_reset}')
        pause.until(self.next_reset)
        self.phase = self.sell
        return None

    def sell(self):
        if self.order_uuid is not None:
            raise Exception(F'An order is already processing, order_uuid:{self.uuid}')
        volume = self.exchange.get_balance(self.ticker)
        order = self.exchange.sell_market_order(self.ticker, volume)
        logger.info(F'SELL - Selling {volume} amount of {self.ticker} at market price (~{format_currency(self.quotation.get_current_price(self.ticker))})')
        if 'uuid' in order:
            self.order_uuid = order['uuid']
            self.phase = self.confirm_sell
        else:
            logger.warning(F'SELL - Order failed, response: {order}')
        return None

    def confirm_sell(self):
        if self.order_uuid is not None:
            raise Exception('There is no sell order to confirm')
        order = self.exchange.get_order(self.order_uuid)
        if 'state' in order:
            state = order['state']
            if state == 'done':
                new_balance = self.exchange.get_balance()
                yield_rate = new_balance / self.balance
                percentage = (1 - round_up(yield_rate, 2)) * 100
                self.acc_yield_rate *= yield_rate
                acc_percentage = (round_up(acc_yield_rate, 2)) * 100
                self.balance = new_balance
                logger.info(F'CONFIRM SELL - order {self.order_uuid} has been closed, yield_rate:{percentage}%, acc_yield_rate:{acc_percentage}%, balance:{new_balance}')
                self.order_uuid = None
                self.phase = self.buy
                return {
                    'phase': 'CONFIRM_SELL',
                    'order': order,
                    'yield_rate': yield_rate,
                    'acc_yield_rate': self.acc_yield_rate
                }
        return None

    def update(self):
        if datetime.now() >= self.next_reset:
            self.vbs = VBS(self.ticker)
        # time.sleep(1)
        return self.phase()
    

if __name__ == '__main__':
    core = Core()