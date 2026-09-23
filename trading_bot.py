"""
Simple Moving Average Crossover Trading Bot for Binance
==========================================================
Trades BTC/USDT using a short-MA / long-MA crossover signal.
"""

import os
import time
import logging
from datetime import datetime

import pandas as pd
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

# =========================== CONFIG ===========================

DRY_RUN = False  # LIVE — real orders will be placed with real funds

SYMBOLS = ["BTCUSDT"]

ALLOCATION_PER_SYMBOL_USDT = 7.0

SHORT_MA_PERIOD = 3
LONG_MA_PERIOD = 8
KLINE_INTERVAL = Client.KLINE_INTERVAL_5MINUTE
LOOKBACK = "1 day ago UTC"

CHECK_INTERVAL_SECONDS = 60 * 5

MAX_DAILY_LOSS_PCT = 5.0
MAX_POSITION_PCT_OF_BALANCE = 0.5

# ================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("trading_bot")


def get_client() -> Client:
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError(
            "Missing BINANCE_API_KEY / BINANCE_API_SECRET environment variables."
        )
    return Client(api_key, api_secret)


def get_price_history(client: Client, symbol: str) -> pd.DataFrame:
    klines = client.get_historical_klines(symbol, KLINE_INTERVAL, LOOKBACK)
    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )
    df["close"] = df["close"].astype(float)
    return df


def compute_signal(df: pd.DataFrame) -> str:
    df = df.copy()
    df["short_ma"] = df["close"].rolling(SHORT_MA_PERIOD).mean()
    df["long_ma"] = df["close"].rolling(LONG_MA_PERIOD).mean()

    if len(df) < LONG_MA_PERIOD + 2:
        return "HOLD"

    prev_short, prev_long = df["short_ma"].iloc[-2], df["long_ma"].iloc[-2]
    curr_short, curr_long = df["short_ma"].iloc[-1], df["long_ma"].iloc[-1]

    if prev_short <= prev_long and curr_short > curr_long:
        return "BUY"
    if prev_short >= prev_long and curr_short < curr_long:
        return "SELL"
    return "HOLD"


def get_symbol_balance_usdt(client: Client, symbol: str) -> float:
    balance = client.get_asset_balance(asset="USDT")
    return float(balance["free"]) if balance else 0.0


def get_total_portfolio_value_usdt(client: Client, symbols: list) -> float:
    total = get_symbol_balance_usdt(client, "USDT")
    for symbol in symbols:
        base_asset = symbol.replace("USDT", "")
        try:
            asset_balance = client.get_asset_balance(asset=base_asset)
            asset_amount = float(asset_balance["free"]) + float(asset_balance["locked"])
            if asset_amount > 0:
                price = float(client.get_symbol_ticker(symbol=symbol)["price"])
                total += asset_amount * price
        except Exception as e:
            log.warning(f"Could not price {base_asset} for portfolio value: {e}")
    return total


def get_day_start_balance(state: dict, current_balance: float) -> float:
    today = datetime.utcnow().date()
    if state.get("day") != today:
        state["day"] = today
        state["day_start_balance"] = current_balance
    return state["day_start_balance"]


def get_lot_size_precision(client: Client, symbol: str) -> int:
    info = client.get_symbol_info(symbol)
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            step_size = f["stepSize"]
            if "." in step_size:
                decimals = len(step_size.rstrip("0").split(".")[1])
            else:
                decimals = 0
            return decimals
    return 5


def get_held_quantity(client: Client, symbol: str) -> float:
    base_asset = symbol.replace("USDT", "")
    balance = client.get_asset_balance(asset=base_asset)
    return float(balance["free"]) if balance else 0.0


def place_order(client: Client, symbol: str, side: str, usdt_amount: float):
    if DRY_RUN:
        log.info(f"[DRY RUN] Would place {side} order on {symbol} for ~{usdt_amount:.2f} USDT")
        return None

    log.info(f"Placing LIVE {side} order on {symbol} for ~{usdt_amount:.2f} USDT")
    try:
        decimals = get_lot_size_precision(client, symbol)
        factor = 10 ** decimals

        if side == "SELL":
            raw_quantity = get_held_quantity(client, symbol)
        else:
            price = float(client.get_symbol_ticker(symbol=symbol)["price"])
            raw_quantity = usdt_amount / price

        quantity = int(raw_quantity * factor) / factor
        quantity_str = f"{quantity:.{decimals}f}"

        if quantity <= 0:
            log.warning(f"Computed quantity is zero for {side} {symbol} — skipping order.")
            return None

        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side == "BUY" else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity_str,
        )
        log.info(f"Order result: {order}")
        return order
    except Exception as e:
        log.error(f"Order failed for {symbol}: {e}")
        return None


def detect_existing_position(client: Client, symbol: str) -> str:
    base_asset = symbol.replace("USDT", "")
    try:
        balance = client.get_asset_balance(asset=base_asset)
        amount = float(balance["free"]) + float(balance["locked"])
        price = float(client.get_symbol_ticker(symbol=symbol)["price"])
        value_usdt = amount * price
        if value_usdt >= 1.0:
            log.info(f"Detected existing {base_asset} position worth ~{value_usdt:.2f} USDT — marking as LONG")
            return "LONG"
    except Exception as e:
        log.warning(f"Could not check existing position for {symbol}: {e}")
    return None


def run():
    client = get_client()
    positions = {s: detect_existing_position(client, s) for s in SYMBOLS}
    state = {}

    log.info(f"Starting bot. DRY_RUN={DRY_RUN}. Symbols={SYMBOLS}")
    if not DRY_RUN:
        log.warning("LIVE TRADING IS ENABLED. Real orders will be placed.")

    while True:
        try:
            portfolio_value = get_total_portfolio_value_usdt(client, SYMBOLS)
            day_start_balance = get_day_start_balance(state, portfolio_value)

            if day_start_balance > 0:
                daily_pct_change = (portfolio_value - day_start_balance) / day_start_balance * 100
                if daily_pct_change <= -MAX_DAILY_LOSS_PCT:
                    log.warning(
                        f"Daily loss limit hit ({daily_pct_change:.2f}%). "
                        f"Pausing trading until next UTC day."
                    )
                    time.sleep(CHECK_INTERVAL_SECONDS)
                    continue

            for symbol in SYMBOLS:
                df = get_price_history(client, symbol)
                signal = compute_signal(df)
                last_price = df["close"].iloc[-1]
                log.info(f"{symbol}: price={last_price:.2f} signal={signal} position={positions[symbol]}")

                if signal == "BUY" and positions[symbol] is None:
                    result = place_order(client, symbol, "BUY", ALLOCATION_PER_SYMBOL_USDT)
                    if result is not None:
                        positions[symbol] = "LONG"
                    else:
                        log.warning(f"BUY order did not succeed for {symbol} — position state unchanged.")
                elif signal == "SELL" and positions[symbol] == "LONG":
                    result = place_order(client, symbol, "SELL", ALLOCATION_PER_SYMBOL_USDT)
                    if result is not None:
                        positions[symbol] = None
                    else:
                        log.warning(f"SELL order did not succeed for {symbol} — position state unchanged.")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
            break
        except Exception as e:
            log.error(f"Unexpected error in main loop: {e}")
            time.sleep(30)


if __name__ == "__main__":
    run()