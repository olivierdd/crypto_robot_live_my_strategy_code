# ---------------------------
# ENVELOPE STRATEGY LIVE CODE
# ---------------------------

# --- IMPORT LIBS ---
import os
my_dir = "/home/oddc/crypto_robot_live/"
#my_dir = "/Users/olivierdedecker/Documents/00_Dev/Python/Crypto_Robot_live/"
lib_file_path = os.path.join(my_dir, 'live_tools', 'utilities')
import sys
sys.path.append(lib_file_path)
import ta
from perp_bybit import *
from datetime import datetime
import json
import uuid
import logging


# --- CONFIGURE LOGGER --
log_file_path = os.path.join(my_dir, 'my_code', 'log_file.txt')
print(log_file_path)
logging.basicConfig(filename = log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

showLog = False

def log_me(message):
    if showLog:
        print(message)
        logging.info(message)
    else:
        logging.info(message)


# --- LAUNCH ---
showLog = True                      #
now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
current_time_python = now.timestamp()
log_me("")
log_me("="*80)
log_me("STARTING BOT")
log_me("------------")
log_me("")
log_me(f"Start Execution Time : {current_time}")

# --- PARAMETERS & VARIABLES ---
# -- Account --
secret_file_path = os.path.join(my_dir, 'live_tools', 'secret.json')
f = open(secret_file_path)
secret = json.load(f)
f.close()

exchange_name = 'bybit'
#account_to_select = 'testnet_account'
account_to_select = 'real_account'
production = True

# -- Coins & timeframe --
timeframe = '1h'
pair = "VET/USDT:USDT"
leverage = 1
log_me(f"Launching bot with {pair} on {timeframe} and Leverage x {leverage}")
log_me("")
log_me("-   "*20)

# -- Indicator variable --
ema_shifts = [0.05, 0.1, 0.15]
ema_period = 5

# -- Rules --
nLevel = len(ema_shifts)            # max number of open positions per coin
position_type = ["long", "short"]   # indicate which kind of positions may be used
open_position_asap = True
close_position_with_indicator = False


# --- FUNCTIONS ---
def open_long(row):
    if ('long' in position_type) and open_position_asap:
        return True
    else:
        return False

def close_long(row):
    if close_position_with_indicator:
        # some code
        return True
    else:
        return False

def open_short(row):
    if ('short' in position_type) and open_position_asap:
        return True
    else:
        return False

def close_short(row):
    if close_position_with_indicator:
        # some code
        return True
    else:
        return False
        

# --- INITIALIZE EXCHANGE & GET BALANCE ---
log_me('CHECKING BALANCES, POSITIONS AND ORDERS')
log_me('---------------------------------------')
log_me("")
# connect exchange
bybit = PerpBybit(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    default_type='swap',
    is_real=secret[account_to_select]["is_real"]
)

# get portfolio balance data from exchange
usdt_equity = float(bybit.get_usdt_equity())
usdt_available_balance = float(bybit.get_usdt_available_balance())
log_me(f'available usdt balance: {usdt_available_balance:.2f} $')

# get balance, position and order data
usd_balance = float(bybit.get_usdt_equity())
log_me(f"USD balance: {usd_balance:.2f} $")

positions_data = bybit.get_open_position()
position_list = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["markPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]
df_position = pd.DataFrame(position_list)
log_me('')
log_me('Positions')
log_me(df_position)

orders_list = []
for order in bybit.get_open_orders():
    if order['symbol']==pair:
        orders_list.append(order["info"])
df_orders = pd.DataFrame(orders_list)
if df_orders.empty == False:
    df_orders["price"] = pd.to_numeric(df_orders["price"])
    df_orders["qty"] = pd.to_numeric(df_orders["qty"])
log_me('')
log_me('Open orders')
log_me(df_orders)
log_me("-   "*20)
log_me('')

# Get data
"""
Reminder: you need to adjust the limit parameter in function of the timeframe you use
On lower timeframes bybit will not provide the must up to date ohlc priced if the 
limit is too high
"""
df = bybit.get_more_last_historical_async(pair, timeframe, 30)


# --- POPULATE INDICATORS ---
log_me("COMPUTE INDICATORS")
log_me("------------------")
log_me("")
sell_ema_values={}
buy_ema_values={}
df.drop(columns=df.columns.difference(['open','high','low','close','volume']), inplace=True)

df['ema_base'] = ta.trend.ema_indicator(close=df['close'], window=ema_period)
log_me(f'ema base : {df.iloc[-1]["ema_base"]}')
for i, shift in enumerate(ema_shifts, start=1):
    df[f'ema_high_{i}'] = df['ema_base'] * (1 + shift)
    df[f'ema_low_{i}'] = df['ema_base'] * (1 - shift)
    log_me(f'ema high {i} : {df.iloc[-1]["ema_high_" + str(i)]}')
    log_me(f'ema low {i} : {df.iloc[-1][f"ema_low_" + str(i)]}')

    sell_ema_values[f'ema_high_{i}'] = bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_high_{i}'])
    buy_ema_values[f'ema_low_{i}'] = bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_low_{i}'])
log_me("")
log_me("-   "*20)

# --- CANCEL OPEN UNFILLED ORDERS ---
log_me("MANAGE ORDERS")
log_me("-------------")
log_me("")
cancelled_longs = []
cancelled_shorts = []

for order in orders_list:
    if order['orderLinkId'] != '' and order['side']=='Buy':
        enveloppe_id = order['orderLinkId'].split("#")[0]
        cancelled_longs.append(enveloppe_id)
        order_id = order['orderId']
        order_symbol = order['symbol']
        log_me(f'Cancel buy order {order_id}')
        if production:
            bybit.cancel_order(order_id = order_id, symbol=order_symbol)
    if order['orderLinkId'] != '' and order['side']=='Sell':
        enveloppe_id = order['orderLinkId'].split("#")[0]
        cancelled_shorts.append(enveloppe_id)
        order_id = order['orderId']
        order_symbol = order['symbol']
        log_me(f'Cancel sell order {order_id}')
        if production:
            bybit.cancel_order(order_id = order_id, symbol=order_symbol)

log_me(f'Cancelled {len(cancelled_longs)} longs and {len(cancelled_shorts)} shorts')


# --- CREATE AND MODIFY ORDERS ---
# deal entry logic
row = df.iloc[-2]
unique_id = f"#{uuid.uuid4()}"

# Determine order size
market_price = float(df.iloc[-1]['close'])
usdt_position_size = usdt_available_balance
usdt_order_size = (usdt_position_size*leverage) / nLevel
log_me(f'usdt order size for new orders: {usdt_order_size} using {leverage}x leverage')
coin_order_size = usdt_order_size / market_price
rounded_coin_order_size = float(bybit.convert_amount_to_precision(pair, coin_order_size))
log_me(f'coin order size for new orders: {coin_order_size}')
log_me(f'rounded coin order size for new orders: {rounded_coin_order_size}')

# Adjust TP of open position
if len(positions_data) > 0:
    log_me("Active position")
    for order in orders_list:
        if order['orderLinkId']=='':
            order_size = order['qty']
            order_tp = bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])
            log_me(f"Modify position TP: {order_size} {pair} at the price of {order_tp}$")
            if production:
                order = bybit.edit_order(
                    id=order['orderId'],
                    symbol=order['symbol'],
                    type=order['orderType'],
                    side=order['side'],
                    amount=order['qty'],
                    price=None,
                    params={
                        'triggerPrice': bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])
                    }
                )

# Create new limit orders for remaining slots
if open_long(row) and "long" in position_type:
    for ema, ema_value in buy_ema_values.items():
        if (ema in cancelled_longs) or df_orders.empty or len(df_position)==0:
            log_me(f"Place {ema} Long Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}$")
            if production:
                order = bybit.place_limit_order(
                    symbol=pair,
                    side='buy',
                    amount=rounded_coin_order_size,
                    limit=ema_value,
                    sl=None,
                    tp=bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base']),
                    reduce=False,
                    orderLinkId=f'{ema}{unique_id}'
                )

if open_short(row) and "short" in position_type:
    for ema, ema_value in sell_ema_values.items():
        if (ema in cancelled_shorts) or df_orders.empty or len(df_position)==0:
            log_me(f"Place {ema} Short Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}$")
            if production:
                order = bybit.place_limit_order(
                    symbol=pair,
                    side='sell',
                    amount=rounded_coin_order_size,
                    limit=ema_value,
                    sl=None,
                    tp=bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base']),
                    reduce=False,
                    orderLinkId=f'{ema}{unique_id}'
                )
log_me("-   "*20)

# --- CLOSE ---
now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
log_me(f"End Execution Time: {current_time}")
log_me("")
