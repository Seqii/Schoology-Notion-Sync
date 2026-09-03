from __future__ import annotations

import time
from typing import Any

import requests

from config import (
    NOTION_API_BASE,
    NOTION_DATABASE_ID,
    NOTION_DATA_SOURCE_ID,
    NOTION_TOKEN,
    NOTION_VERSION,
)


class NotionClient:
    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": (
                    f"Bearer {NOTION_TOKEN}"
                ),
                "Notion-Version": (
                    NOTION_VERSION
                ),
                "Content-Type": (
                    "application/json"
                ),
            }
        )

        self._data_source_id: (
            str | None
        ) = None

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = (
            f"{NOTION_API_BASE}/"
            f"{path.lstrip('/')}"
        )

        for _ in range(4):

            response = self.session.request(
                method,
                url,
                json=payload,
                timeout=30,
            )

            # Notion may rate-limit us.
            if response.status_code == 429:

                try:
                    delay = float(
                        response.headers.get(
                            "Retry-After",
                            "1",
                        )
                    )
                except ValueError:
                    delay = 1

                time.sleep(delay)
                continue

            if not response.ok:
                raise RuntimeError(
                    f"Notion API error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

            if not response.content:
                return {}

            return response.json()

        raise RuntimeError(
            "Notion kept rate limiting "
            "the request"
        )

    # --------------------------------------------------------
    # Data source
    # --------------------------------------------------------

    def get_data_source_id(
        self,
    ) -> str | None:

        if self._data_source_id:
            return self._data_source_id

        # If manually specified, use it.
        if NOTION_DATA_SOURCE_ID:
            self._data_source_id = (
                NOTION_DATA_SOURCE_ID
            )

            return self._data_source_id

        # Otherwise discover it from the normal database ID.
        database = self._request(
            "GET",
            (
                f"/databases/"
                f"{NOTION_DATABASE_ID}"
            ),
        )

        data_sources = database.get(
            "data_sources",
            [],
        )

        if not data_sources:
            raise RuntimeError(
                "No accessible data sources "
                "found in the Notion database"
            )

        # Most databases will only have one.
        if len(data_sources) > 1:

            options = ", ".join(
                (
                    f"{item.get('name', 'Unnamed')}"
                    f"={item.get('id')}"
                )
                for item in data_sources
            )

            raise RuntimeError(
                "This database has multiple data sources. "
                "Set NOTION_DATA_SOURCE_ID in .env. "
                f"Options: {options}"
            )

        self._data_source_id = (
            data_sources[0]["id"]
        )

        return self._data_source_id

    # --------------------------------------------------------
    # Pages
    # --------------------------------------------------------

    def get_all_pages(
        self,
    ) -> list[dict[str, Any]]:

        data_source_id = (
            self.get_data_source_id()
        )

        pages: list[
            dict[str, Any]
        ] = []

        cursor: str | None = None

        while True:

            payload: dict[str, Any] = {
                "page_size": 100,
            }

            if cursor:
                payload[
                    "start_cursor"
                ] = cursor

            response = self._request(
                "POST",
                (
                    f"/data_sources/"
                    f"{data_source_id}/query"
                ),
                payload,
            )

            pages.extend(
                response.get(
                    "results",
                    [],
                )
            )

            if not response.get(
                "has_more"
            ):
                break

            cursor = response.get(
                "next_cursor"
            )

            if not cursor:
                break

        return pages

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    def create_page(
        self,
        properties: dict[str, Any],
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            "/pages",
            {
                "parent": {
                    "type": (
                        "data_source_id"
                    ),
                    "data_source_id": (
                        self.get_data_source_id()
                    ),
                },
                "properties": properties,
            },
        )

    # --------------------------------------------------------
    # Update
    # --------------------------------------------------------

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:

        return self._request(
            "PATCH",
            f"/pages/{page_id}",
            {
                "properties": properties,
            },
        )