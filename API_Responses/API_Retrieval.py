import json
import os
import requests

# Your extracted endpoint mapping
APIS = {
    "high_battery_usage_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/high-battery-usage-count",
    "good_usage_onoff_duty_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-usage-onoff-duty-count",
    "missing_gps_sessions": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/missing-gps-sessions",
    "app_version_use_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/app-version-use-count",
    "notification_events": "https://admin-dashboard.grow-matic.com/api/v1/event/notification",
    "missing_gps_events": "https://admin-dashboard.grow-matic.com/api/v1/event/missing-gps",
    "bad_app_settings": "https://admin-dashboard.grow-matic.com/api/v1/event/bad-app-settings",
    "good_distance_sessions_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-distance-sessions-count",
    "start_with_low_battery_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/start-with-low-battery-count",
    "tenant": "https://admin-dashboard.grow-matic.com/api/tenant",
    "user_profile": "https://admin-dashboard.grow-matic.com/api/user/profile",
    "tenant_config_count": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/tenant-config-count",
    "most_on_duty_users": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/most-on-duty-users",
    "cumulative_tenant_count_history": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/cumulative-tenant-count-history",
    "all_tenants": "https://admin-dashboard.grow-matic.com/api/tenants/get-all-tenants",
    "tenant_list": "https://admin-dashboard.grow-matic.com/api/v1/dashboard/tenant-list",
    "last_synced": "https://admin-dashboard.grow-matic.com/api/v1/live-sessions/last-synced",
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
    output_dir = "api_responses"
    os.makedirs(output_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(COOKIES)

    for name, url in APIS.items():
        print(f"\nProcessing: {name}...")

        # Changed order: Try POST first since dashboard/analytics APIs predominantly use POST
        # to accept query filter bodies.
        methods = ["POST", "GET"]

        for method in methods:
            try:
                # Dashboard APIs often expect body filters. If you notice specific parameters
                # in your browser network tab (like tenantId, fromDate, toDate), put them here.
                payload_data = {}

                response = session.request(
                    method, url, timeout=10, json=payload_data
                )

                # Parse data safely
                try:
                    payload_json = response.json()
                    is_json = True
                except ValueError:
                    payload_json = {"raw_text": response.text}
                    is_json = False

                # Handle the case where the server replies with 200 OK but the JSON content explicitly
                # states that the method is unhandled or invalid.
                error_msg = ""
                if is_json and "errorMessage" in payload_json:
                    error_msg = payload_json["errorMessage"]

                if "There is no method to handle" in error_msg:
                    print(
                        f"⚠️ Server returned unhandled method error for {method}. Trying alternative..."
                    )
                    continue  # Break out and try the next method in the list

                # Construct execution context package
                output_structure = {
                    "__metadata__": {
                        "endpoint_alias": name,
                        "request_url": url,
                        "resolved_method": method,
                        "http_status_code": response.status_code,
                        "content_is_native_json": is_json,
                    },
                    "payload": payload_json,
                }

                file_path = os.path.join(output_dir, f"{name}.json")
                with open(file_path, "w", encoding="utf-8") as json_file:
                    json.dump(
                        output_structure, json_file, indent=4, ensure_ascii=False
                    )

                print(
                    f"✅ Saved response to {file_path} (Method: {method}, Status: {response.status_code})"
                )
                break  # Successfully handled, skip trying remaining methods for this API

            except requests.exceptions.RequestException as error:
                print(f"❌ Network processing failed for {name}: {error}")
                break


if __name__ == "__main__":
    main()