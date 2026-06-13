import json
import requests

# ==================================================
# CONFIG
# ==================================================

TENANT_ID = "370"

PAYLOAD = {
    "tenantId": 370,
    "order": [],      # try "asc" if desc fails
    "skip": 0,            # pagination offset
    "limit": 100          # records per page
}

URL = "https://admin-dashboard.grow-matic.com/api/v1/live-sessions/last-synced"

COOKIES = {
    "userId": "s%3A63490c42252ad0001b2051f8.0tEzEBbNxKErXgsa3p8votxAzi2ayGgrw8H0cFSu5dc",
    "express:sess": "eyJwYXNzcG9ydCI6eyJ1c2VyIjoiNjM0OTBjNDIyNTJhZDAwMDFiMjA1MWY4In19",
    "express:sess.sig": "T2dUQ0VJlNBxraZjV0ckmbC9qkE",
    "access_token": "s%3AJ7LJcgKA1DfhMQSAs6KWqdKEN9BQIxvII6Yiou5lnB71jA19lX7aZ4HAN4mpAHyB.lLNR22p3B%2Bl4eHUw%2FgcbKoyvWmUHSfp5VcdjtAkT67c",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ==================================================
# REQUEST
# ==================================================

session = requests.Session()
session.headers.update(HEADERS)
session.cookies.update(COOKIES)

try:
    response = session.post(
        URL,
        json=PAYLOAD,
        timeout=20
    )

    print("Status Code:", response.status_code)

    try:
        data = response.json()

        print("\nResponse:\n")
        print(json.dumps(data, indent=4))

        with open("last_synced.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print("\nSaved -> last_synced.json")

    except Exception:
        print("\nNon JSON Response:")
        print(response.text)

except Exception as e:
    print("Error:", e)