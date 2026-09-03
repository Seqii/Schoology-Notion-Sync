from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any

from config import (
    SCHOOLOGY_TIMEZONE,
    SCHOOLOGY_WEB_BASE,
)
from notion import NotionClient
from schoology import SchoologyClient


# ============================================================
# Normalized assignment
# ============================================================

@dataclass(frozen=True)
class Assignment:
    name: str
    class_name: str
    due: str | None
    url: str
    description: str


# ============================================================
# Schoology description HTML -> plain text
# ============================================================

class _HTMLToText(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def __init__(self):
        super().__init__()

        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(
        self,
        tag: str,
    ):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(
        self,
        data: str,
    ):
        self.parts.append(data)


def _html_to_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    parser = _HTMLToText()
    parser.feed(value)

    text = unescape(
        "".join(
            parser.parts
        )
    )

    # Collapse unnecessary spaces.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Collapse excessive blank lines.
    text = re.sub(
        r"\n\s*\n+",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# Dates
# ============================================================

def _schoology_due_to_iso(
    value: str | None,
) -> str | None:

    if not value:
        return None

    parsed = datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S",
    )

    parsed = parsed.replace(
        tzinfo=SCHOOLOGY_TIMEZONE
    )

    return parsed.isoformat()


def _normalize_iso(
    value: str | None,
) -> str | None:

    if not value:
        return None

    try:
        return (
            datetime.fromisoformat(value)
            .replace(microsecond=0)
            .isoformat()
        )

    except ValueError:
        return value


# ============================================================
# Schoology -> normalized assignment
# ============================================================

def _class_name(
    section: dict[str, Any],
) -> str:

    return (
        section.get("course_title")
        or section.get("section_title")
        or section.get("title")
        or (
            f"Section "
            f"{section.get('id', 'Unknown')}"
        )
    )


def _normalize_assignment(
    section: dict[str, Any],
    raw: dict[str, Any],
) -> Assignment:

    assignment_id = str(
        raw["id"]
    )

    return Assignment(
        name=(
            raw.get("title")
            or "Untitled Assignment"
        ),

        class_name=_class_name(
            section
        ),

        due=_schoology_due_to_iso(
            raw.get("due")
        ),

        url=(
            f"{SCHOOLOGY_WEB_BASE}"
            f"/assignment/"
            f"{assignment_id}"
            f"/info"
        ),

        description=_html_to_text(
            raw.get("description")
        ),
    )


# ============================================================
# Normalized assignment -> Notion properties
# ============================================================

def _rich_text(
    value: str,
) -> list[dict[str, Any]]:

    if not value:
        return []

    # Split long descriptions into multiple Notion text objects.
    chunks = [
        value[i : i + 1900]
        for i in range(
            0,
            len(value),
            1900,
        )
    ]

    return [
        {
            "type": "text",
            "text": {
                "content": chunk,
            },
        }
        for chunk in chunks[:100]
    ]


def _notion_properties(
    assignment: Assignment,
) -> dict[str, Any]:

    return {
        # ----------------------------------------------------
        # Assignment
        # Notion type: Title
        # ----------------------------------------------------

        "Assignment": {
            "title": _rich_text(
                assignment.name
            ),
        },

        # ----------------------------------------------------
        # Class
        # Notion type: Multi-Select
        # ----------------------------------------------------

        "Class": {
            "select": {
                "name": assignment.class_name
            }
        },

        # ----------------------------------------------------
        # Due
        # Notion type: Date
        # ----------------------------------------------------

        "Due": {
            "date": (
                {
                    "start": (
                        assignment.due
                    )
                }
                if assignment.due
                else None
            ),
        },

        # ----------------------------------------------------
        # URL
        # Notion type: URL
        # ----------------------------------------------------

        "URL": {
            "url": assignment.url,
        },

        # ----------------------------------------------------
        # Description
        # Notion type: Text
        # ----------------------------------------------------

        "Description": {
            "rich_text": _rich_text(
                assignment.description
            ),
        },
    }


# ============================================================
# Read existing Notion pages
# ============================================================

def _plain_text(
    items: list[dict[str, Any]],
) -> str:

    return "".join(
        item.get(
            "plain_text",
            "",
        )
        for item in items
    )


def _page_values(
    page: dict[str, Any],
) -> Assignment | None:

    props = page.get(
        "properties",
        {},
    )

    url = (
        props.get(
            "URL",
            {},
        )
        .get(
            "url"
        )
    )

    # Not a Schoology-imported row if it has no URL.
    if not url:
        return None

    due_object = (
        props.get(
            "Due",
            {},
        )
        .get(
            "date"
        )
    )

    due = (
        due_object.get("start")
        if due_object
        else None
    )

    class_option = (
        props.get(
            "Class",
            {},
        ).get(
            "select"
        )
    )

    class_name = (
        class_option.get("name", "")
        if class_option
        else ""
    )

    return Assignment(
        name=_plain_text(
            props.get(
                "Assignment",
                {},
            ).get(
                "title",
                [],
            )
        ),


        class_name = class_name,

        due=due,

        url=url,

        description=_plain_text(
            props.get(
                "Description",
                {},
            ).get(
                "rich_text",
                [],
            )
        ),
    )


# ============================================================
# Compare assignments
# ============================================================

def _same_assignment(
    new: Assignment,
    old: Assignment,
) -> bool:

    return (
        new.name
        == old.name

        and new.class_name
        == old.class_name

        and _normalize_iso(
            new.due
        )
        == _normalize_iso(
            old.due
        )

        and new.url
        == old.url

        and new.description
        == old.description
    )


# ============================================================
# Schoology user
# ============================================================

def _schoology_user_id(
    user: dict[str, Any],
) -> str:

    user_id = (
        user.get("uid")
        or user.get("id")
    )

    if not user_id:
        raise RuntimeError(
            "Could not determine "
            "the Schoology user ID"
        )

    return str(user_id)


# ============================================================
# Sync
# ============================================================

def sync_assignments(
    schoology: SchoologyClient,
    notion: NotionClient,
) -> None:

    # --------------------------------------------------------
    # Get Schoology user/classes
    # --------------------------------------------------------

    user = schoology.get_me()

    user_id = _schoology_user_id(
        user
    )

    sections = schoology.get_sections(
        user_id
    )

    # --------------------------------------------------------
    # Index existing Notion rows by URL
    # --------------------------------------------------------

    existing_by_url: dict[
        str,
        tuple[str, Assignment],
    ] = {}

    for page in notion.get_all_pages():

        existing = _page_values(
            page
        )

        if existing:
            existing_by_url[
                existing.url
            ] = (
                page["id"],
                existing,
            )

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    created = 0
    updated = 0
    unchanged = 0

    print(
        f"Found {len(sections)} "
        f"Schoology classes"
    )

    # --------------------------------------------------------
    # Each Schoology class
    # --------------------------------------------------------

    for section in sections:

        section_id = str(
            section["id"]
        )

        class_name = _class_name(
            section
        )

        raw_assignments = (
            schoology.get_assignments(
                section_id
            )
        )

        print(
            f"  {class_name}: "
            f"{len(raw_assignments)} "
            f"assignments"
        )

        # ----------------------------------------------------
        # Each assignment
        # ----------------------------------------------------

        for raw in raw_assignments:

            assignment = (
                _normalize_assignment(
                    section,
                    raw,
                )
            )

            existing = (
                existing_by_url.get(
                    assignment.url
                )
            )

            # ------------------------------------------------
            # New assignment
            # ------------------------------------------------

            if existing is None:

                properties = _notion_properties(
                    assignment
                )

                properties["Status"] = {
                    "status": {
                        "name": "Not Started"
                    }
                }

                notion.create_page(
                    properties
                )

                created += 1

                print(
                    f"    + "
                    f"{assignment.name}"
                )

                continue

            # ------------------------------------------------
            # Existing assignment
            # ------------------------------------------------

            page_id, old_assignment = (
                existing
            )

            # Nothing changed.
            if _same_assignment(
                assignment,
                old_assignment,
            ):
                unchanged += 1
                continue

            # Something changed in Schoology.
            notion.update_page(
                page_id,
                _notion_properties(
                    assignment
                ),
            )

            updated += 1

            print(
                f"    ~ "
                f"{assignment.name}"
            )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print()

    print(
        f"Created:   {created}"
    )

    print(
        f"Updated:   {updated}"
    )

    print(
        f"Unchanged: {unchanged}"
    )