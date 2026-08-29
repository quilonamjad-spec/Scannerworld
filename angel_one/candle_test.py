import os
from datetime import datetime, timedelta

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect


load_dotenv()

API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PIN = os.getenv("ANGEL_PIN")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")


def login():
    totp = pyotp.TOTP(TOTP_SECRET).now()

    smart_api = SmartConnect(api_key=API_KEY)

    response = smart_api.generateSession(
        CLIENT_ID,
        PIN,
        totp
    )

    if response.get("status") is not True:
        raise RuntimeError(
            f"Angel One login failed: {response}"
        )

    return smart_api


def main():
    print("\nANGEL ONE — CANDLE TEST")
    print("========================")

    smart_api = login()
    print("Authentication : OK")

    # Step 1: Find TCS token
    search = smart_api.searchScrip("NSE", "TCS")

    print("\nSCRIP SEARCH RESPONSE:")
    print(search)

    if not search.get("status") or not search.get("data"):
        raise RuntimeError("Could not find TCS on NSE")

    # Use the first matching NSE result
    result = next(
        (
            item
            for item in search["data"]
            if item["tradingsymbol"] == "TCS-EQ"
        ),
        None
    )

    if result is None:
        raise RuntimeError("TCS-EQ was not found")



    symbol = result["tradingsymbol"]
    token = result["symboltoken"]

    print("\nSelected instrument:")
    print("Trading symbol :", symbol)
    print("Symbol token   :", token)

    # Step 2: Request a small historical window
    today = datetime.now()
    previous_day = today - timedelta(days=1)

    from_date = previous_day.strftime("%Y-%m-%d") + " 09:15"
    to_date = previous_day.strftime("%Y-%m-%d") + " 10:00"

    params = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": "FIVE_MINUTE",
        "fromdate": from_date,
        "todate": to_date,
    }

    print("\nCANDLE REQUEST:")
    print(params)

    response = smart_api.getCandleData(params)

    print("\nRAW CANDLE RESPONSE:")
    print(response)


if __name__ == "__main__":
    main()
