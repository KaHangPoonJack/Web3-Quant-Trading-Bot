import requests
import time
import hmac
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from flask import Flask, render_template_string
import plotly.graph_objects as go
from urllib.parse import urlparse
import math
# ================================
# Configuration and Setup
# ================================

BASE_URL = "https://mock-api.roostoo.com"
API_KEY = "R5tY9uIpcN3vB1kMH7qD2wXaL0oG6eZfsP8jK4QraV1mT7UyxC5nF3WdJ2yS8lGo"
SECRET_KEY = "L9ZxCV1bN3mQwE5rT7yUiP9oA1sDdF3gJ5hKlZ7xC9vBnM1qW3eRtY5uI7oP"
HORUS_URL = "https://api-horus.com"
HORUS_API_KEY = "dcca142de11f3c3a6db14d91757a8ed2dc9bd8ebbd92103d65946deecf82e9ee"
BINANCE_URL = "wss://stream.binance.com:9443"

# --- STATE ---
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
use_close = True
long_stop = None
short_stop = None
long_stop_prev = None
short_stop_prev = None
dir = 1
prev_dir = None  # To track for signals
buy_signal = False
sell_signal = False

st_factor = 3
st_atr_period = 10
st_atr = 0.0
up = 0.0
down = 0.0
prev_up = 0.0
prev_down = 0.0
supertrend = 0.0
prev_supertrend = 0.0
is_uptrend = False

time_frame = 15
ATR_period = 22
highest_20bar = 0
ATR_5_avg = 0
atr = 0
RSI = 0
enter_amount = 0
enter_price = 0
current_price = 0
order_PL = 0

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

def place_order_with_retry(pair, side, quantity, max_retries=5, delay_base=1.0):

    for attempt in range(1, max_retries + 1):
        print(f"Attempt {attempt} to place {side} order for {quantity} {pair}")
        response = place_order(pair, side, quantity)
        
        # Check if API returned a valid response
        if response is None:
            print(f" Attempt {attempt}: No response from server.")
        else:
            # Success condition per API docs: Success == true AND ErrMsg == ""
            if response.get("Success", False) and response.get("ErrMsg", "") == "":
                print(f" Order succeeded on attempt {attempt}: {response}")
                return response
            else:
                err_msg = response.get("ErrMsg", "Unknown error")
                print(f" Attempt {attempt} failed: {err_msg}")
                print(f"Full response: {response}")

        # Wait before retrying (exponential backoff)
        if attempt < max_retries:
            sleep_time = delay_base * (2 ** (attempt - 1))
            print(f" Retrying in {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)

    print(f" All {max_retries} attempts to place {side} order failed.")
    return None

# ================================
# TECHNICAL INDICATORS
# ================================



# ================================
# MAIN
# ================================
next_run = time.time()
while True:
    now_datetime = datetime.now()
    now_UTCtime = int(time.time())
    if bars:    
        last_close = bars[-1]["close"]
    else:
        last_close = 0
    # make bar
    if now_UTCtime != last_second:
        last_second = now_UTCtime
        ticker_response = get_ticker(currency)
        if ticker_response is None:
            print(now_datetime, "Failed to fetch ticker data. Skipping this cycle.")
            time.sleep(0.5)
            continue
        try:
            current_price = ticker_response["Data"][currency]["LastPrice"]
        except (KeyError, TypeError) as e:
            print(now_datetime, f"Unexpected ticker response format: {ticker_response}, error: {e}")
            time.sleep(0.5)
            continue
        price_data_15min.append(current_price)
        if len(price_data_15min) > (60 * time_frame):
            price_data_15min = price_data_15min[-(60 * time_frame):]
        if len(price_data_15min) >= (60 * time_frame) and \
            now_datetime.minute % time_frame == 0:
            high = max(price_data_15min)
            low = min(price_data_15min)
            if bars:
                true_range = max(high - low, abs(high - last_close), abs(low - last_close))
            else:
                true_range = high - low
            bar = {"high": high,
                   "low": low,
                   "close": current_price,
                   "TrueRange": true_range}
            bars.append(bar)
            prev_price = last_close
            last_close = current_price
            TrueRangeList.append(true_range)
            price_data_15min = []
            print(now_datetime,": ", bar)
    
    if now_datetime.minute % time_frame == 0 and now_datetime.second == 0 and bars:
        # caculate atr14
        if len(TrueRangeList) > ATR_period + 1:
            TrueRangeList = TrueRangeList[-23:]
        if len(TrueRangeList) == ATR_period + 1:
            atr = np.mean(TrueRangeList[-23: -1])
            atr_averageList.append(atr)
            if len(atr_averageList) > 5:
                atr_averageList = atr_averageList[-5:]
            if len(atr_averageList) == 5:
                ATR_5_avg = np.mean(atr_averageList[-5:])
                print (now_datetime, " ATR_5_avg: ", ATR_5_avg)
            print (now_datetime, " Average True Range: ", atr)

        # caculate CE
        if len(bars) >= ATR_period:
            if use_close:
                closes = [bar["close"] for bar in bars[-ATR_period:]]
                highest = max(closes)
                lowest = min(closes)
            else:
                highs = [bar["high"] for bar in bars[-ATR_period:]]
                lows = [bar["low"] for bar in bars[-ATR_period:]]
                highest = max(highs)
                lowest = min(lows)
            ce_atr = 3.5 * atr
            long_stop = highest - ce_atr
            short_stop = lowest + ce_atr
            if long_stop_prev is None:
                # Initial setup
                long_stop_prev = long_stop
                short_stop_prev = short_stop
            else:
                # Trail using previous close
                close_prev = bars[-2]["close"]
                if close_prev > long_stop_prev:
                    long_stop = max(long_stop, long_stop_prev)
                if close_prev < short_stop_prev:
                    short_stop = min(short_stop, short_stop_prev)
            # Calculate direction using current close and previous stops
            current_close = bars[-1]["close"]
            prev_dir = dir
            if current_close > short_stop:
                dir = 1
            elif current_close < long_stop:
                dir = -1
            else:
                dir = prev_dir
            # Update prev stops for next bar
            long_stop_prev = long_stop
            short_stop_prev = short_stop
            # Generate signals
            buy_signal = (dir == 1) and (prev_dir == -1)
            sell_signal = (dir == -1) and (prev_dir == 1)

        # caculate Supertrend
        if len(TrueRangeList) >= st_atr_period:
            # Note: Including current TR in the mean, unlike your ATR which excludes it. Adjust if needed.
            tr_list = TrueRangeList[-st_atr_period:]
            st_atr = np.mean(tr_list)
    
            high = bars[-1]["high"]
            low = bars[-1]["low"]
            close = bars[-1]["close"]
            hl2 = (high + low) / 2
    
            up = hl2 - (st_factor * st_atr)
            down = hl2 + (st_factor * st_atr)
    
            if prev_up == 0:  # Initial setup on first calculation
                prev_up = up
                prev_down = down
                prev_supertrend = up  # Arbitrary start, as in standard Supertrend
            else:
                close_prev = bars[-2]["close"]
        
                # Trail up
                if close_prev > prev_up:
                    up = max(up, prev_up)
        
                # Trail down
                if close_prev < prev_down:
                    down = min(down, prev_down)
        
                # Determine supertrend
                if prev_supertrend == prev_up:
                    supertrend = up if close > prev_down else down
                else:
                    supertrend = down if close < prev_up else up
    
            is_uptrend = supertrend < close  # Uptrend if supertrend below price

            # Update prev for next bar
            prev_up = up
            prev_down = down
            prev_supertrend = supertrend

    if buy_signal and not Have_order and is_uptrend:
        balance_info = get_balance()
        if balance_info is None:
            print(now_datetime, " Failed to fetch balance. Skipping buy.")
        else:
            usd_free = float(balance_info.get('SpotWallet', {}).get('USD', {}).get('Free', 0))
            print(now_datetime, "USD Free Balance:", usd_free)
            if usd_free <= 0:
                print(now_datetime, " Insufficient USD balance.")
            else:
                amount = usd_free / current_price
                int_amount = round(amount, 3) - 0.005
                if int_amount <= 0:
                    print(now_datetime, " Calculated buy amount is non-positive.")
                else:
                    order_reply = place_order_with_retry(currency, "BUY", int_amount, max_retries=5)
                    if order_reply is not None:
                    # Extract filled price and quantity from OrderDetail if available
                        order_detail = order_reply.get("OrderDetail", {})
                        enter_price = order_detail.get("FilledAverPrice", current_price)  # fallback to current price
                        enter_amount = order_detail.get("FilledQuantity", int_amount)     # fallback to requested amount
                        Have_order = True
                        print(now_datetime, f" Position opened: {enter_amount} @ {enter_price}")
                    else:
                        print(now_datetime, " Failed to open position after retries.")
        
    if Have_order:
        if enter_price and enter_price > 0:
            order_PL = ((current_price - enter_price) / enter_price) * 100
        else:
            print(now_datetime, "Invalid enter_price. Resetting position.")
            Have_order = False
            continue
        if (order_PL <= -2.5) or (order_PL >= 5.4) or sell_signal:
            print(now_datetime, f" Triggering sell (P/L: {order_PL:.2f}%)")
            balance_info = get_balance()
            if balance_info is None:
                print(now_datetime, " Failed to fetch balance. Cannot sell.")
            else:
                eth_free = float(balance_info.get('SpotWallet', {}).get('ETH', {}).get('Free', 0))
                if eth_free <= 0:
                    print(now_datetime, " No ETH to sell. Resetting position.")
                    Have_order = False
                else:
                    order_reply = place_order_with_retry(currency, "SELL", eth_free, max_retries=5)
                    if order_reply is not None:
                        # Optionally log filled details
                        order_detail = order_reply.get("OrderDetail", {})
                        filled_qty = order_detail.get("FilledQuantity", eth_free)
                        filled_price = order_detail.get("FilledAverPrice", current_price)
                        print(now_datetime, f" Sold {filled_qty} ETH @ avg {filled_price}")
                        Have_order = False
                    else:
                        print(now_datetime, " Failed to close position after retries.")
    
    next_run += 1
    sleep_time = max(0, next_run - time.time())
    time.sleep(sleep_time)
