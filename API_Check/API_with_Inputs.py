import json
import os
from datetime import datetime, timedelta
import requests

# ==============================================================================
# CONFIGURATION BLOCK
# ==============================================================================
# 1. Update this value with the tenant ID you found in tenant.json or tenant_list.json
TARGET_TENANT_ID = "370"

# 2. Define the date range (Currently defaults to the last 30 days)
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

# Formats date to standard ISO 8601 string (e.g., "2026-05-12T14:30:00.000Z")
# Change to .strftime("%Y-%m-%d") if the server prefers simple dates without time.
FROM_DATE = start_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
TO_DATE = end_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

# Specific filtered endpoints target list
TARGET_APIS = {
    "app_version_use_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/app-version-use-count",
    "cumulative_tenant_count_history": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/cumulative-tenant-count-history",
    "good_distance_sessions_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-distance-sessions-count",
    "good_usage_onoff_duty_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-usage-onoff-duty-count",
    "high_battery_usage_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/high-battery-usage-count",
    "missing_gps_sessions": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/missing-gps-sessions",
    "start_with_low_battery_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/start-with-low-battery-count",
}

COOKIES = {
    "userId": "s%3A63490c42252ad0001b2051f8.0tEzEBbNxKErXgsa3p8votxAzi2ayGgrw8H0cFSu5dc",
    "express:sess": "eyJwYXNzcG9ydCI6eyJ1c2VyIjoiNjM0OTBjNDIyNTJhZDAwMDFiMjA1MWY4In19",
    "express:sess.sig": "T2dUQ0VJlNBxraZjV0ckmbC9qkE",
    "access_token": "s%3AJ7LJcgKA1DfhMQSAs6KWqdKEN9BQIxvII6Yiou5lnB71jA19lX7aZ4HAN4mpAHyB.lLNR22p3B%2Bl4eHUw%2FgcbKoyvWmUHSfp5VcdjtAkT67c",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}


def main():
    output_dir = "dashboard_responses"
    os.makedirs(output_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(COOKIES)

    print(f"--- Dashboard Analytics Retrieval ---")
    print(f"Tenant Target: {TARGET_TENANT_ID}")
    print(f"Time Range:    {FROM_DATE} --> {TO_DATE}\n")

    # The payload structure explicitly satisfying the backend requirements
    for name, url in TARGET_APIS.items():
        
        if name == "cumulative_tenant_count_history":
            payload_body = {
                "fromDate": FROM_DATE,
                "toDate": TO_DATE,
            }
        else:
            payload_body = {
                "tenantId": TARGET_TENANT_ID,
                "fromDate": FROM_DATE,
                "toDate": TO_DATE,
            }

        print(f"Requesting data for: {name}...")

        try:
            response = session.post(
                url,
                timeout=12,
                json=payload_body
            )

            try:
                data = response.json()
                is_json = True
            except ValueError:
                data = {"raw_text": response.text}
                is_json = False

            output_structure = {
                "__metadata__": {
                "endpoint_name": name,
                "url": url,
                "status_code": response.status_code,
                "sent_payload": payload_body,
                },
                "response_data": data,
            }

            file_path = os.path.join(output_dir, f"{name}.json")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output_structure, f, indent=4, ensure_ascii=False)

            if response.status_code == 200 and is_json:
                print(f"  ✅ Success -> Saved to {file_path}")
            else:
                print(
                    f"  ⚠️ Completed with status {response.status_code}. Verify content inside {file_path}"
                )

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request failed for {name}: {e}")


if __name__ == "__main__":
    if TARGET_TENANT_ID == "YOUR_ACTUAL_TENANT_ID_HERE":
        print(
            "🛑 Error: Please update TARGET_TENANT_ID at the top of the file before running."
        )
    else:
        main()