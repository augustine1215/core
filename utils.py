from datetime import datetime
import math


def epoch_time_now():
    return int(datetime.datetime.now().timestamp())


def average(lst):
    return sum(lst)/len(lst)


def format_currency(n):
    return '{:,.0f}'.format(n)


def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


def is_date(datestring):
    try:
        datetime.strptime(datestring, '%Y-%m-%d %H:%M:%S')
        return True
    except:
        return False

