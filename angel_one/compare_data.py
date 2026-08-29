import os
from datetime import datetime

import pandas as pd
import pyotp
import yfinance as yf
from dotenv import load_dotenv
from SmartApi import SmartConnect


load_dotenv()

API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PIN = os.getenv("ANGEL_PIN")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")


def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()

    smart_api = SmartConnect(api_key=API_KEY)

    response = smart_api.generateSession(
        CLIENT_ID,
        PIN,
        totp
    )

    if response.get("status") is not True:
        raise RuntimeError(f"Angel One login failed: {response}")

    return smart_api


def get_angel_data():
    smart_api = angel_login()

    params = {
        "exchange": "NSE",
        "symboltoken": "11536",
        "interval": "FIVE_MINUTE",
        "fromdate": "2026-08-28 09:15",
        "todate": "2026-08-28 10:00",
    }

    response = smart_api.getCandleData(params)

    if response.get("status") is not True:
        raise RuntimeError(f"Angel One candle request failed: {response}")

    df = pd.DataFrame(
        response["data"],
        columns=["Datetime", "Open", "High", "Low", "Close", "Volume"]
    )

    df["Datetime"] = pd.to_datetime(df["Datetime"])

    return df


def get_yahoo_data():
    df = yf.download(
        "TCS.NS",
        start=datetime(2026, 8, 28, 9, 15),
        end=datetime(2026, 8, 28, 10, 1),
        interval="5m",
        progress=False,
        auto_adjust=False,
    )

    if df.empty:
        raise RuntimeError("Yahoo returned no data")

    # Yahoo can return a MultiIndex depending on the yfinance version.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    df = df.rename(columns={
        "Datetime": "Datetime",
        "Open": "Open",
        "High": "High",
        "Low": "Low",
        "Close": "Close",
        "Volume": "Volume",
    })

    df["Datetime"] = pd.to_datetime(df["Datetime"])

    return df[[
        "Datetime",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]]


def main():
    print("\nANGEL ONE vs YAHOO")
    print("==================")

    angel = get_angel_data()
    yahoo = get_yahoo_data()

    print("\nANGEL ONE DATA")
    print(angel.to_string(index=False))

    print("\nYAHOO DATA")
    print(yahoo.to_string(index=False))

    print("\nCOMPARISON")

    merged = pd.merge(
        angel,
        yahoo,
        on="Datetime",
        how="outer",
        suffixes=("_Angel", "_Yahoo")
    ).sort_values("Datetime")

    print(merged.to_string(index=False))


if __name__ == "__main__":
    main()
