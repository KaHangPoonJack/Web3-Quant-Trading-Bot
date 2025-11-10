import requests
import time
import hmac
import hashlib
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import os
import threading
from flask import Flask, render_template_string
import plotly.graph_objects as go
import gzip
import io
from urllib.parse import urlparse
# ================================
# Configuration and Setup
# ================================

BASE_URL = "https://mock-api.roostoo.com"
API_KEY = "R5tY9uIpcN3vB1kMH7qD2wXaL0oG6eZfsP8jK4QraV1mT7UyxC5nF3WdJ2yS8lGo"
SECRET_KEY = "L9ZxCV1bN3mQwE5rT7yUiP9oA1sDdF3gJ5hKlZ7xC9vBnM1qW3eRtY5uI7oP"
HORUS_URL = "https://api-horus.com"
HORUS_API_KEY = "dcca142de11f3c3a6db14d91757a8ed2dc9bd8ebbd92103d65946deecf82e9ee"

# --- STATE ---
state = {"equity": 10000, "peak": 10000, "pos": 0, "entry": 0, "trades_today": 0, "last_date": "", "prices": []}
price_data_20high = []
price_data_15min = []
last_second = -1
currency = "ETH/USD"
bars = []
TrueRangeList = []
atr_averageList = []

high_bar_20Trigger = False
ATR_trigger = False
RSI_trigger = False
Have_order = False

# ------------------------------
# Utility Functions
# ------------------------------

def _get_timestamp():
    """Return a 13-digit millisecond timestamp as string."""
    return str(int(time.time() * 1000))


def _get_signed_headers(payload: dict = {}):
    """
    Generate signed headers and totalParams for RCL_TopLevelCheck endpoints.
    """
    payload['timestamp'] = _get_timestamp()
    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)

    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        total_params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'RST-API-KEY': API_KEY,
        'MSG-SIGNATURE': signature
    }

    return headers, payload, total_params


# ------------------------------
# Public Endpoints
# ------------------------------

def check_server_time():
    """Check API server time."""
    url = f"{BASE_URL}/v3/serverTime"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error checking server time: {e}")
        return None


def get_exchange_info():
    """Get exchange trading pairs and info."""
    url = f"{BASE_URL}/v3/exchangeInfo"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting exchange info: {e}")
        return None


def get_ticker(pair=None):
    """Get ticker for one or all pairs."""
    url = f"{BASE_URL}/v3/ticker"
    params = {'timestamp': _get_timestamp()}
    if pair:
        params['pair'] = pair
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting ticker: {e}")
        return None


# ------------------------------
# Signed Endpoints
# ------------------------------

def get_balance():
    """Get wallet balances (RCL_TopLevelCheck)."""
    url = f"{BASE_URL}/v3/balance"
    headers, payload, _ = _get_signed_headers({})
    try:
        res = requests.get(url, headers=headers, params=payload)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting balance: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def get_pending_count():
    """Get total pending order count."""
    url = f"{BASE_URL}/v3/pending_count"
    headers, payload, _ = _get_signed_headers({})
    try:
        res = requests.get(url, headers=headers, params=payload)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting pending count: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def place_order(pair_or_coin, side, quantity, price=None, order_type=None):
    """
    Place a LIMIT or MARKET order.
    """
    url = f"{BASE_URL}/v3/place_order"
    pair = f"{pair_or_coin}/USD" if "/" not in pair_or_coin else pair_or_coin

    if order_type is None:
        order_type = "LIMIT" if price is not None else "MARKET"

    if order_type == 'LIMIT' and price is None:
        print("Error: LIMIT orders require 'price'.")
        return None

    payload = {
        'pair': pair,
        'side': side.upper(),
        'type': order_type.upper(),
        'quantity': str(quantity)
    }
    if order_type == 'LIMIT':
        payload['price'] = str(price)

    headers, _, total_params = _get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error placing order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def query_order(order_id=None, pair=None, pending_only=None):
    """Query order history or pending orders."""
    url = f"{BASE_URL}/v3/query_order"
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair:
        payload['pair'] = pair
        if pending_only is not None:
            payload['pending_only'] = 'TRUE' if pending_only else 'FALSE'

    headers, _, total_params = _get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def cancel_order(order_id=None, pair=None):
    """Cancel specific or all pending orders."""
    url = f"{BASE_URL}/v3/cancel_order"
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair:
        payload['pair'] = pair

    headers, _, total_params = _get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error canceling order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None

# ================================
# TECHNICAL INDICATORS
# ================================



# ================================
# MAIN
# ================================

while True:
    time_frame = 15 #15min
    now_datetime = datetime.now()
    ATR_period = 5
    now_UTCtime = int(time.time())
    if bars:    
        last_close = bars[-1]["close"]
    else:
        last_close = None
    # make bar
    if now_UTCtime != last_second:
        last_second = now_UTCtime
        current_price = get_ticker(currency)["Data"][currency]["LastPrice"]
        price_data_15min.append(current_price)
        if len(price_data_15min) > 900:
            price_data_15min = price_data_15min[-900:]
        if len(price_data_15min) == 900 and \
        now_datetime.minute % time_frame == 0 and \
        now_datetime.second == 0:
            high = max(price_data_15min)
            low = min(price_data_15min)
            true_range = max(high, last_close) - min(low, last_close)
            bar = {"high": high,
                   "low": low,
                   "close": current_price,
                   "TrueRange": true_range}
            last_close = current_price
            bars.append(bar)
            TrueRangeList.append(true_range)
            price_data_15min = []
            print(bars)
    
    if now_datetime.minute % time_frame == 0 and now_datetime.second == 0:
        # calculate the 20 bar highest    
        high_price_15min = bars[-1]["high"]
        price_data_20high.append(high_price_15min)
        if len(price_data_20high) > 21:
            price_data_20high = price_data_20high[-21:]
        if len(price_data_20high) == 21:
            highest_20bar = max(price_data_20high[-21:-1])
        print ("20 bar high: ", price_data_20high)
        

        # caculate atr14
        if len(TrueRangeList) > ATR_period + 1:
            TrueRangeList = TrueRangeList[-6:]
        if len(TrueRangeList) == ATR_period + 1:
            atr = np.mean(TrueRangeList[-6: -1])
            atr_averageList.append(atr)
            if len(atr_averageList) > 5:
                atr_averageList = atr_averageList[-5:]
            if len(atr_averageList) == 5:
                ATR_5_avg = np.mean(atr_averageList[-5:])
            print ("ATR_5_avg", ATR_5_avg)
        print ("Average True Range", atr)

        # caculate CE


        # caculate RSI
        if len(bars) > 14:
            closes = [bar["close"] for bar in bars[-15:]]
            deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
            positive_sum = sum(dp for dp in deltas if dp > 0)
            negative_sum = sum(abs(dp) for dp in deltas if dp < 0)
            Avg_gain = positive_sum / 14
            Avg_loss = negative_sum / 14
            RSI = 100 - (100/(1 + (Avg_gain / Avg_loss)))
        print (RSI)

    if current_price > highest_20bar:
        high_bar_20Trigger = True
    else:
        high_bar_20Trigger = False
    if atr > (1.5 * ATR_5_avg):
        ATR_trigger = True
    else:
        ATR_trigger = False
    if RSI < 75:
        RSI_trigger = True
    else:
        RSI_trigger = False

    if high_bar_20Trigger and ATR_trigger and RSI_trigger:
        usd_free = get_balance().get('SpotWallet', {}).get('USD', {}).get('Free', 0)
        print("Previous USD Free Balance:", usd_free)
        amount = usd_free / current_price
        place_order(currency, "BUY", amount)
        enter_price = current_price
        enter_amount = amount
        print("Enter Price: ", enter_price, "Enter Amount: ", enter_amount)
        print(get_balance())
        Have_order = True
        ATR_trigger = False
        high_bar_20Trigger = False
        RSI_trigger = False
    if Have_order:
        order_PL = ((current_price - enter_price)/enter_price) * 100
        if order_PL <= -2:
            place_order(currency, "SELL", enter_amount)
            print (get_balance())
        if order_PL >= 4:
            place_order(currency, "SELL", enter_amount)
            print (get_balance())

    time.sleep(1)
