import os
import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect


load_dotenv()

API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PIN = os.getenv("ANGEL_PIN")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")


def main():
    print("\nANGEL ONE HANDSHAKE")
    print("-------------------")

    if not all([API_KEY, CLIENT_ID, PIN, TOTP_SECRET]):
        print("ERROR: Missing Angel One credentials in .env")
        return

    try:
        totp = pyotp.TOTP(TOTP_SECRET).now()

        print("Generating TOTP : OK")
        print("Connecting       : ...")

        smart_api = SmartConnect(api_key=API_KEY)

        response = smart_api.generateSession(
            CLIENT_ID,
            PIN,
            totp
        )

        if response.get("status") is True:
            print("Authentication   : OK")
            print("Session          : OK")
            print("\nANGEL ONE HANDSHAKE SUCCESS")

        else:
            print("Authentication   : FAILED")
            print("Message          :", response.get("message"))
            print("Error code       :", response.get("errorcode"))

    except Exception as e:
        print("\nANGEL ONE HANDSHAKE FAILED")
        print("Error:", str(e))


if __name__ == "__main__":
    main()
