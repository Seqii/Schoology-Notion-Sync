from __future__ import annotations

import time
import uuid
from typing import Any
from urllib.parse import quote, urljoin

import requests
from requests.auth import AuthBase

from config import (
    SCHOOLOGY_API_BASE,
    SCHOOLOGY_KEY,
    SCHOOLOGY_SECRET,
)


# ============================================================
# OAuth
# ============================================================

def _oauth_encode(value: Any) -> str:
    return quote(
        str(value),
        safe="~-._",
    )


class SchoologyTwoLeggedAuth(AuthBase):
    """
    Implements Schoology's two-legged OAuth 1.0 authentication.

    This is appropriate for a personal script where the API consumer
    and the Schoology user are the same person.
    """

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def __call__(self, request):
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time()))

        # For Schoology's two-legged PLAINTEXT OAuth:
        #
        # signature = consumer_secret + "&"
        signature = self.consumer_secret + "&"

        parts = [
            'realm="Schoology API"',
            (
                f'oauth_consumer_key="'
                f'{_oauth_encode(self.consumer_key)}"'
            ),
            'oauth_token=""',
            f'oauth_nonce="{_oauth_encode(nonce)}"',
            f'oauth_timestamp="{timestamp}"',
            'oauth_signature_method="PLAINTEXT"',
            'oauth_version="1.0"',
            (
                f'oauth_signature="'
                f'{_oauth_encode(signature)}"'
            ),
        ]

        request.headers["Authorization"] = (
            "OAuth " + ", ".join(parts)
        )

        return request


# ============================================================
# Schoology client
# ============================================================

class SchoologyClient:
    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
            }
        )

        self.auth = SchoologyTwoLeggedAuth(
            SCHOOLOGY_KEY,
            SCHOOLOGY_SECRET,
        )

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = (
                f"{SCHOOLOGY_API_BASE}/"
                f"{path.lstrip('/')}"
            )

        current_params = params

        # Schoology's /users/me endpoint may redirect.
        #
        # We follow redirects manually because Schoology requires
        # a new OAuth nonce/timestamp after a redirect.
        for _ in range(5):

            response = self.session.get(
                url,
                params=current_params,
                auth=self.auth,
                allow_redirects=False,
                timeout=30,
            )

            if response.status_code in {
                301,
                302,
                303,
                307,
                308,
            }:
                location = response.headers.get(
                    "Location"
                )

                if not location:
                    raise RuntimeError(
                        "Schoology redirected without "
                        "a Location header"
                    )

                url = urljoin(
                    url,
                    location,
                )

                # The redirect URL already contains what it needs.
                current_params = None

                continue

            if not response.ok:
                raise RuntimeError(
                    f"Schoology API error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

            return response.json()

        raise RuntimeError(
            "Too many Schoology redirects"
        )

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    def _collection(
        self,
        path: str,
        key: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        start = 0

        while True:

            data = self._get(
                path,
                params={
                    "start": start,
                    "limit": limit,
                },
            )

            batch = data.get(
                key,
                [],
            )

            # Occasionally APIs return a single object instead of
            # a one-element list.
            if isinstance(batch, dict):
                batch = [batch]

            if not batch:
                break

            new_count = 0

            for item in batch:
                item_id = str(
                    item.get(
                        "id",
                        "",
                    )
                )

                if (
                    item_id
                    and item_id in seen_ids
                ):
                    continue

                if item_id:
                    seen_ids.add(
                        item_id
                    )

                items.append(
                    item
                )

                new_count += 1

            # Some Schoology collections provide "total".
            total = data.get("total")

            if total is not None:
                try:
                    if len(items) >= int(total):
                        break
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            # If Schoology returned fewer than requested,
            # we've reached the final page.
            if len(batch) < limit:
                break

            # Prevent an infinite loop if Schoology returns
            # duplicate results.
            if new_count == 0:
                break

            start += limit

        return items

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def get_me(
        self,
    ) -> dict[str, Any]:

        return self._get(
            "/users/me"
        )

    def get_sections(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:

        return self._collection(
            f"/users/{user_id}/sections",
            "section",
        )

    def get_assignments(
        self,
        section_id: str,
    ) -> list[dict[str, Any]]:

        return self._collection(
            f"/sections/{section_id}/assignments",
            "assignment",
        )