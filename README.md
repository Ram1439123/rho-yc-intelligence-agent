```markdown
# Rho YC & Speedrun Early-Signal GTM Intelligence Agent

## Overview

This is a personal Slack bot designed for Senior GTM professionals at Rho. Its goal is to provide a competitive advantage by identifying and alerting on new Y Combinator (YC) and YC Speedrun company launches in real-time.

Crucially, this agent includes "early-detection logic" [cite: 1]. It monitors founder activity on social media (currently X/Twitter) to detect acceptance announcements made by founders *before* YC officially lists them in their public directory. This allows for immediate outreach, beating the general market to high-priority prospects.

This single-workspace application maintains persistent state to ensure only incremental updates are pushed every 8 hours, avoiding duplicate alerts [cite: 1]. It includes specific tagging for YC Speedrun companies to distinguish them from the main batch [cite: 1].

The current implementation supports monitoring X (Twitter) and the YC Directory via direct API access [cite: 1, 2]. The codebase is structured for future expandability to other platforms like LinkedIn [cite: 2].

## Key Features

*   **Early Detection:** Identifies YC/Speedrun founders announcing on social media before the official YC directory update [cite: 1].
*   **Stateful Monitoring:** Uses a local SQLite database to track already-alerted companies, ensuring alerts are unique and incremental [cite: 1].
*   **Speedrun Awareness:** Specifically identifies and tags companies from the YC Speedrun sub-program [cite: 1].
*   **Slack Integration:** Delivers rich, structured alerts (Block Kit format) directly to a specified Slack channel or DM, including company, founder, and source details [cite: 1].
*   **Automated Updates:** Designed to run continuously, checking sources on a recurring schedule (default 8 hours) [cite: 1].

## Prerequisites

To run this agent, you will need:

1.  **Python 3.9+**
2.  **A Slack App:** With a Bot User OAuth Token (`xoxb-`) and the `chat:write` scope installed in your workspace.
3.  **Slack Channel:** A channel (e.g., `#yc-alerts`) where the bot is invited.

## Local Installation

1.  Clone the repository:
    ```bash
    git clone [https://github.com/your-username/rho-yc-intelligence-agent.git](https://github.com/your-username/rho-yc-intelligence-agent.git)
    cd rho-yc-intelligence-agent
    ```

2.  Create a virtual environment and activate it:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # On Windows: venv\Scripts\activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure environment variables:
    *   Copy the example file: `cp .env.example .env`
    *   Open `.env` and fill in your actual values:
        ```env
        SLACK_BOT_TOKEN=xoxb-your-actual-token
        SLACK_CHANNEL_ID=C01ABC23DE (Your Channel ID, not the name)
        # Optional: Database path, Port
        ```

5.  Run the application:
    ```bash
    python main.py
    ```

The application will initialize the SQLite database on the first run and immediately check for new companies.

## Deployment & Production

To run the agent persistently (continuously) as requested [cite: 1], you should deploy it to a server or cloud function platform (like Render, Railway, AWS EC2/Lambda).

Ensure you configure the environment variables on the deployment platform to match your `.env` settings. The agent automatically exposes a port (`8080` default) to keep the process alive [cite: 2].

### Pond Agent Infrastructure Integration

If running this as an AI agent via Pond [cite: 2]:

*   **Manifest:** The manifest is available via `GET /manifest`.
*   **Execution:** The continuous monitoring loop is triggered via `POST /runs`. Secure this endpoint using the `POND_ACCESS_KEY` environment variable [cite: 2].

## Example Alerts

The bot delivers structured alerts in Slack.

### 🔥 Early Detection Alert
Generated when a founder announces on social media before the official YC listing:

```text
🔥 EARLY YC SIGNAL — Founder Announced Before YC

Company: Acme AI
Founder: Jane Doe (@janedoe)
Batch: YC S26
Source: X
Status: ⚡ Founder announced / not yet officially announced by YC

Original post:
"We got into YC S26! Excited to move to SF and start building."

Original post: [https://x.com/janedoe/status/123456789](https://x.com/janedoe/status/123456789)
Company: [https://acme.ai](https://acme.ai)
Detected: Aug. 28, 2026, 9:14 AM PT

```

### ✅ Official YC Listing Alert

Generated when a company is added to the YC Directory [cite: 1]:

```text
NEW YC COMPANY

Company: Logistics AI
Batch: YC S26
Source: YC Directory
Status: ✅ Confirmed by YC

Description: AI agents for optimized route planning.
YC Profile: [https://www.ycombinator.com/companies/logistics-ai](https://www.ycombinator.com/companies/logistics-ai)
Detected: Aug. 28, 2026, 2:03 PM PT

```

## Future Upgradability

The structure of the monitoring functions in `main.py` is modular, allowing easy integration of additional social media sources (e.g., LinkedIn) as requested for future iterations [cite: 1, 2].

```

```

"Note: For security best practices, API keys have been replaced with placeholders. To run the Algolia search feature locally, insert an Algolia API key in the placeholder location."
