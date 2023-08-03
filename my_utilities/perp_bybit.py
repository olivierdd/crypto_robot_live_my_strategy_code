import ccxt
import pandas as pd
import time
from multiprocessing.pool import ThreadPool as Pool
import numpy as np
from datetime import datetime

# --- INTERACT WITH BYBIT ---

class PerpBybit():
    def __init__(self, apiKey=None, secret=None, default_type=None, is_real=None):
        bybit_auth_object = {
            "apiKey": apiKey,
            "secret": secret,
            'options': {
                'defaultType': default_type,
            }
        }
        if bybit_auth_object['secret'] == None:
            self._auth = False
            self._session = ccxt.bybit()
        else:
            self._auth = True
            self._session = ccxt.bybit(bybit_auth_object)
            if is_real=="False":
                print('hey .. set sandbox mode ON')
                self._session.set_sandbox_mode(True)
            else:
                print('ok.. set sandbox mode OFF')
                self._session.set_sandbox_mode(False)
        self.market = self._session.load_markets()

    def authentication_required(fn):
        """Annotation for methods that require auth."""
        def wrapped(self, *args, **kwargs): #!!!!!!!!!
            if not self._auth:
                # print("You must be authenticated to use this method", fn)
                raise Exception("You must be authenticated to use this method")
            else:
                return fn(self, *args, **kwargs)#!!!! *kwargs
        return wrapped
    
    def activate_testnet_mode(self):
        self._session.set_sandbox_mode(True) # activates testnet mode

#   market data

    def get_last_historical(self, symbol, timeframe, limit):
        result = pd.DataFrame(data=self._session.fetch_ohlcv(
            symbol, timeframe, None, limit=limit))
        result = result.rename(
            columns={0: 'timestamp', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'})
        result = result.set_index(result['timestamp'])
        result.index = pd.to_datetime(result.index, unit='ms')
        del result['timestamp']
        return result

    def get_more_last_historical_async(self, symbol, timeframe, limit):
        max_threads = 4
        pool_size = round(limit/100)  # your "parallelness"

        # define worker function before a Pool is instantiated
        full_result = []
        def worker(i):

            try:
                return self._session.fetch_ohlcv(
                symbol, timeframe, round(time.time() * 1000) - (i*1000*60*60), limit=100)
            except Exception as err:
                raise Exception("Error on last historical on " + symbol + ": " + str(err))

        pool = Pool(max_threads)

        full_result = pool.map(worker,range(limit, 0, -100))
        full_result = np.array(full_result).reshape(-1,6)
        result = pd.DataFrame(data=full_result)
        result = result.rename(
            columns={0: 'timestamp', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'})
        result = result.set_index(result['timestamp'])
        result.index = pd.to_datetime(result.index, unit='ms')
        del result['timestamp']
        return result.sort_index()
    
    def fetch_markets(self, params=None):
        result = pd.DataFrame(data=self._session.fetch_markets(params))
        return result

#   account data

    @authentication_required
    def get_usdt_equity(self):
        try:
            usdt_equity = self._session.fetch_balance({'coin':'USDT' })["info"]['result']['list'][0]['equity']

        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return usdt_equity
        except:
            return 0

    @authentication_required
    def get_open_position(self,symbol=None):
        #print("ohoho",self._session.fetch_positions(symbol))
        try:
            positions = self._session.fetch_positions(symbol)
            #print('hello', positions)
            truePositions = []
            for position in positions:
                if float(position['contractSize']) > 0:
                    truePositions.append(position)
            return truePositions
        except BaseException as err:
            raise TypeError("An error occured in get_open_position", err)
    
    @authentication_required
    def get_open_orders(self,symbol=None):
        try:
            open_orders = self._session.fetch_open_orders(symbol)

        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return open_orders
        except:
            return 0

    @authentication_required
    def get_all_balances(self):
        try:
            balances = self._session.fetch_balance()

        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return balances
        except:
            return 0
        
    @authentication_required
    def get_usdt_available_balance(self):
        try:
            usdt_avail_balance = self._session.fetch_balance({'coin':'USDT' })["info"]['result']['list'][0]['availableBalance']

        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return usdt_avail_balance
        except:
            return 0

    @authentication_required
    def get_orders(self, symbol, since=None):
        try:
            open_orders = self._session.fetch_orders(symbol=symbol, since=since)

        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return open_orders
        except:
            return 0

#   trade

    def convert_amount_to_precision(self, symbol, amount):
        return self._session.amount_to_precision(symbol, amount)

    def convert_price_to_precision(self, symbol, price):
        return self._session.price_to_precision(symbol, price)

    @authentication_required
    def place_market_order(self, symbol, side, amount, reduce=False):
        try:
            return self._session.create_order(
                symbol,
                'market',
                side,
                self.convert_amount_to_precision(symbol, amount),
                None,
                params = {'reduce_only': reduce},
            )
        except BaseException as err:
            raise Exception(err)
        
    @authentication_required
    def place_limit_order(self, symbol, side, amount, limit, sl=None, tp=None, reduce=False, orderLinkId=None):
        try:
            params = {
                'reduce_only': reduce,
                'orderLinkId': orderLinkId,
                'positionIdx': 0,
                'reduceOnly': False,
            }
            if sl is not None:
                params['stopLoss'] = self.convert_price_to_precision(symbol, sl)
            if tp is not None:
                params['takeProfit'] = self.convert_price_to_precision(symbol, tp)

            return self._session.create_order(
                symbol,
                'limit',
                side,
                self.convert_amount_to_precision(symbol, amount),
                self.convert_price_to_precision(symbol,limit),
                params = params,
            )
        except BaseException as err:
            raise Exception(err)

    @authentication_required
    def cancel_order(self, order_id, symbol, params={}):
        try:
            return self._session.cancel_order(
                order_id,
                symbol,
                params
            )
        except BaseException as err:
            raise Exception(err)

    
    @authentication_required
    def edit_order(self, id, symbol, type, side, amount=None, price=None, params={}):
        try:
            return self._session.edit_order(
                id=id,
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params
            )
        except BaseException as err:
            raise Exception(err)
    
    
    
    @authentication_required
    def place_market_stop_loss(self, symbol, side, amount, trigger_price, reduce=False):

        try:
            return self._session.create_order(
                symbol,
                'market',
                side,
                self.convert_amount_to_precision(symbol, amount),
                self.convert_price_to_precision(symbol, trigger_price),
                params = {
                    'stop_loss': self.convert_price_to_precision(symbol, trigger_price),  # your stop price
                    "triggerType": "market_price",
                    "reduce_only": reduce
                },
            )
        except BaseException as err:
            raise Exception(err)

        

# --- CREATE DATAFRAMES ---

def create_filled_orders_df(orders):
    filled_orders_list = []
    for order in orders:
        created_ts = float(order['info']['createdTime'])/1000
        updated_ts = float(order['info']['updatedTime'])/1000
        order_data = {
            'order_id': order['info']['orderId'],
            'symbol': order['info']['symbol'],
            'avg_price': order['info']['avgPrice'],
            'quantity': order['info']['qty'],
            'side': order['info']['side'],
            'order_type': order['info']['orderType'],
            'stop_order_type': order['info']['stopOrderType'] if order['info']['stopOrderType'] != 'UNKNOWN' else '-',
            'limit_price': order['info']['price'],
            'sl_price':order['info']['stopLoss'],
            'tp_price':order['info']['takeProfit'],
            'status': order['info']['orderStatus'],
            'created_ts': datetime.fromtimestamp(created_ts, tz = None),
            'updated_ts': datetime.fromtimestamp(updated_ts, tz = None)
        }
        if order['info']['orderStatus']=='Filled':
            filled_orders_list.append(order_data)
    df_filled_orders = pd.DataFrame(filled_orders_list)
    return df_filled_orders

def create_open_orders_df(orders):
    open_orders_list = []
    for order in orders:
        created_ts = float(order['info']['createdTime'])/1000
        updated_ts = float(order['info']['updatedTime'])/1000
        order_data = {
            'order_id': order['info']['orderId'],
            'symbol': order['info']['symbol'],
            'avg_price': order['info']['avgPrice'],
            'quantity': order['info']['qty'],
            'side': order['info']['side'],
            'order_type': order['info']['orderType'],
            'stop_order_type': order['info']['stopOrderType'] if order['info']['stopOrderType'] != 'UNKNOWN' else '-',
            'limit_price': order['info']['price'],
            'sl_price':order['info']['stopLoss'],
            'tp_price':order['info']['takeProfit'],
            'status': order['info']['orderStatus'],
            'created_ts': datetime.fromtimestamp(created_ts, tz = None),
            'updated_ts': datetime.fromtimestamp(updated_ts, tz = None)
        }
        open_orders_list.append(order_data)
    df_open_orders = pd.DataFrame(open_orders_list)
    return df_open_orders

def create_open_positions_df(positions):
    open_positions_list=[]
    for position in positions:
        created_ts = float(position['info']['createdTime'])/1000
        updated_ts = float(position['info']['updatedTime'])/1000
        order_data = {
            'position_id': position['info']['positionIdx'],
            'symbol': position['info']['symbol'],
            'avg_price': position['info']['avgPrice'],
            'size': position['info']['size'],
            'side': position['info']['side'],
            'leverage': position['info']['leverage'],
            'status': position['info']['positionStatus'],
            'created_ts': datetime.fromtimestamp(created_ts, tz = None),
            'updated_ts': datetime.fromtimestamp(updated_ts, tz = None)
        }
        open_positions_list.append(order_data)
    df_open_positions = pd.DataFrame(open_positions_list)
    return df_open_positions


