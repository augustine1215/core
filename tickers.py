import os
import json

with open('markets.json', 'r', encoding='utf-8') as f:
    markets_json = json.load(f)

TICKERS = [market for market in markets_json]

if __name__ == '__main__':
    print(TICKERS)