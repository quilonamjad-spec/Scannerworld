from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger

from .data_provider import AngelOneProvider


SYMBOL = "TCS"

CORRELATION_ID = "scanner2-test"
MODE = 2          # LTP mode
EXCHANGE_TYPE = 1 # NSE


def main():

    print()
    print("=" * 70)
    print("ANGEL ONE → WEBSOCKET TEST")
    print("=" * 70)
    print()

    # -----------------------------------------------------
    # Login using our existing provider
    # -----------------------------------------------------

    provider = AngelOneProvider()

    print("Logging into Angel One...")
    login_response = provider.login()

    print("Authentication : OK")

    auth_token = login_response["data"]["jwtToken"]
    feed_token = provider.smart_api.getfeedToken()

    print("Feed token     : OK")

    # -----------------------------------------------------
    # Resolve the normal symbol through our existing wrapper
    # -----------------------------------------------------

    instrument = provider.resolve_symbol(SYMBOL)

    print()
    print("Symbol         :", SYMBOL)
    print("Trading symbol :", instrument["tradingsymbol"])
    print("Symbol token   :", instrument["symboltoken"])
    print()

    # -----------------------------------------------------
    # WebSocket
    # -----------------------------------------------------

    sws = SmartWebSocketV2(
        auth_token,
        provider.api_key,
        provider.client_id,
        feed_token,
    )

    token_list = [
        {
            "exchangeType": EXCHANGE_TYPE,
            "tokens": [
                instrument["symboltoken"]
            ],
        }
    ]

    def on_open(wsapp):
        print()
        print("WEBSOCKET OPEN")
        print("Subscribing to", SYMBOL)
        print()

        sws.subscribe(
            CORRELATION_ID,
            MODE,
            token_list,
        )

    def on_data(wsapp, message):

        print()
        print("=" * 70)
        print("TICK RECEIVED")
        print("=" * 70)

        print("Message type:", type(message))
        print("Complete message:")
        print(message)

        print("=" * 70)

    def on_error(wsapp, error):

        print()
        print("WEBSOCKET ERROR")
        print(error)

    def on_close(wsapp):

        print()
        print("WEBSOCKET CLOSED")

    sws.on_open = on_open
    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = on_close

    print("Connecting to Angel One WebSocket...")
    print()

    sws.connect()


if __name__ == "__main__":
    main()
