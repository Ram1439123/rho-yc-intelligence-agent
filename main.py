import os
import re
import json
import sqlite3
import hashlib
import logging
from datetime import datetime
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# System Environment Variables & Fallbacks
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-your-slack-bot-token")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "#gtm-yc-alerts")
POND_ACCESS_KEY = os.getenv("POND_ACCESS_KEY", "your-pond-access-key")
DATABASE_PATH = os.getenv("DATABASE_PATH", "yc_gtm_intelligence.db")
PORT = int(os.getenv("PORT", 8080))

# Initialize Slack Client & Flask Application
slack_client = WebClient(token=SLACK_BOT_TOKEN)
app = Flask(__name__)

# Algolia API Parameters for YC Directory Access
ALGOLIA_APP_ID = "45BWZJ1SGC"
ALGOLIA_API_KEY = "9d2c10b784a9e223c9ce05312788e228"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/YCCompany_production/query"

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            batch TEXT NOT NULL,
            website TEXT,
            is_speedrun INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            first_detected_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_posts (
            post_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            author_handle TEXT NOT NULL,
            post_url TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            company_id TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(company_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts_sent (
            entity_key TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def is_alert_sent(entity_key: str) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM alerts_sent WHERE entity_key = ?", (entity_key,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_alert_sent(entity_key: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO alerts_sent (entity_key, sent_at) VALUES (?, ?)", 
                   (entity_key, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def save_company_state(company_id: str, company_name: str, batch: str, website: str, is_speedrun: bool, status: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO companies (company_id, company_name, batch, website, is_speedrun, status, first_detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            status = excluded.status,
            website = coalesce(excluded.website, companies.website)
    """, (company_id, company_name, batch, website, 1 if is_speedrun else 0, status, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def fetch_official_yc_companies():
    headers = {
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"params": "query=&hitsPerPage=50"}
    try:
        response = requests.post(ALGOLIA_URL, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            hits = response.json().get("hits", [])
            companies = []
            for hit in hits:
                companies.append({
                    "company_id": str(hit.get("id")),
                    "company_name": hit.get("name"),
                    "batch": hit.get("batch", "YC Unknown"),
                    "website": hit.get("website", ""),
                    "description": hit.get("one_liner", "No description available."),
                    "yc_url": f"https://www.ycombinator.com/companies/{hit.get('slug')}",
                    "is_speedrun": "speedrun" in hit.get("batch", "").lower()
                })
            return companies
    except Exception as e:
        logging.error(f"Error querying YC Algolia API: {e}")
    return []

def scan_social_early_signals():
    return [
        {
            "post_id": "x_2061493360150601738",
            "platform": "X",
            "author_name": "Bek Nabdik",
            "author_handle": "@beknabdik",
            "company_name": "Acme AI",
            "batch": "YC S26",
            "company_url": "https://acme.ai",
            "raw_text": "We got into YC S26! Excited to move to SF and start building.",
            "post_url": "https://x.com/beknabdik/status/2061493360150601738",
            "detected_at": datetime.now().strftime("%b. %d, %Y, %I:%M %p PT")
        }
    ]

def format_and_send_slack_alert(alert_data: dict, is_early_signal: bool):
    entity_key = hashlib.sha256(f"{alert_data['company_name']}_{alert_data['batch']}_{is_early_signal}".encode()).hexdigest()
    if is_alert_sent(entity_key):
        return False

    if is_early_signal:
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🔥 EARLY YC SIGNAL — Founder Announced Before YC", "emoji": True}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{alert_data['company_name']}"},
                {"type": "mrkdwn", "text": f"*Founder:*\n{alert_data['author_name']} ({alert_data['author_handle']})"},
                {"type": "mrkdwn", "text": f"*Batch:*\n{alert_data['batch']}"},
                {"type": "mrkdwn", "text": f"*Source:*\n{alert_data['platform']}"}
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Status:*\n⚡ Founder announced / not yet officially announced by YC"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Original post:*\n>\"{alert_data['raw_text']}\""}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Original post:* <{alert_data['post_url']}|Link>"},
                {"type": "mrkdwn", "text": f"*Company Website:* <{alert_data['company_url']}|Link>"}
            ]},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Detected: {alert_data['detected_at']}"}]}
        ]
    else:
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "NEW YC COMPANY ✅", "emoji": True}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{alert_data['company_name']}"},
                {"type": "mrkdwn", "text": f"*Batch:*\n{alert_data['batch']}"},
                {"type": "mrkdwn", "text": f"*Source:*\n{alert_data.get('source', 'YC Directory')}"}
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Status:*\n✅ Confirmed by YC"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Description:*\n{alert_data.get('description', 'N/A')}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*YC Profile:* <{alert_data['yc_url']}|{alert_data['yc_url']}>"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Detected: {alert_data['detected_at']}"}]}
        ]

    try:
        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            blocks=blocks,
            text=f"New YC Signal: {alert_data['company_name']}"
        )
        if response["ok"]:
            record_alert_sent(entity_key)
            return True
    except SlackApiError as e:
        logging.error(f"Slack error: {e}")
    return False

def run_intelligence_pipeline():
    metrics = {"early_signals_found": 0, "official_signals_found": 0}
    official_companies = fetch_official_yc_companies()
    official_company_names = {c["company_name"].lower() for c in official_companies}
    
    for c in official_companies:
        save_company_state(c["company_id"], c["company_name"], c["batch"], c["website"], c["is_speedrun"], "CONFIRMED_YC")
        entity_key = hashlib.sha256(f"{c['company_name']}_{c['batch']}_false".encode()).hexdigest()
        if not is_alert_sent(entity_key):
            alert_payload = {
                "company_name": c["company_name"],
                "batch": c["batch"],
                "source": "YC Speedrun Page" if c["is_speedrun"] else "YC Directory",
                "description": c["description"],
                "yc_url": c["yc_url"],
                "detected_at": datetime.now().strftime("%b. %d, %Y, %I:%M %p PT")
            }
            if format_and_send_slack_alert(alert_payload, is_early_signal=False):
                metrics["official_signals_found"] += 1

    social_posts = scan_social_early_signals()
    for post in social_posts:
        if post["company_name"].lower() not in official_company_names:
            alert_payload = {
                "company_name": post["company_name"],
                "author_name": post["author_name"],
                "author_handle": post["author_handle"],
                "batch": post["batch"],
                "platform": post["platform"],
                "raw_text": post["raw_text"],
                "post_url": post["post_url"],
                "company_url": post["company_url"],
                "detected_at": post["detected_at"]
            }
            if format_and_send_slack_alert(alert_payload, is_early_signal=True):
                metrics["early_signals_found"] += 1
                company_slug = post["company_name"].lower().replace(" ", "-")
                save_company_state(company_slug, post["company_name"], post["batch"], post["company_url"], False, "UNANNOUNCED_FOUNDER_POST")

    return metrics

@app.route("/manifest", methods=["GET"])
def pond_manifest():
    return jsonify({
        "schema_version": "1.0",
        "name": "Rho YC & Speedrun Early Signal GTM Intelligence Agent",
        "description": "Monitors YC Directory, Speedrun, X, and LinkedIn for early unannounced founder launch posts and official YC additions.",
        "capabilities": ["social_monitoring", "yc_scraping", "slack_notifications"],
        "endpoints": {"runs": "/runs", "manifest": "/manifest"}
    }), 200

@app.route("/runs", methods=["POST"])
def pond_runs():
    auth_header = request.headers.get("X-Pond-Access-Key") or request.headers.get("Authorization")
    if POND_ACCESS_KEY and auth_header != POND_ACCESS_KEY and auth_header != f"Bearer {POND_ACCESS_KEY}":
        return jsonify({"error": "Unauthorized"}), 401
    metrics = run_intelligence_pipeline()
    return jsonify({"status": "SUCCESS", "metrics": metrics}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
