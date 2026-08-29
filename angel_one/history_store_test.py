import pandas as pd

from angel_one.history_store import HistoryStore


store = HistoryStore()

test_data = pd.DataFrame(
    [
        {
            "Datetime": "2026-08-28 09:15:00+05:30",
            "Open": 2272.0,
            "High": 2299.5,
            "Low": 2263.3,
            "Close": 2293.4,
            "Volume": 239540,
        },
        {
            "Datetime": "2026-08-28 09:20:00+05:30",
            "Open": 2293.4,
            "High": 2305.0,
            "Low": 2288.0,
            "Close": 2301.0,
            "Volume": 150000,
        },
    ]
)

added = store.save_candles(
    "TCS",
    test_data,
)

print("\nHISTORY STORE TEST")
print("==================")

print("Database:", store.db_path)
print("New candles added:", added)
print("Total TCS candles:", store.count_candles("TCS"))

print("\nLatest timestamp:")
print(store.get_latest_timestamp("TCS"))

print("\nRetrieved data:")
print(
    store.get_candles("TCS").to_string(
        index=False
    )
)
