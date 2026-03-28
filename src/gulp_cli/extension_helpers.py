from __future__ import annotations

from typing import Any, Callable

from gulp_sdk.api.request_utils import wait_for_request_stats
from gulp_sdk.websocket import WSMessage


async def call_custom_endpoint(
    client: Any,
    *,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    ensure_websocket: bool = False,
    wait: bool = False,
    timeout: int = 120,
    ws_callback: Callable[[WSMessage], None] | None = None,
) -> dict[str, Any]:
    """
    Execute a direct API call for extension endpoints.

    Optionally ensures websocket connection and waits for terminal request stats
    when server responds with JSend pending status.
    """
    if ensure_websocket or wait:
        await client.ensure_websocket()

    response: dict[str, Any] = await client._request(
        method,
        path,
        params=params,
        json=json_body,
    )

    if (
        wait
        and isinstance(response, dict)
        and response.get("status") == "pending"
        and response.get("req_id")
    ):
        return await wait_for_request_stats(
            client,
            str(response.get("req_id")),
            timeout,
            ws_callback=ws_callback,
        )

    return response
