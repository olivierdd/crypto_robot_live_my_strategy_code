# ---------------------------
# ENVELOPE STRATEGY LIVE CODE
# ---------------------------

# --- IMPORT LIBS ---
import sys
#sys.path.append('/Users/olivierdedecker/Documents/00_Dev/Python/Crypto_Robot_live/live_tools/utilities')
sys.path.append('/home/oddc/crypto_robot_live/live_tools/utilities')
import ccxt
import ta
import pandas as pd
#from perp_bitget import PerpBitget
from perp_bybit import *
from custom_indicators import get_n_columns
from datetime import datetime
import time
import json
import pprint
import uuid
import logging

# --- LAUNCH ---
# Configure the logging module
logging.basicConfig(filename='/home/oddc/crypto_robot_live/my_code/log_file.txt', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
current_time_python = now.timestamp()
logging.info('-------------------------------------------------------------------------------------')
#logging.info("--- Start Execution Time :", current_time, "---")
logging.info("--- Start Execution Time: %s ---", current_time)

# --- PARAMETERS & VARIABLES ---
# -- Account --
f = open('/home/oddc/crypto_robot_live/live_tools/secret.json')
secret = json.load(f)
f.close()
logging.info("loaded json secret file")

exchange_name = 'bybit'
account_to_select = 'real_account'
production = True

# -- Coins & timeframe --
timeframe = '1h'
pair = "VET/USDT:USDT"
leverage = 1
logging.info(f"--- {pair} {timeframe} Leverage x {leverage} ---")

# -- Indicator variable --
ema_shifts = [0.05, 0.1, 0.15]
ema_period = 5

# -- Rules --
SL_ativation = False                # flag to set explicit stop loss
TP_activation = False               # flag to set explicit take profit
SL_percentage = 0.5                 # stop loss percentage applied to buy/sell price if flag activated
TP_percentage = 0.10                # not used
multi_ATR = 0.3                     # used to set take profit if flag activated
showLog = True                      #
max_coins_in_position = 1           # max number of coin positions
nLevel = len(ema_shifts)            # max number of open positions per coin
position_type = ["long", "short"]
open_position_asap = True
close_position_with_indicator = False

# -- Value initialisation of trade monitoring variables of each coin --
stopLoss = 0            # list of stop loss of each coin, set if SL_ativation is True
takeProfit = 5000000    # list of take profit if TP_activation is True
walletCoinArray = 0     # list of number of coins longed / shorted
walletUsdArray = 0      # list of USDT used to enter in the position of each coin
entryPrice = 0          # list of entry price of each coin
leverageEnter = 1       # list of leverage used for each coin
position = 'LONG'       # list of position directions for each coin
nPosition = 0           # list of number of positions in each coin
activePositions = 0     # number of open positions

# -- Formating of dataframes --
pd.set_option('display.max_columns', 5)             # Display any number of columns
pd.set_option('display.max_rows', 5)                # Display any number of rows
pd.set_option('display.expand_frame_repr', False)   # Don't wrap repr(DataFrame) across additional lines


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
#logging.info(f'available usdt balance : {usdt_available_balance}')
logging.info('available usdt balance: %s', usdt_available_balance)


# get balance, position and order data
usd_balance = float(bybit.get_usdt_equity())
#logging.info("USD balance :", round(usd_balance, 2), "$")
logging.info("USD balance: %.2f $", usd_balance)

positions_data = bybit.get_open_position()
position_list = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["markPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]
df_position = pd.DataFrame(position_list)
logging.info('Positions')
logging.info(df_position)

orders_list = []
for order in bybit.get_open_orders():
    orders_list.append(order["info"])
df_orders = pd.DataFrame(orders_list)
if df_orders.empty == False:
    df_orders["price"] = pd.to_numeric(df_orders["price"])
    df_orders["qty"] = pd.to_numeric(df_orders["qty"])
logging.info('Open orders')
logging.info(df_orders)

# Get data
df = bybit.get_more_last_historical_async(pair, timeframe, 1000)


# --- POPULATE INDICATORS ---
sell_ema_values={}
buy_ema_values={}
df.drop(columns=df.columns.difference(['open','high','low','close','volume']), inplace=True)

df['ema_base'] = ta.trend.ema_indicator(close=df['close'], window=ema_period)
for i, shift in enumerate(ema_shifts, start=1):
    df[f'ema_high_{i}'] = df['ema_base'] * (1 + shift)
    df[f'ema_low_{i}'] = df['ema_base'] * (1 - shift)
    sell_ema_values[f'ema_high_{i}'] = bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_high_{i}'])
    buy_ema_values[f'ema_low_{i}'] = bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_low_{i}'])

# df = get_n_columns(df, ["ema_base"] + [f"ema_high_{i}" for i in range(1, len(ema_shifts) + 1)] 
#                    + [f"ema_low_{i}" for i in range(1, len(ema_shifts) + 1)] + ["close"], 1)


# --- CANCEL OPEN UNFILLED ORDERS ---
cancelled_longs = []
cancelled_shorts = []

for order in orders_list:
    if order['orderLinkId'] != '' and order['side']=='Buy':
        enveloppe_id = order['orderLinkId'].split("#")[0]
        cancelled_longs.append(enveloppe_id)
        order_id = order['orderId']
        order_symbol = order['symbol']
        logging.info(f'Cancel buy order {order_id}')
        if production:
            bybit.cancel_order(order_id = order_id, symbol=order_symbol)
    if order['orderLinkId'] != '' and order['side']=='Sell':
        enveloppe_id = order['orderLinkId'].split("#")[0]
        cancelled_shorts.append(enveloppe_id)
        order_id = order['orderId']
        order_symbol = order['symbol']
        logging.info(f'Cancel sell order {order_id}')
        if production:
            bybit.cancel_order(order_id = order_id, symbol=order_symbol)

logging.info(f'Cancelled {len(cancelled_longs)} longs and {len(cancelled_shorts)} shorts')


# --- CREATE AND MODIFY ORDERS ---
# deal entry logic
row = df.iloc[-2]
unique_id = f"#{uuid.uuid4()}"

# Determine order size
available_positions = max_coins_in_position #- len(df_position)
market_price = float(df.iloc[-1]['close'])
usdt_position_size = usdt_available_balance / available_positions
usdt_order_size = (usdt_position_size*leverage) / nLevel
logging.info(f'usdt order size for new orders: {usdt_order_size} using {leverage}x leverage')
coin_order_size = usdt_order_size / market_price
rounded_coin_order_size = float(bybit.convert_amount_to_precision(pair, coin_order_size))
logging.info(f'coin order size for new orders: {coin_order_size}')
logging.info(f'rounded coin order size for new orders: {rounded_coin_order_size}')

# Adjust TP of open position
if len(positions_data) > 0:
    logging.info(f"Active position")
    for order in orders_list:
        if order['orderLinkId']=='':
            order_size = order['qty']
            order_tp = bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])
            logging.info(f"Modify position TP: {order_size} {pair} at the price of {order_tp}$")
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
            # print(f'modified order:')
            # pprint.pprint(order)

# Create new limit orders for remaining slots
if open_long(row) and "long" in position_type:
    for ema, ema_value in buy_ema_values.items():
        if (ema in cancelled_longs) or df_orders.empty:
            logging.info(f"Place {ema} Long Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}$")
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
                #print('placed buy orders:')
                #pprint.pprint(order)

if open_short(row) and "short" in position_type:
    for ema, ema_value in sell_ema_values.items():
        if (ema in cancelled_shorts) or df_orders.empty:
            logging.info(f"Place {ema} Short Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}$")
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
                #print('placed buy orders:')
                #pprint.pprint(order)

# --- CLOSE ---
now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
#logging.info("--- End Execution Time :", current_time, "---")
logging.info("--- End Execution Time: %s ---", current_time)
logging.info("")
