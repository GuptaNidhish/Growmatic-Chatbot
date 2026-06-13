"""
Grow-Matic Admin Intelligence Chatbot
======================================
A Streamlit chatbot that allows managers to ask plain-English questions about
application health and tenant metrics. Uses a 3-step pipeline:
  1. Intent Mapping  (Gemini) → selects the right API endpoints
  2. Data Fetching   (Python) → calls live API endpoints via `requests` with local mock fallbacks
  3. Response Synthesis (Gemini) → streams an executive-level textual summary
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st
import requests
import markdown
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
load_dotenv()
APIS: dict[str, str] = {
    "high_battery_usage_count":         "https://admin-dashboard.grow-matic.com/api/v1/dashboard/high-battery-usage-count",
    "good_usage_onoff_duty_count":      "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-usage-onoff-duty-count",
    "missing_gps_sessions":             "https://admin-dashboard.grow-matic.com/api/v1/dashboard/missing-gps-sessions",
    "app_version_use_count":            "https://admin-dashboard.grow-matic.com/api/v1/dashboard/app-version-use-count",
    "notification_events":              "https://admin-dashboard.grow-matic.com/api/v1/event/notification",
    "missing_gps_events":               "https://admin-dashboard.grow-matic.com/api/v1/event/missing-gps",
    "bad_app_settings":                 "https://admin-dashboard.grow-matic.com/api/v1/event/bad-app-settings",
    "good_distance_sessions_count":     "https://admin-dashboard.grow-matic.com/api/v1/dashboard/good-distance-sessions-count",
    "start_with_low_battery_count":     "https://admin-dashboard.grow-matic.com/api/v1/dashboard/start-with-low-battery-count",
    "tenant":                           "https://admin-dashboard.grow-matic.com/api/tenant",
    "user_profile":                     "https://admin-dashboard.grow-matic.com/api/user/profile",
    "tenant_config_count":              "https://admin-dashboard.grow-matic.com/api/v1/dashboard/tenant-config-count",
    "most_on_duty_users":               "https://admin-dashboard.grow-matic.com/api/v1/dashboard/most-on-duty-users",
    "cumulative_tenant_count_history":  "https://admin-dashboard.grow-matic.com/api/v1/dashboard/cumulative-tenant-count-history",
    "all_tenants":                      "https://admin-dashboard.grow-matic.com/api/tenants/get-all-tenants",
    "tenant_list":                      "https://admin-dashboard.grow-matic.com/api/v1/dashboard/tenant-list",
    "last_synced":                      "https://admin-dashboard.grow-matic.com/api/v1/live-sessions/last-synced",
}

API_DESCRIPTIONS = {
    "high_battery_usage_count":        "Battery drain statistics – sessions with high battery usage (>10%/hr), unique users affected, percentages",
    "good_usage_onoff_duty_count":     "Session duration categories (short <10 min, medium 10 min–3 hrs, long sessions) and on/off-duty usage quality",
    "missing_gps_sessions":            "Sessions with missing/lost GPS coverage – total sessions, hours missed, unique affected users, GPS off-hours",
    "app_version_use_count":           "App version adoption – how many sessions ran on each app version, unique users per version",
    "notification_events":             "Push notification events sent to users (GPS tracking alerts, etc.) with tenant and user details",
    "missing_gps_events":              "Detailed event log of each individual GPS-missing incident with device model, OS, and time info",
    "bad_app_settings":                "Events where app was running with bad/incorrect settings (bad battery optimisation, permissions, etc.)",
    "good_distance_sessions_count":    "Distance-based session quality categories and total session counts",
    "start_with_low_battery_count":    "Sessions that started with low battery (<15%, 15-45%, >45%) – potential session interruption risk",
    "tenant":                          "Current tenant configuration, theme, locale, version, and internal service URLs",
    "user_profile":                    "Logged-in admin user profile: name, email, roles, avatar",
    "tenant_config_count":             "Count of tenants by config type (tally vs normal) with tenant IDs",
    "most_on_duty_users":              "Leaderboard of users who spent the most time on-duty in the selected period",
    "cumulative_tenant_count_history": "Historical growth of tenant count over time (cumulative trend)",
    "all_tenants":                     "Complete list of all registered tenants with their details",
    "tenant_list":                     "Filtered/paginated tenant list for a given date range",
    "last_synced":                     "Timestamp of when live session data was last synced from the tracking system",
}

GEMINI_MODEL = "gemini-2.5-flash"

COOKIES: dict[str, str] = {
    "userId":           "s%3A63490c42252ad0001b2051f8.0tEzEBbNxKErXgsa3p8votxAzi2ayGgrw8H0cFSu5dc",
    "express:sess":     "eyJwYXNzcG9ydCI6eyJ1c2VyIjoiNjM0OTBjNDIyNTJhZDAwMDFiMjA1MWY4In19",
    "express:sess.sig": "T2dUQ0VJlNBxraZjV0ckmbC9qkE",
    "access_token":     "s%3AJ7LJcgKA1DfhMQSAs6KWqdKEN9BQIxvII6Yiou5lnB71jA19lX7aZ4HAN4mpAHyB.lLNR22p3B%2Bl4eHUw%2FgcbKoyvWmUHSfp5VcdjtAkT67c",
}


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg-primary:    #0a0e17;
    --bg-secondary:  #111622;
    --bg-card:       #181f2f;
    --border:        #26354a;
    --accent-green:  #10b981;
    --accent-blue:   #3b82f6;
    --accent-purple: #8b5cf6;
    --accent-orange: #f59e0b;
    --text-primary:  #f3f4f6;
    --text-muted:    #9ca3af;
    --user-bubble:   linear-gradient(135deg, #2563eb, #1d4ed8);
    --bot-bubble:    rgba(24, 31, 47, 0.7);
    --shadow:        0 8px 32px 0 rgba(0, 0, 0, 0.37);
    --radius:        16px;
}

html, body, [class*="css"] { 
    font-family: 'Inter', sans-serif !important; 
}
.stApp { 
    background: radial-gradient(circle at top right, #1e1b4b 0%, #0a0e17 60%) !important; 
    color: var(--text-primary) !important; 
}
.block-container { 
    padding: 2rem 3rem 4rem !important; 
    max-width: 1150px; 
}

[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .stMarkdown h4 { 
    color: var(--text-primary) !important; 
}

.brand-header {
    display: flex; align-items: center; gap: 16px;
    padding: 1.5rem 2rem;
    background: rgba(24, 31, 47, 0.6) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
}
.brand-icon { font-size: 2.2rem; }
.brand-title {
    font-size: 1.6rem; font-weight: 700;
    background: linear-gradient(90deg, var(--accent-green), var(--accent-blue));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.brand-sub { font-size: 0.82rem; color: var(--text-muted); margin-top: 2px; }

.chat-container { display: flex; flex-direction: column; gap: 20px; margin-bottom: 1.5rem; }

.msg-row { display: flex; align-items: flex-start; gap: 12px; }
.msg-row.user  { flex-direction: row-reverse; }

.avatar {
    width: 40px; height: 40px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.avatar.user-av { background: var(--user-bubble); color: #fff; }
.avatar.bot-av  { 
    background: rgba(24, 31, 47, 0.8); 
    border: 1px solid var(--border); 
}

.bubble {
    max-width: 85%; padding: 16px 20px;
    border-radius: var(--radius); font-size: 0.92rem; line-height: 1.7;
    box-shadow: var(--shadow);
}
.bubble.user-bubble {
    background: var(--user-bubble) !important; color: #fff !important;
    border-bottom-right-radius: 4px;
}
.bubble.bot-bubble {
    background: var(--bot-bubble) !important; 
    border: 1px solid var(--border) !important;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    color: var(--text-primary) !important; 
    border-bottom-left-radius: 4px;
}

/* Table styling within bot bubble */
.bubble.bot-bubble table {
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
    font-size: 0.85rem;
}
.bubble.bot-bubble th, .bubble.bot-bubble td {
    border: 1px solid var(--border);
    padding: 8px 12px;
    text-align: left;
}
.bubble.bot-bubble th {
    background-color: var(--bg-secondary);
    color: var(--accent-green);
    font-weight: 600;
}
.bubble.bot-bubble tr:nth-child(even) {
    background-color: rgba(255, 255, 255, 0.02);
}

.bubble.bot-bubble ul { margin: 0.5em 0 0.5em 1.3em; padding: 0; }
.bubble.bot-bubble li { margin-bottom: 6px; }
.bubble.bot-bubble strong { color: var(--accent-green); }
.bubble.bot-bubble code {
    background: rgba(16, 185, 129, 0.12); color: var(--accent-green);
    padding: 2px 6px; border-radius: 4px; font-size: 0.85rem;
}

.pipeline-step {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.8rem; color: var(--text-muted); padding: 8px 12px;
    background: var(--bg-secondary); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 12px;
}
.step-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--accent-green);
    animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); box-shadow: 0 0 0 0px rgba(16, 185, 129, 0.4); }
    50%       { opacity: 0.4; transform: scale(0.8); box-shadow: 0 0 8px 2px rgba(16, 185, 129, 0.4); }
}

.metric-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 16px; margin-bottom: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.metric-card .metric-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.6px; }
.metric-card .metric-value { font-size: 1.15rem; font-weight: 600; color: var(--accent-green); margin-top: 3px; }

.stTextInput > div > div > input {
    background: var(--bg-card) !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important;
    padding: 14px 18px !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent-green) !important;
    box-shadow: 0 0 0 2px rgba(16,185,129,.15) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #10b981, #1e3a8a) !important;
    border: 1px solid var(--border) !important; color: var(--text-primary) !important;
    border-radius: var(--radius) !important; font-weight: 600 !important;
    padding: 10px 24px !important; transition: all .2s !important;
}
.stButton > button:hover {
    border-color: var(--accent-green) !important; transform: translateY(-1px);
    box-shadow: 0 4px 20px rgba(16,185,129,.25) !important;
}

.streamlit-expanderHeader { 
    color: var(--text-muted) !important; 
    font-size: 0.82rem !important; 
    background-color: var(--bg-secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
details > summary:hover { color: var(--accent-blue) !important; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

.msg-ts { font-size: 0.7rem; color: var(--text-muted); margin-top: 6px; }
</style>
"""


def _date_range_payload(days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_date   = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"fromDate": from_date, "toDate": to_date}

def load_mock_data(key: str) -> Any:
    """Load cached/mock response data from local files when live API fails."""
    # check in root for last_synced
    if key == "last_synced":
        path = "last_synced.json"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    
    # check in api_responses
    api_path = os.path.join("api_responses", f"{key}.json")
    if os.path.exists(api_path):
        try:
            with open(api_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("payload", data)
        except Exception:
            pass
            
    # check in dashboard_responses
    dash_path = os.path.join("dashboard_responses", f"{key}.json")
    if os.path.exists(dash_path):
        try:
            with open(dash_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("response_data", data)
        except Exception:
            pass
            
    return {"error": f"No mock or cached data found for endpoint: {key}"}
@st.cache_data(show_spinner=False)
def load_tenant_options(force_cached: bool = False) -> list[tuple[str, str]]:
    """Fetch all available tenants and return list of (id, display_name).
    Defaults to cached file if live call fails.
    """
    try:
        url = APIS["tenant_list"]
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not force_cached:
            resp = requests.get(url, headers=headers, cookies=COOKIES, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("result") == 0:
                    tenants = data.get("data", [])
                    options = [(str(t["id"]), f"{t['id']} - {t['name']}") for t in tenants if t.get("id") is not None]
                    if options:
                        return options
    except Exception:
        pass

    # Fallback to local tenant_list.json
    mock_data = load_mock_data("tenant_list")
    if isinstance(mock_data, dict) and mock_data.get("result") == 0:
        tenants = mock_data.get("data", [])
        return [(str(t["id"]), f"{t['id']} - {t['name']}") for t in tenants if t.get("id") is not None]

    # Hardcoded defaults if all else fails
    return [("370", "370 - krystal.grow-matic.com")]

@st.cache_data(show_spinner=False)
def load_user_profile(force_cached: bool = False) -> dict:
    """Fetch current user profile. Fallback to user_profile.json."""
    try:
        url = APIS["user_profile"]
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not force_cached:
            resp = requests.get(url, headers=headers, cookies=COOKIES, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data
    except Exception:
        pass

    mock_data = load_mock_data("user_profile")
    if isinstance(mock_data, dict) and "error" not in mock_data:
        return mock_data

    return {
        "displayName": "Administrator",
        "email": "admin@grow-matic.com",
        "avatar": "",
        "roles": {"Administrator": True}
    }
def make_gemini_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# ── Step 1 – Intent Mapping via Gemini ────────────────────────────────────
# ---------------------------------------------------------------------------

def map_intent_to_apis(
    client: genai.Client,
    user_query: str,
    tenant_id: str,
    date_range_days: int,
) -> dict:
    """Ask Gemini which API endpoints are needed to answer the query.

    Returns:
        {
          "endpoints": ["missing_gps_sessions"],
          "reasoning": "The user is asking about GPS ...",
          "needs_tenant_id": true,
          "needs_date_range": true
        }
    """
    api_catalog = "\n".join(
        f"  - **{k}**: {v}" for k, v in API_DESCRIPTIONS.items()
    )

    prompt = f"""You are an expert API router for the Grow-Matic admin dashboard.
Analyse the manager's question and return a JSON object identifying which API endpoints are needed.

Available endpoints:
{api_catalog}

Rules:
1. Choose the MINIMUM set of endpoints – do not over-fetch.
2. Return ONLY valid raw JSON with exactly these keys:
   - "endpoints"        : list of endpoint key strings from the catalog
   - "reasoning"        : one concise sentence explaining your choice
   - "needs_tenant_id"  : true/false
   - "needs_date_range" : true/false
3. No markdown, no code fences, no extra prose – raw JSON only.
4. If unrelated to APIs return: {{"endpoints":[],"reasoning":"No matching endpoint","needs_tenant_id":false,"needs_date_range":false}}

Manager's question: "{user_query}"
Active tenant ID: {tenant_id}
Date range: last {date_range_days} days

Return JSON only."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    raw = response.text.strip()
    # Strip potential markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)

def fetch_api_data(
    endpoint_keys: list[str],
    tenant_id: str,
    date_range_days: int,
    page_size: int = 50,
    force_cached: bool = False,
) -> dict[str, Any]:
    """Call each required endpoint with session cookies and return raw data.
    Falls back to cached JSON files if live requests fail or return internal database errors.
    """
    results: dict[str, Any] = {}
    
    if force_cached:
        for key in endpoint_keys:
            mock_data = load_mock_data(key)
            if isinstance(mock_data, dict):
                mock_data["__data_source__"] = "cached"
            results[key] = _trim_ids(mock_data)
        return results

    date_payload = _date_range_payload(date_range_days)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Define endpoints mapping explicitly to make requests extremely robust
    # POST endpoints matching analytical queries
    post_anal_endpoints = {
        "high_battery_usage_count", "good_usage_onoff_duty_count", "missing_gps_sessions",
        "app_version_use_count", "good_distance_sessions_count", "start_with_low_battery_count",
        "most_on_duty_users"
    }
    # POST endpoints matching events logs
    post_event_endpoints = {"notification_events", "missing_gps_events", "bad_app_settings"}

    for key in endpoint_keys:
        url = APIS.get(key)
        if not url:
            results[key] = {"error": f"Unknown endpoint key: {key}", "__data_source__": "error"}
            continue

        resp_json = None
        data_source = "live"

        try:
            # 1. Dispatch request with correct HTTP method & payload structure
            if key in post_anal_endpoints:
                payload = {"tenantId": str(tenant_id), **date_payload}
                resp = requests.post(url, json=payload, headers=headers, cookies=COOKIES, timeout=15)
            elif key in post_event_endpoints:
                payload = {"tenantId": str(tenant_id), **date_payload, "page": 1, "limit": page_size}
                resp = requests.post(url, json=payload, headers=headers, cookies=COOKIES, timeout=15)
            elif key == "cumulative_tenant_count_history":
                payload = date_payload.copy()
                resp = requests.post(url, json=payload, headers=headers, cookies=COOKIES, timeout=15)
            elif key == "all_tenants":
                resp = requests.post(url, json={}, headers=headers, cookies=COOKIES, timeout=15)
            elif key == "last_synced":
                try:
                    tid_val = int(tenant_id)
                except ValueError:
                    tid_val = tenant_id
                payload = {"tenantId": tid_val, "order": [], "skip": 0, "limit": page_size}
                resp = requests.post(url, json=payload, headers=headers, cookies=COOKIES, timeout=15)
            else:
                # GET endpoints: tenant, user_profile, tenant_config_count, tenant_list
                resp = requests.get(url, headers=headers, cookies=COOKIES, timeout=15)

            resp.raise_for_status()
            resp_json = resp.json()

            # 2. Check for backend database/TypeError bugs inside successful response
            is_internal_error = False
            if isinstance(resp_json, dict):
                if resp_json.get("result") == -1 or "errorMessage" in resp_json:
                    is_internal_error = True
                elif "message" in resp_json and ("Error" in str(resp_json["message"]) or "property" in str(resp_json["message"])):
                    is_internal_error = True

            if is_internal_error:
                raise ValueError(f"Backend SQL/Code error detected: {resp_json}")
            
            # Trim large payloads
            resp_json = _trim_ids(resp_json)
            if isinstance(resp_json, dict):
                resp_json["__data_source__"] = "live"
            else:
                resp_json = {"data": resp_json, "__data_source__": "live"}
            results[key] = resp_json

        except Exception as exc:
            # 3. Fallback to cached mock data
            mock_data = load_mock_data(key)
            if isinstance(mock_data, dict) and "error" not in mock_data:
                mock_data["__data_source__"] = "cached"
                mock_data["__live_error__"] = str(exc)
                results[key] = _trim_ids(mock_data)
            else:
                results[key] = {
                    "error": f"Live failed ({exc}) and cached file missing: {mock_data.get('error', '')}",
                    "__data_source__": "error"
                }

    return results
def _trim_ids(obj: Any, max_ids: int = 10) -> Any:
    """Recursively truncate long id arrays to keep LLM context manageable."""
    if isinstance(obj, dict):
        trimmed = {}
        for k, v in obj.items():
            if k in {"ids", "uniqueUserIds", "uniqueUsersIds", "totalCountIds"} \
                    and isinstance(v, list) and len(v) > max_ids:
                trimmed[k] = v[:max_ids] + [f"... ({len(v) - max_ids} more)"]
            else:
                trimmed[k] = _trim_ids(v, max_ids)
        return trimmed
    if isinstance(obj, list):
        return [_trim_ids(item, max_ids) for item in obj]
    return obj
def synthesize_response_stream(
    client: genai.Client,
    user_query: str,
    api_data: dict[str, Any],
    intent_meta: dict,
    stream_placeholder,
):
    """Stream the Gemini synthesis into a Streamlit placeholder.

    Returns the full assembled text string when complete.
    """
    data_block = json.dumps(api_data, indent=2)

    prompt = f"""You are an intelligent senior analytics assistant for the Grow-Matic admin dashboard.
You receive raw API data and a manager's question. Produce a clear, concise, executive-level textual summary.

Formatting rules:
- Present numeric statistics in Markdown Tables if there are multiple comparison items (e.g. lists of app versions, tenant configurations, or user leaderboards), which makes metrics much easier to read.
- Use plain text with light markdown (bold for key figures, bullet lists for multiple items).
- Lead with the most important insight or direct answer.
- Include specific numbers and percentages where available.
- Highlight risks or anomalies a manager should act on.
- End with one actionable recommendation if appropriate.
- Keep the response under 400 words unless the data genuinely warrants more.
- Do NOT repeat raw JSON or mention technical implementation details (like endpoints, methods, or database queries).
- If an endpoint returned cached data, summarize it normally without mentioning the word "mock" or "cached fallback" in the final summary.

Manager's question: "{user_query}"
Routing context: {intent_meta.get("reasoning", "")}

Raw API data:
```json
{data_block}
```

Provide a clear, executive-level answer and also deduce meaningfull insights from this data."""

    full_text = ""
    rendered_placeholder = stream_placeholder.empty()

    for chunk in client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=prompt,
    ):
        if chunk.text:
            full_text += chunk.text
            # Parse markdown directly to HTML for real-time preview
            html_preview = markdown.markdown(full_text, extensions=['tables', 'fenced_code'])
            rendered_placeholder.markdown(
                f'<div class="bubble bot-bubble" style="max-width:100%;">{html_preview}</div>',
                unsafe_allow_html=True,
            )

    rendered_placeholder.empty()  # will be re-rendered properly in chat history
    return full_text
def get_overall_data_source(api_data: dict) -> str:
    """Determine overall data source from api_data outcomes."""
    if not api_data:
        return "none"
    sources = [v.get("__data_source__") for v in api_data.values() if isinstance(v, dict)]
    if "cached" in sources:
        return "cached"
    if "error" in sources:
        return "error"
    if "live" in sources:
        return "live"
    return "none"

def run_pipeline(
    client: genai.Client,
    user_query: str,
    tenant_id: str,
    date_range_days: int,
    page_size: int,
    status_callback=None,
    stream_placeholder=None,
    force_cached: bool = False,
) -> tuple[str, dict]:
    """Execute the 3-step pipeline. Returns (final_text, debug_info)."""

    debug: dict[str, Any] = {}

    # ── Step 1: Intent Mapping ──
    if status_callback:
        status_callback("step1", "🔍 Analysing your question…")
    intent = map_intent_to_apis(client, user_query, tenant_id, date_range_days)
    debug["intent"] = intent
    endpoints = intent.get("endpoints", [])

    if not endpoints:
        return (
            "I wasn't able to match your question to any of the available API endpoints. "
            "Try asking about GPS sessions, battery usage, app versions, tenant counts, "
            "or notification events.",
            {"intent": intent, "api_data": {}, "answer": ""},
        )

    # ── Step 2: Data Fetching ──
    if status_callback:
        ep_list = ", ".join(f"`{e}`" for e in endpoints)
        status_callback("step2", f"📡 Fetching data from: {ep_list}…")
    api_data = fetch_api_data(endpoints, tenant_id, date_range_days, page_size, force_cached)
    debug["api_data"] = api_data

    # ── Step 3: Response Synthesis (streaming) ──
    if status_callback:
        status_callback("step3", "✨ Synthesising your answer…")
    answer = synthesize_response_stream(client, user_query, api_data, intent, stream_placeholder)
    debug["answer"] = answer

    return answer, debug


# ---------------------------------------------------------------------------
# ── Suggested quick questions ──────────────────────────────────────────────
# ---------------------------------------------------------------------------

SUGGESTED_QUESTIONS = [
    "How many sessions had missing GPS this month?",
    "Which app versions are users running?",
    "Show me the top users who were most on duty.",
    "How many sessions started with low battery?",
    "What is the state of our tenant configurations?",
    "Are there any bad app settings I should be aware of?",
    "How many GPS tracking notifications were sent recently?",
    "What's the current cumulative tenant growth trend?",
]
def render_sidebar() -> tuple[str, str, int, int, bool, bool]:
    """Render sidebar. Returns (api_key, tenant_id, days, page_size, debug_mode, force_cached)."""
    with st.sidebar:
        st.markdown("### 🌱 Grow-Matic Intelligence")
        st.markdown("---")

        # ── Toggle for offline mode ──
        force_cached = st.toggle("💾 Force Offline/Cached Data", value=False, key="force_cached_toggle")
        
        # ── User Profile ──
        profile = load_user_profile(force_cached=force_cached)
        display_name = profile.get("displayName", "Administrator")
        email = profile.get("email", "admin@grow-matic.com")
        avatar_url = profile.get("avatar", "")

        profile_html = f"""
        <div style="display: flex; align-items: center; gap: 12px; background: var(--bg-card); padding: 12px; border-radius: var(--radius); border: 1px solid var(--border); margin-bottom: 15px; box-shadow: var(--shadow);">
            <img src="{avatar_url if avatar_url else 'https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y'}" style="width: 42px; height: 42px; border-radius: 50%; border: 2px solid var(--accent-green);" />
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.3;">
                <div style="font-weight: 700; font-size: 0.85rem; color: var(--text-primary);">{display_name}</div>
                <div style="font-size: 0.72rem; color: var(--text-muted);">{email}</div>
            </div>
        </div>
        """
        st.markdown(profile_html, unsafe_allow_html=True)
        st.markdown("---")

        # ── Gemini API Key ──
        # ── Gemini API Key ──
        st.markdown("#### 🔑 Gemini API Key")

        api_key = os.getenv("GEMINI_API_KEY", "")

        if api_key:
            st.success("✅ API key loaded from .env")
        else:
            st.error("❌ GEMINI_API_KEY not found in .env")
        st.markdown("---")

        # ── Cookie auth indicator ──
        st.markdown("#### 🍪 Backend Auth")
        st.markdown(
            "<div class='metric-card' style='border-color:#10b981;'>"
            "<div class='metric-label'>Session cookies</div>"
            "<div class='metric-value' style='font-size:0.85rem; color:#10b981;'>✅ Authenticated</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Tenant Selection dropdown ──
        st.markdown("#### 🏢 Tenant Settings")
        tenant_options = load_tenant_options(force_cached=force_cached)
        
        # Default index helper
        default_idx = 0
        for idx, (tid, _) in enumerate(tenant_options):
            if tid == "370":
                default_idx = idx
                break

        selected_tenant = st.selectbox(
            "Select Active Tenant",
            options=tenant_options,
            index=default_idx,
            format_func=lambda x: x[1],
            key="sidebar_tenant_selectbox",
        )
        tenant_id = selected_tenant[0]

        date_range_days = st.slider(
            "Date Range (days)", min_value=1, max_value=90, value=30,
            step=1, key="sidebar_date_range",
        )
        page_size = st.slider(
            "Max records per endpoint", min_value=10, max_value=200,
            value=50, step=10, key="sidebar_page_size",
        )

        st.markdown("---")

        debug_mode = st.toggle("🔬 Show debug info", value=False, key="sidebar_debug")

        st.markdown("---")

        # ── Session stats ──
        st.markdown("#### 📊 Session Stats")
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Messages this session</div>
                <div class="metric-value">{len(st.session_state.get("messages", []))}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Active tenant ID</div>
                <div class="metric-value">{tenant_id}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Date window</div>
                <div class="metric-value">Last {date_range_days}d</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        if st.button("🗑️ Clear chat", use_container_width=True, key="clear_chat_btn"):
            st.session_state.messages = []
            st.session_state.debug_data = []
            st.rerun()

        st.markdown(
            f"<div style='font-size:0.7rem;color:#9ca3af;text-align:center;margin-top:12px;'>"
            f"Powered by Gemini ({GEMINI_MODEL}) · Grow-Matic v1.0"
            "</div>",
            unsafe_allow_html=True,
        )

    return api_key, tenant_id, date_range_days, page_size, debug_mode, force_cached


# ---------------------------------------------------------------------------
# ── Chat message renderer ──────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def render_message(role: str, content: str, timestamp: str = "", data_source: str = ""):
    """Render a single chat bubble."""
    if role == "user":
        html = f"""
        <div class="msg-row user">
            <div class="avatar user-av">👤</div>
            <div>
                <div class="bubble user-bubble">{content}</div>
                <div class="msg-ts" style="text-align: right;">{timestamp}</div>
            </div>
        </div>"""
    else:
        # Format markdown dynamically using full markdown library (handles tables, fenced code, etc.)
        rendered = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        
        # Render dynamic badge for data source
        badge_html = ""
        if data_source == "live":
            badge_html = '<span style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 20px; font-size: 0.68rem; font-weight: 600; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px;">📡 Live Data</span>'
        elif data_source == "cached":
            badge_html = '<span style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 8px; border-radius: 20px; font-size: 0.68rem; font-weight: 600; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px;">💾 Cached Data (Fallback)</span>'
        
        html = f"""
        <div class="msg-row">
            <div class="avatar bot-av">🌱</div>
            <div>
                <div class="bubble bot-bubble">{rendered}</div>
                <div class="msg-ts" style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                    {timestamp} {badge_html}
                </div>
            </div>
        </div>"""

    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# ── Main ────────────────------------------------------------------------───
# ---------------------------------------------------------------------------

def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    api_key, tenant_id, date_range_days, page_size, debug_mode, force_cached = render_sidebar()

    # ── Header ──
    st.markdown(
        """
        <div class="brand-header">
            <div class="brand-icon">🌱</div>
            <div>
                <div class="brand-title">Grow-Matic Admin Intelligence</div>
                <div class="brand-sub">Ask anything about application health, sessions, GPS, battery, tenants &amp; more</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Session state ──
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "debug_data" not in st.session_state:
        st.session_state.debug_data = []

    # ── Suggested questions (only when chat is empty) ──
    if not st.session_state.messages:
        st.markdown("#### 💡 Try asking…")
        cols = st.columns(4)
        for idx, q in enumerate(SUGGESTED_QUESTIONS):
            with cols[idx % 4]:
                if st.button(q, key=f"sq_{idx}", use_container_width=True):
                    st.session_state["pending_query"] = q
        st.markdown("---")

    # ── Render chat history ──
    if st.session_state.messages:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for i, msg in enumerate(st.session_state.messages):
            render_message(msg["role"], msg["content"], msg.get("ts", ""), msg.get("data_source", ""))
            if debug_mode and msg["role"] == "assistant":
                dbg_idx = i // 2
                if dbg_idx < len(st.session_state.debug_data):
                    with st.expander("🔬 Debug: intent mapping & raw API data", expanded=False):
                        st.json(st.session_state.debug_data[dbg_idx])
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Input area ──
    st.markdown("---")
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Ask a question",
            placeholder="e.g. How many users had GPS issues last week?",
            label_visibility="collapsed",
            key="user_input_field",
            value=st.session_state.pop("pending_query", ""),
        )
    with col_btn:
        send_clicked = st.button("Send ➤", use_container_width=True, key="send_btn")

    # ── Process query ──
    if (send_clicked or user_input) and user_input.strip():
        query = user_input.strip()

        if not api_key:
            st.error("⚠️ Please enter your Gemini API key in the sidebar before sending a message.")
            return

        ts_now = datetime.now().strftime("%H:%M")
        st.session_state.messages.append({"role": "user", "content": query, "ts": ts_now})

        client = make_gemini_client(api_key)

        pipeline_status = st.empty()
        stream_area    = st.empty()   # live streaming output lands here

        def update_status(step: str, msg: str):
            colors = {"step1": "#ffa657", "step2": "#3b82f6", "step3": "#10b981"}
            icons  = {"step1": "🔍",      "step2": "📡",      "step3": "✨"}
            color  = colors.get(step, "#9ca3af")
            icon   = icons.get(step, "⚙️")
            pipeline_status.markdown(
                f"""<div class="pipeline-step">
                        <div class="step-dot" style="background:{color};"></div>
                        <span style="color:{color};font-size:0.82rem;font-weight:500;">{icon} {msg}</span>
                    </div>""",
                unsafe_allow_html=True,
            )

        try:
            answer, debug_info = run_pipeline(
                client=client,
                user_query=query,
                tenant_id=tenant_id,
                date_range_days=date_range_days,
                page_size=page_size,
                status_callback=update_status,
                stream_placeholder=stream_area,
                force_cached=force_cached,
            )
        except Exception as exc:  # noqa: BLE001
            pipeline_status.empty()
            stream_area.empty()
            err = str(exc)
            if "API_KEY" in err.upper() or "api key" in err.lower() or "401" in err:
                st.error("❌ Invalid Gemini API key. Please check your key in the sidebar.")
            elif "quota" in err.lower() or "429" in err:
                st.error("❌ Gemini quota exceeded. Please wait a moment and try again.")
            else:
                st.error(f"❌ An unexpected error occurred: {exc}")
            return

        pipeline_status.empty()
        stream_area.empty()

        # Find overall data source used in execution
        data_source = get_overall_data_source(debug_info.get("api_data", {}))

        st.session_state.messages.append({
            "role": "assistant", 
            "content": answer, 
            "ts": ts_now,
            "data_source": data_source
        })
        st.session_state.debug_data.append(debug_info)
        st.rerun()


if __name__ == "__main__":
    main()
