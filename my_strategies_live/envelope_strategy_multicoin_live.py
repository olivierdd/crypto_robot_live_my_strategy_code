# ----------------------------------------
# MULTI COIN ENVELOPE STRATEGY LIVE CODE
# ----------------------------------------

"""
REMARQUES
- Les paires doivent être en Position Mode 'One Way Only' dans Bybit



A FAIRE
[x] Ajuster taille position pour que l'on soit au total égal à la taille du ptf en USDT
[x] Vérifier que strat marche quand zero ordres et zero positions
[x] Vérifier que strat marche quand ordres existent (cancel & replace ordres limite)
[x] Vérifier que strat marche quand position existe (ajustement prix TP et prix limite ordres restants)
[x] Vérifier que strat marche quand TP atteint
[x] Vérifier que strat marche quand SL atteint
[x] Ajout stop loss -> (1-x)% du prix d'entrée moyen si Long et (1+x)% si Short
[ ] Corriger calcul à la fin du commitment (tenir compte positions)
[ ] Optimiser le code
[x] Gérer config sans stop loss
"""

# --- IMPORT LIBS ---
import os
try:
    current_path = os.path.dirname(os.path.abspath(__file__))
    my_dir = os.path.dirname(current_path)
except:
    current_path = os.getcwd()
    my_dir = os.path.dirname(current_path)
lib_file_path = os.path.join(my_dir, 'my_utilities')
import sys
sys.path.append(lib_file_path)
import ta
from perp_bybit import *
from datetime import datetime
import json
import uuid
import logging


# --- CONFIGURE LOGGER --
log_file_path = os.path.join(my_dir, 'log_file_multi_envelope_live.txt')
print(f'Logging to: {log_file_path}')
logging.basicConfig(filename = log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

showLog = True

def log_me(message):
    if showLog:
        print(message)
        logging.info(message)
    else:
        logging.info(message)


# --- LAUNCH ---
showLog = True
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
secret_file_path = os.path.join(my_dir, 'secret.json')
f = open(secret_file_path)
secret = json.load(f)
f.close()

exchange_name = 'bybit'
#account_to_select = 'testnet_account'
account_to_select = 'real_account'
production = True

# -- Coins & timeframe --
timeframe = '1h'
pair_list = ["DYDX/USDT:USDT", "GFT/USDT:USDT"]
log_me(f"Launching bot with {pair_list} on {timeframe}")
log_me("")
log_me("-   "*20)

# -- Indicator variable --
ema_shifts = [0.05, 0.1, 0.15]
ema_period = 5

# -- Rules --
leverage = 0.2
nLevel = len(ema_shifts)            # max number of open positions per coin
position_type = ["long", "short"]   # indicate which kind of positions may be used
open_position_asap = True
close_position_with_indicator = False
stop_loss_pc = 0.25                  # % stop loss from average entry price


# --- INITIALIZE EXCHANGE & GET BALANCE ---
log_me('CHECKING BALANCES, POSITIONS AND ORDERS')
log_me('---------------------------------------')
log_me("")

# init lists
positions_list = []
orders_list = []

# connect exchange
bybit = PerpBybit(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    default_type='swap',
    is_real=secret[account_to_select]["is_real"]
)

# get all tradable pairs
markets = bybit.fetch_markets('')

# get portfolio balance data from exchange
usdt_available_balance = float(bybit.get_usdt_equity())
#usdt_available_balance = float(bybit.get_usdt_available_balance())
log_me(f'available usdt balance: {usdt_available_balance:.2f} $')

# get open positions for coins of our strategy
positions_data = bybit.get_open_position()
positions_list = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["markPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] in pair_list]
df_position = pd.DataFrame(positions_list)
log_me('')
log_me('- Positions -')
if df_position.empty:
    log_me("No open positions")
else:
    log_me(df_position)

for pair in pair_list:
    # get open orders for coins in our strategy
    for order in bybit.get_open_orders(pair):
        orders_list.append(order["info"])
df_orders = pd.DataFrame(orders_list)
log_me('')
log_me('- Open orders -')
if df_orders.empty:
    log_me("No open orders")
else:
    df_orders["price"] = pd.to_numeric(df_orders["price"])
    df_orders["qty"] = pd.to_numeric(df_orders["qty"])
    #log_me(df_orders)
    for index, row in df_orders.iterrows():
        log_me(f'  {index} - {row.symbol} {row.side} {row.qty} at {row.price}')
log_me("-   "*20)
log_me('')



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

def get_data(pair, timeframe, length):
    """
    Reminder: you need to adjust the limit parameter in function of the timeframe you use
    On lower timeframes bybit will not provide the most up to date ohlc prices if the 
    limit is set too high
    """
    df = bybit.get_more_last_historical_async(pair, timeframe, length)
    return df

def populate_indicators(df, ema_period, ema_shifts):
    log_me("COMPUTE INDICATORS")
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
        sell_ema_values[f'ema_high_{i}'] = float(bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_high_{i}']))
        buy_ema_values[f'ema_low_{i}'] = float(bybit.convert_price_to_precision(pair, df.iloc[-1][f'ema_low_{i}']))
    log_me("")
    return(df, sell_ema_values, buy_ema_values)

def cancel_unfilled_orders(orders_list, production, pair):
    log_me("MANAGE ORDERS")
    log_me("")
    cancelled_longs = []
    cancelled_shorts = []
    if len(orders_list)!=0:
        for order in orders_list:
            order_symbol = order['orderLinkId'].split('@')[0]
            if order_symbol==pair:
                if order['orderLinkId'] != '' and order['side']=='Buy':
                    enveloppe_id = order['orderLinkId'].split("@")[1]
                    cancelled_longs.append(enveloppe_id)
                    order_id = order['orderId']
                    order_symbol = order['symbol']
                    log_me(f'Cancel buy order {order_id}')
                    if production:
                        bybit.cancel_order(order_id = order_id, symbol=order_symbol)
                if order['orderLinkId'] != '' and order['side']=='Sell':
                    enveloppe_id = order['orderLinkId'].split("@")[1]
                    cancelled_shorts.append(enveloppe_id)
                    order_id = order['orderId']
                    order_symbol = order['symbol']
                    log_me(f'Cancel sell order {order_id}')
                    if production:
                        bybit.cancel_order(order_id = order_id, symbol=order_symbol)
        log_me(f'Cancelled {len(cancelled_longs)} longs and {len(cancelled_shorts)} shorts')
        log_me("")
    else:
        log_me(f'No orders to cancel')
        log_me("")
    return(cancelled_longs, cancelled_shorts)

def determine_usdt_order_size(usdt_available_balance, leverage, nLevel):
    usdt_position_size = usdt_available_balance #/ available_positions
    usdt_order_size = (usdt_position_size*leverage) / (nLevel * len(pair_list))
    usdt_order_size = round(usdt_order_size, 2)
    log_me(f'usdt order size for new orders: {usdt_order_size} USDT using {leverage}x leverage')
    log_me(f'this allows to enter into {nLevel * len(pair_list)} positions with {leverage} leverage')
    log_me(f'{nLevel * len(pair_list)} x {usdt_order_size} = {round(nLevel * len(pair_list) * usdt_order_size, 2)}')
    log_me(f'available funds = {round(usdt_position_size, 2)} USDT')
    return(usdt_order_size)

def determine_coin_order_size(usdt_order_size, coin_limit_price):
    #market_price = float(df.iloc[-1]['close'])
    coin_limit_price = float(coin_limit_price)
    coin_order_size = usdt_order_size / coin_limit_price
    rounded_coin_order_size = float(bybit.convert_amount_to_precision(pair, coin_order_size))
    return(rounded_coin_order_size)

def modify_symbol(symbol):
    if ":" in symbol:
        symbol = symbol.split(':')[0]
    symbol = symbol.replace("/", "")
    return(symbol)

def adjust_tps(positions_data, orders_list, production, pair, df):
    if len(positions_data) > 0:
        for order in orders_list:
            order_symbol = order['symbol']
            if order['orderLinkId']=='' and order_symbol==modify_symbol(pair):
                order_size = order['qty']
                order_tp = bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])
                log_me("Active positions ... need to modify tps")
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
        log_me("")
    else:
        log_me("No active position > no tps to modify")
        log_me("")
    return()

def create_orders(row, position_type, buy_ema_values, sell_ema_values, cancelled_longs, cancelled_shorts, df_orders, df_position, usdt_order_size, pair, df, unique_id, stop_loss_pc):
    # Create new limit orders for remaining slots
    if open_long(row) and "long" in position_type:
        average_entry_price = sum(buy_ema_values.values())/len(buy_ema_values)
        for ema, ema_value in buy_ema_values.items():
            if (ema in cancelled_longs) or df_orders.empty or len(df_position)==0:
                market_price = float(df.iloc[-1]['close'])
                rounded_coin_order_size = determine_coin_order_size(usdt_order_size, ema_value)
                log_me(f"Place {ema} Long Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}, tp at {bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])} and sl at {bybit.convert_price_to_precision(pair, compute_stop_loss_price(average_entry_price, stop_loss_pc, 'long'))}")
                if production:
                    order = bybit.place_limit_order(
                        symbol=pair,
                        side='buy',
                        amount=rounded_coin_order_size,
                        limit=ema_value,
                        sl=bybit.convert_price_to_precision(pair, compute_stop_loss_price(average_entry_price, stop_loss_pc, 'long')),
                        tp=bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base']),
                        reduce=False,
                        orderLinkId=f'{pair}@{ema}@{unique_id}'
                    )

    if open_short(row) and "short" in position_type:
        average_entry_price = sum(sell_ema_values.values())/len(sell_ema_values)
        for ema, ema_value in sell_ema_values.items():
            if (ema in cancelled_shorts) or df_orders.empty or len(df_position)==0:
                market_price = float(df.iloc[-1]['close'])
                rounded_coin_order_size = determine_coin_order_size(usdt_order_size, ema_value)
                log_me(f"Place {ema} Short Limit Order: {rounded_coin_order_size} {pair} at the price of {ema_value}, tp at {bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base'])} and sl at {bybit.convert_price_to_precision(pair, compute_stop_loss_price(average_entry_price, stop_loss_pc, 'short'))}")
                if production:
                    order = bybit.place_limit_order(
                        symbol=pair,
                        side='sell',
                        amount=rounded_coin_order_size,
                        limit=ema_value,
                        sl=bybit.convert_price_to_precision(pair, compute_stop_loss_price(average_entry_price, stop_loss_pc, 'short')),
                        tp=bybit.convert_price_to_precision(pair, df.iloc[-1]['ema_base']),
                        reduce=False,
                        orderLinkId=f'{pair}@{ema}@{unique_id}'
                    )
    return()

def compute_stop_loss_price(average_entry_price, stop_loss_pc, direction):
    if direction=='long':
        return(average_entry_price*(1-stop_loss_pc))
    elif direction=='short':
        return(average_entry_price*(1+stop_loss_pc))
    else:
        return()
    

    print('NOW COMPUTING USDT ORDER SIZE')
usdt_order_size = determine_usdt_order_size(usdt_available_balance, leverage, nLevel)
print("")

for pair in pair_list:
    print("")
    print(f'NOW HANDLING {pair}')
    print("--------------------------")
    print("")
    df = get_data(pair, timeframe, 30)
    df, sell_ema_values, buy_ema_values = populate_indicators(df, ema_period, ema_shifts)
    cancelled_longs, cancelled_shorts = cancel_unfilled_orders(orders_list, production, pair)
    row = df.iloc[-2]
    unique_id = f"#{uuid.uuid4()}"
    adjust_tps(positions_data, orders_list, production, pair, df)
    create_orders(row, position_type, buy_ema_values, sell_ema_values, cancelled_longs, cancelled_shorts, df_orders, df_position, usdt_order_size, pair, df, unique_id, stop_loss_pc)


# --- CHECK EXCHANGE ORDERS vs BALANCE ---
log_me('CHECKING NEW ORDERS vs BALANCE & POSITIONS')
log_me('------------------------------------------')
log_me("")

# init lists
new_positions_list = []
new_orders_list = []
buy_commitment_in_usdt = 0
sell_commitment_in_usdt = 0

# get portfolio balance data from exchange
new_usdt_available_balance = float(bybit.get_usdt_available_balance())
new_usdt_equity = round(float(bybit.get_usdt_equity()), 2)
log_me(f'available usdt balance: {new_usdt_available_balance:.2f} $')
log_me(f'available usdt equity: {new_usdt_equity:.2f} $')



# get open positions for coins of our strategy
new_positions_data = bybit.get_open_position()
new_positions_list = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["markPrice"]), "open_price": d["entryPrice"]}
    for d in new_positions_data if d["symbol"] in pair_list]
new_df_position = pd.DataFrame(new_positions_list)
log_me('')
log_me('- New positions -')
if new_df_position.empty:
    log_me("No new open positions")
else:
    log_me(new_df_position)


# get open orders for coins in our strategy
for pair in pair_list:
    # get open orders for coins in our strategy
    for order in bybit.get_open_orders(pair):
        new_orders_list.append(order["info"])
new_df_orders = pd.DataFrame(new_orders_list)
log_me('')
log_me('- New open orders -')
if new_df_orders.empty:
    log_me("No new open orders")
else:
    new_df_orders["price"] = pd.to_numeric(new_df_orders["price"])
    new_df_orders["qty"] = pd.to_numeric(new_df_orders["qty"])
    buy_orders_df = new_df_orders[new_df_orders['side'] == 'Buy']
    sell_orders_df = new_df_orders[new_df_orders['side'] == 'Sell']
    buy_commitment_in_usdt = (buy_orders_df["price"] * buy_orders_df["qty"]).sum()
    sell_commitment_in_usdt = (sell_orders_df["price"] * sell_orders_df["qty"]).sum()
    for index, row in new_df_orders.iterrows():
        log_me(f'  {index:02} - {row.symbol} {row.side} {row.qty} at {row.price} -> {round(row.qty * row.price, 2)} USDT')
log_me("-   "*20)
log_me('')
log_me(f'USDT equity : {new_usdt_equity}')
log_me(f'Strategy buy commitment : {round(buy_commitment_in_usdt, 2)}')
log_me(f'Strategy sell commitment : {round(sell_commitment_in_usdt, 2)}')


# --- CLOSE ---
now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
log_me(f"End Execution Time: {current_time}")
log_me("")