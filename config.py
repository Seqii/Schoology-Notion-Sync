import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


# ============================================================
# Schoology
# ============================================================

SCHOOLOGY_KEY = _required("SCHOOLOGY_KEY")
SCHOOLOGY_SECRET = _required("SCHOOLOGY_SECRET")

SCHOOLOGY_API_BASE = "https://api.schoology.com/v1"

SCHOOLOGY_WEB_BASE = os.getenv(
    "SCHOOLOGY_WEB_BASE",
    "https://app.schoology.com",
).rstrip("/")

SCHOOLOGY_TIMEZONE = ZoneInfo(
    os.getenv(
        "SCHOOLOGY_TIMEZONE",
        "America/Chicago",
    )
)


# ============================================================
# Notion
# ============================================================

NOTION_TOKEN = _required("NOTION_TOKEN")
NOTION_DATABASE_ID = _required("NOTION_DATABASE_ID")

# Optional.
# Only really necessary if the Notion database has multiple data sources.
NOTION_DATA_SOURCE_ID = os.getenv(
    "NOTION_DATA_SOURCE_ID",
    "",
).strip()

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"