import requests
import time
import hmac
import hashlib
import time
import numpy as np
import pandas as pd

BASE_URL = "https://mock-api.roostoo.com"
API_KEY = "USEAPIKEYASMYID"
SECRET_KEY = "S1XP1e3UZj6A7H5fATj0jNhqPxxdSJYdInClVN65XAbvqqMKjVHjA7PZj4W12oep"
# --------------------------------------------------------

def _get_timestamp():
    """Returns a 13-digit millisecond timestamp as a string."""
    return str(int(time.time() * 1000))

def _get_signed_headers(payload={}):
    """
    Creates a signature for a given payload (dict) and returns
    the correct headers for a SIGNED (RCL_TopLevelCheck) request.
    """
    # 1. Add timestamp to the payload
    payload['timestamp'] = _get_timestamp()
    
    # 2. Sort keys and create the totalParams string
    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{key}={payload[key]}" for key in sorted_keys)
    
    # 3. Create HMAC-SHA256 signature
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        total_params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 4. Create headers
    headers = {
        'RST-API-KEY': API_KEY,
        'MSG-SIGNATURE': signature
    }
    
    return headers, payload, total_params

# --- Now we can define functions for each API call ---

# --------------------------------------------------------

def check_server_time():
    """Checks server time. (Auth: RCL_NoVerification)"""
    url = f"{BASE_URL}/v3/serverTime"
    try:
        response = requests.get(url)
        response.raise_for_status() # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error checking server time: {e}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Checking Server Time ---")
#     server_time = check_server_time()
#     if server_time:
#         print(f"Server time: {server_time.get('ServerTime')}")

# --------------------------------------------------------

def get_exchange_info():
    """Gets exchange info. (Auth: RCL_NoVerification)"""
    url = f"{BASE_URL}/v3/exchangeInfo"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting exchange info: {e}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Getting Exchange Info ---")
#     info = get_exchange_info()
#     if info:
#         print(f"Is running: {info.get('IsRunning')}")
#         print(f"Available pairs: {list(info.get('TradePairs', {}).keys())}")

# --------------------------------------------------------

def get_ticker(pair=None):
    """Gets market ticker. (Auth: RCL_TSCheck)"""
    url = f"{BASE_URL}/v3/ticker"
    params = {
        'timestamp': _get_timestamp()
    }
    if pair:
        params['pair'] = pair
        
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting ticker: {e}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Getting Ticker (All) ---")
#     ticker_all = get_ticker()
#     if ticker_all:
#         print(f"Got data for {len(ticker_all.get('Data', {}))} pairs.")
    
#     print("\n--- Getting Ticker (BTC/USD) ---")
#     ticker_btc = get_ticker(pair="BTC/USD")
#     if ticker_btc:
#         print(f"BTC/USD Last Price: {ticker_btc.get('Data', {}).get('BTC/USD', {}).get('LastPrice')}")

# --------------------------------------------------------

def get_balance():
    """Gets account balance. (Auth: RCL_TopLevelCheck)"""
    url = f"{BASE_URL}/v3/balance"
    
    # 1. Get signed headers and the payload (which now includes timestamp)
    # For a GET request with no params, the payload is just the timestamp
    headers, payload, total_params_string = _get_signed_headers(payload={})
    
    try:
        # 2. Send the request
        # In a GET request, the payload is sent as 'params'
        response = requests.get(url, headers=headers, params=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting balance: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Getting Balance ---")
#     balance = get_balance()
#     if balance and balance.get('Success'):
#         print(f"USD Free: {balance.get('Wallet', {}).get('USD', {}).get('Free')}")
#     elif balance:
#         print(f"Error: {balance.get('ErrMsg')}")

# --------------------------------------------------------

def get_pending_count():
    """Gets pending order count. (Auth: RCL_TopLevelCheck)"""
    url = f"{BASE_URL}/v3/pending_count"
    
    headers, payload, total_params_string = _get_signed_headers(payload={})
    
    try:
        response = requests.get(url, headers=headers, params=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting pending count: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Getting Pending Order Count ---")
#     count = get_pending_count()
#     if count:
#         print(f"Success: {count.get('Success')}")
#         print(f"Total Pending: {count.get('TotalPending')}")
#         print(f"Error Msg: {count.get('ErrMsg')}")

# --------------------------------------------------------

def place_order(pair_or_coin, side, quantity, price=None, order_type=None):
    """
    Places a new order with improved flexibility and safety checks.

    Args:
        pair_or_coin (str): The asset to trade (e.g., "BTC" or "BTC/USD").
        side (str): "BUY" or "SELL".
        quantity (float or int): The amount to trade.
        price (float, optional): The price for a LIMIT order. Defaults to None.
        order_type (str, optional): "LIMIT" or "MARKET". Auto-detected if not provided.
    """
    print(f"\n--- Placing a new order for {quantity} {pair_or_coin} ---")
    url = f"{BASE_URL}/v3/place_order"

    # 1. Determine the full pair name
    pair = f"{pair_or_coin}/USD" if "/" not in pair_or_coin else pair_or_coin

    # 2. Auto-detect order_type if it's not specified
    if order_type is None:
        order_type = "LIMIT" if price is not None else "MARKET"
        print(f"Auto-detected order type: {order_type}")

    # 3. Validate parameters to prevent errors
    if order_type == 'LIMIT' and price is None:
        print("Error: LIMIT orders require a 'price' parameter.")
        return None
    if order_type == 'MARKET' and price is not None:
        print("Warning: Price is provided for a MARKET order and will be ignored by the API.")

    # 4. Create the request payload
    payload = {
        'pair': pair,
        'side': side.upper(),
        'type': order_type.upper(),
        'quantity': str(quantity)
    }
    if order_type == 'LIMIT':
        payload['price'] = str(price)

    # 5. Get signed headers and the final request body
    headers, total_params_string = _get_signed_headers(payload) #_get_signed_headers_and_body()

    # 6. Send the request
    try:
        response = requests.post(url, headers=headers, data=total_params_string)
        response.raise_for_status()
        print(f"API Response: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error placing order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


# --- Example Usage ---
#if __name__ == "__main__":
    # Example 1: Place a LIMIT order (by providing a price)
    # The function will correctly identify this as a LIMIT order.
#    place_order(
#        pair_or_coin="BTC",
#        side="SELL",
#        quantity=0.01,
#        price=99000
#    )

    # Example 2: Place a MARKET order (by not providing a price)
    # The function will correctly identify this as a MARKET order.
#    place_order(
#        pair_or_coin="BNB/USD",
#        side="BUY",
#        quantity=10
#    )

    # Example 3: Invalid order (LIMIT without a price)
    # The function will catch this error before sending the request.
#    place_order(
#        pair_or_coin="ETH",
#        side="BUY",
#        quantity=0.5,
#        order_type="LIMIT" # Explicitly set, but no price given
#    )

def query_order(order_id=None, pair=None, pending_only=None):
    """Queries orders. (Auth: RCL_TopLevelCheck)"""
    url = f"{BASE_URL}/v3/query_order"
    
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair: # Docs say order_id and pair cannot be sent together
        payload['pair'] = pair
        if pending_only is not None:
             # Docs specify STRING_BOOL
            payload['pending_only'] = 'TRUE' if pending_only else 'FALSE'
            
    headers, final_payload, total_params_string = _get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    
    try:
        response = requests.post(url, headers=headers, data=total_params_string)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     print("--- Querying Pending BTC/USD Orders ---")
#     orders = query_order(pair="BTC/USD", pending_only=True)
#     if orders and orders.get('Success'):
#         print(f"Found {len(orders.get('OrderMatched', []))} matching orders.")
#     elif orders:
#         print(f"Error: {orders.get('ErrMsg')}")

# --------------------------------------------------------

def cancel_order(order_id=None, pair=None):
    """Cancels orders. (Auth: RCL_TopLevelCheck)"""
    url = f"{BASE_URL}/v3/cancel_order"
    
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair: # Docs say only one is allowed
        payload['pair'] = pair
    # If neither is sent, it cancels all
        
    headers, final_payload, total_params_string = _get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    
    try:
        response = requests.post(url, headers=headers, data=total_params_string)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error canceling order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None

# --- To run this specific test ---
# if __name__ == "__main__":
#     # First, let's place an order to cancel
#     print("--- Placing an order to cancel ---")
#     order_to_cancel = place_order("ETH/USD", "BUY", "LIMIT", 0.1, 1000)
#     if order_to_cancel and order_to_cancel.get('Success'):
#         order_id = order_to_cancel.get('OrderDetail', {}).get('OrderID')
#         print(f"Placed order with ID: {order_id}")
        
#         if order_id:
#             print(f"\n--- 8. Canceling order {order_id} ---")
#             cancel_result = cancel_order(order_id=order_id)
#             if cancel_result:
#                 print(f"Cancel Success: {cancel_result.get('Success')}")
#                 print(f"Canceled List: {cancel_result.get('CanceledList')}")
#     else:
#         print("Could not place order to test cancellation.")

# --------------------------------------------------------
# --------------------------------------------------------
place_order ("BTC/USD", "BUY", 100, , )
