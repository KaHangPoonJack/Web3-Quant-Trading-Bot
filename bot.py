import requests
import os
import time
import hmac
import hashlib
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
# ================================
# Configuration and Setup
# ================================

BASE_URL = "https://mock-api.roostoo.com"
API_KEY = "R5tY9uIpcN3vB1kMH7qD2wXaL0oG6eZfsP8jK4QraV1mT7UyxC5nF3WdJ2yS8lGo"
SECRET_KEY = "L9ZxCV1bN3mQwE5rT7yUiP9oA1sDdF3gJ5hKlZ7xC9vBnM1qW3eRtY5uI7oP"
HORUS_URL = "https://api-horus.com"
HORUS_API_KEY = "dcca142de11f3c3a6db14d91757a8ed2dc9bd8ebbd92103d65946deecf82e9ee"
COINBASE_URL = "https://api.exchange.coinbase.com"
CURRENCY_COINBASE = "ETH-USD"

# --- STATE ---
last_second = -1
currency = "ETH/USD"
bars = []
TrueRangeList = []

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

def get_historical_candles(symbol: str = CURRENCY_COINBASE, limit: int = ATR_period + 50) -> List[Dict]:
    """Fetch historical 15m candles from Coinbase (public, no key)."""
    url = f"{COINBASE_URL}/products/{symbol}/candles"
    params = {"granularity": time_frame * 60, "limit": limit}  # 900 sec = 15 min
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        raw = res.json()  # Newest first: [[time_sec, low, high, open, close, vol], ...]
        candles = []
        for c in reversed(raw):  # Reverse to oldest first
            candles.append({
                "open_time": c[0] * 1000,  # sec to ms (if needed; optional)
                "high": float(c[2]),
                "low": float(c[1]),
                "close": float(c[4])
            })
        return candles
    except requests.exceptions.RequestException as e:
        print(f"Error fetching historical candles: {e}")
        return []

def fetch_latest_candle(symbol: str = CURRENCY_COINBASE) -> Optional[Dict]:
    """Fetch the latest closed 15m candle from Coinbase."""
    url = f"{COINBASE_URL}/products/{symbol}/candles"
    params = {"granularity": 900, "limit": 1}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        raw = res.json()[0]  # [time_sec, low, high, open, close, vol]
        return {
            "open_time": raw[0] * 1000,
            "high": float(raw[2]),
            "low": float(raw[1]),
            "close": float(raw[4])
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest candle: {e}")
        return None

# ================================
# BACKTEST ENGINE
# ================================

# ================================
# MAIN
# ================================
# Load historical 15m candles from Coinbase (instant startup)
historical_candles = get_historical_candles()
if not historical_candles:
    print("Failed to load historical candles. Using empty bars.")
else:
    last_close = 0.0
    for i, candle in enumerate(historical_candles):
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        if i == 0:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - last_close), abs(low - last_close))
        bar = {"high": high, "low": low, "close": close, "TrueRange": true_range}
        bars.append(bar)
        TrueRangeList.append(true_range)
        last_close = close
    print(f"Loaded {len(bars)} historical bars from Coinbase. Last close: {last_close}")

# ================================
# CORRECT: Initialize Indicators (Run ONCE on last historical bar)
# ================================
if len(bars) >= ATR_period:  # Need at least 22 bars
    print(f"Initializing indicators using {len(bars)} historical bars...")

    # --- 1. Calculate ATR (22-period) ---
    if len(TrueRangeList) >= ATR_period:
        # Use last 22 True Ranges
        atr = np.mean(TrueRangeList[-ATR_period:]) if len(TrueRangeList) > ATR_period else np.mean(TrueRangeList[-ATR_period:])
        print(f"  → Initial ATR ({ATR_period}-period): {atr:.4f}")

    # --- 2. Chandelier Exit ---
    closes = [b["close"] for b in bars[-ATR_period:]]
    highest = max(closes)
    lowest = min(closes)
    ce_atr = 3.5 * atr
    long_stop = highest - ce_atr
    short_stop = lowest + ce_atr

    # Set initial previous stops
    long_stop_prev = long_stop
    short_stop_prev = short_stop

    current_close = bars[-1]["close"]
    if current_close > short_stop:
        dir = 1
    elif current_close < long_stop:
        dir = -1
    else:
        dir = 1  # default up
    print(f"  → CE: long_stop={long_stop:.2f}, short_stop={short_stop:.2f}, dir={dir}")

    # --- 3. Supertrend ---
    if len(TrueRangeList) >= st_atr_period:
        tr_list = TrueRangeList[-st_atr_period:]
        st_atr = np.mean(tr_list)
        high = bars[-1]["high"]
        low = bars[-1]["low"]
        close = bars[-1]["close"]
        hl2 = (high + low) / 2
        up = hl2 - (st_factor * st_atr)
        down = hl2 + (st_factor * st_atr)

        # Initialize prev values
        prev_up = up
        prev_down = down
        prev_supertrend = up
        is_uptrend = close > up
        print(f"  → Supertrend: up={up:.2f}, close={close:.2f}, is_uptrend={is_uptrend}")
    print("Indicator initialization complete. Ready for live trading.")
else:
    print(f"Only {len(bars)} bars loaded. Need {ATR_period} for full init. Building in real-time...")

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
        
    
    if now_datetime.minute % time_frame == 0 and now_datetime.second == 0 and bars:
        latest_candle = fetch_latest_candle()
        if latest_candle is None:
            print(now_datetime, "Failed to fetch latest candle, try again")
            time.sleep(0.5)
            latest_candle = fetch_latest_candle()
        else:
            high = latest_candle["high"]
            low = latest_candle["low"]
            close = latest_candle["close"]
            true_range = max(high - low, abs(high - last_close), abs(low - last_close))
            bar = {"high": high, "low": low, "close": close, "TrueRange": true_range}
            bars.append(bar)
            TrueRangeList.append(true_range)
            last_close = close  # Update for next TR
            print(now_datetime, ": New bar from Coinbase:", bar)
        if len(bars) > 100:
            bars = bars[-100:]
            
        # caculate atr22
        if len(TrueRangeList) > ATR_period + 1:
            TrueRangeList = TrueRangeList[-(ATR_period + 1):]
        if len(TrueRangeList) == ATR_period + 1:
            atr = np.mean(TrueRangeList[-ATR_period:])
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
        if (order_PL <= -2.5) or (order_PL >= 5) or sell_signal:
            print(now_datetime, f" Triggering sell (P/L: {order_PL:.2f}%)")
            balance_info = get_balance()
            print(balance_info)
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
                        print(get_balance())
                        Have_order = False
                    else:
                        print(now_datetime, " Failed to close position after retries.")
    
    next_run += 1
    sleep_time = max(0, next_run - time.time())
    time.sleep(sleep_time)
