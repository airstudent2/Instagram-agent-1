import os
import json
import re
import requests

# Meta Graph API Configuration
GRAPH_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Load environment variables
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")

# Optional Rule Inputs from GitHub Actions
INPUT_POST_URL = os.getenv("INPUT_POST_URL", "").strip()
INPUT_KEYWORD = os.getenv("INPUT_KEYWORD", "").strip()
INPUT_REPLY = os.getenv("INPUT_REPLY", "").strip()

RULES_FILE = "rules.json"
PROCESSED_FILE = "processed_comments.json"

def load_json(filepath, default):
    """Loads a JSON file or returns a default structure if it doesn't exist."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def save_json(filepath, data):
    """Saves data to a JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def extract_shortcode(url):
    """Extracts Instagram shortcode from /p/ or /reel/ URLs."""
    match = re.search(r"instagram\.com/(?:p|reel)/([^/?#&]+)", url)
    if match:
        return match.group(1)
    return None

def main():
    print("🤖 Starting Instagram Auto-Reply Bot...")

    if not ACCESS_TOKEN or not IG_USER_ID:
        print("❌ Error: Missing ACCESS_TOKEN or IG_USER_ID environment variables.")
        exit(1)

    # Load databases
    rules = load_json(RULES_FILE, {})
    processed = load_json(PROCESSED_FILE,[])

    # Ensure files exist for git to track
    save_json(RULES_FILE, rules)
    save_json(PROCESSED_FILE, processed)

    # 1. Check if we need to add a new rule
    if INPUT_POST_URL and INPUT_KEYWORD and INPUT_REPLY:
        print("📥 Processing new rule input...")
        shortcode = extract_shortcode(INPUT_POST_URL)
        if shortcode:
            rules[shortcode] = {
                "keyword": INPUT_KEYWORD,
                "reply": INPUT_REPLY
            }
            save_json(RULES_FILE, rules)
            print(f"✅ Added rule -> Shortcode: {shortcode} | Keyword: '{INPUT_KEYWORD}' | Reply: '{INPUT_REPLY}'")
        else:
            print("❌ Could not extract shortcode from provided URL.")

    if not rules:
        print("🤷 No rules configured. Exiting gracefully.")
        exit(0)

    # 2. Fetch recent 50 media items
    print("🔍 Fetching recent media items...")
    media_res = requests.get(
        f"{BASE_URL}/{IG_USER_ID}/media",
        params={"fields": "id,shortcode", "limit": 50, "access_token": ACCESS_TOKEN}
    )
    
    if media_res.status_code != 200:
        print(f"❌ Failed to fetch media: {media_res.text}")
        exit(1)
        
    media_data = media_res.json().get("data",[])

    # 3. Process each post that has a matching rule
    for item in media_data:
        shortcode = item.get("shortcode")
        media_id = item.get("id")

        if shortcode in rules:
            rule = rules[shortcode]
            keyword = rule["keyword"].lower()
            reply_text = rule["reply"]

            print(f"💬 Checking comments for shortcode: {shortcode} (Trigger: '{keyword}')")
            comments_res = requests.get(
                f"{BASE_URL}/{media_id}/comments",
                params={"fields": "id,text", "access_token": ACCESS_TOKEN}
            )

            if comments_res.status_code != 200:
                print(f"❌ Failed to fetch comments for {shortcode}: {comments_res.text}")
                continue

            comments = comments_res.json().get("data",[])
            for comment in comments:
                c_id = comment.get("id")
                c_text = comment.get("text", "")

                # Skip if already processed
                if c_id in processed:
                    continue

                # Check if keyword is in the comment (case-insensitive)
                if keyword in c_text.lower():
                    print(f"🚀 Keyword detected! Replying to comment {c_id}: '{c_text}'")
                    reply_res = requests.post(
                        f"{BASE_URL}/{c_id}/replies",
                        data={"message": reply_text, "access_token": ACCESS_TOKEN}
                    )

                    if reply_res.status_code == 200:
                        print(f"✅ Successfully replied to {c_id}")
                        processed.append(c_id)
                        # Save state immediately to avoid duplicate replies if script crashes halfway
                        save_json(PROCESSED_FILE, processed)
                    else:
                        print(f"❌ Failed to reply to {c_id}: {reply_res.text}")

    print("🏁 Finished processing.")

if __name__ == "__main__":
    main()
