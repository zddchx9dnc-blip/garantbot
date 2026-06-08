import os

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
ADMIN_ID: int = int(os.environ.get("ADMIN_ID", "0"))

# Anti-spam settings
SPAM_INTERVAL = 1.5  # seconds between messages
MAX_DEAL_PER_USER = 10  # max active deals per user
