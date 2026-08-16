"""Live forecourt WebSocket.

``GET /ws/pumps?token=<jwt>`` — the browser cannot set an Authorization header
on a WebSocket, so the JWT travels as a query parameter; an invalid or missing
token closes the socket with **4401**.

On connect the client gets one ``{"type":"snapshot","pumps":[...]}`` frame built
from the pump manager, then every message published on the Redis pump channel is
forwarded verbatim.  A ``{"type":"ping"}`` frame is emitted while idle so dead
sockets are noticed quickly.

NOTE: this router intentionally has **no** ``/api`` prefix.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.redis_client import PUMP_CHANNEL, get_redis
from app.security import decode_token

log = logging.getLogger("kolonk.ws")

router = APIRouter(tags=["ws"])

WS_UNAUTHORIZED = 4401
IDLE_TIMEOUT_SECONDS = 15.0


def _valid_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = decode_token(token)
        uuid.UUID(str(payload["sub"]))
    except Exception:  # noqa: BLE001 — any decode problem is simply "not allowed"
        return False
    return True


async def _snapshot_frame(websocket: WebSocket) -> dict:
    manager = getattr(websocket.app.state, "pump_manager", None)
    pumps = []
    if manager is not None:
        try:
            pumps = [t.as_dict() for t in manager.snapshot()]
        except Exception:  # noqa: BLE001
            log.warning("Насосны төлөв уншихад алдаа гарлаа", exc_info=True)
    return {"type": "snapshot", "pumps": pumps}


async def _forward(websocket: WebSocket, pubsub) -> None:
    while True:
        message = await pubsub.get_message(
            ignore_subscribe_messages=True, timeout=IDLE_TIMEOUT_SECONDS
        )
        if message is None:
            await websocket.send_json({"type": "ping"})
            continue
        if message.get("type") != "message":
            continue
        data = message.get("data")
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        await websocket.send_text(str(data))


async def _watch_client(websocket: WebSocket) -> None:
    """Consume client frames purely to notice a disconnect."""
    while True:
        event = await websocket.receive()
        if event.get("type") == "websocket.disconnect":
            return


async def _close_pubsub(pubsub) -> None:
    with contextlib.suppress(Exception):
        await pubsub.unsubscribe(PUMP_CHANNEL)
    closer = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
    if closer is not None:
        with contextlib.suppress(Exception):
            await closer()


@router.websocket("/ws/pumps")
async def pumps_socket(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    if not _valid_token(token):
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    await websocket.accept()

    try:
        await websocket.send_json(await _snapshot_frame(websocket))
    except (WebSocketDisconnect, RuntimeError):
        return

    try:
        pubsub = get_redis().pubsub()
        await pubsub.subscribe(PUMP_CHANNEL)
    except Exception:  # noqa: BLE001 — Redis is down; the client keeps the snapshot
        log.warning("Redis сувагт бүртгүүлж чадсангүй", exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "error", "message": "Сервертэй холбогдоход алдаа гарлаа"}
            )
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)
        return

    tasks = [
        asyncio.create_task(_forward(websocket, pubsub), name="ws-pumps-forward"),
        asyncio.create_task(_watch_client(websocket), name="ws-pumps-watch"),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        for task in done:
            with contextlib.suppress(asyncio.CancelledError):
                exc = task.exception()
                if exc is not None and not isinstance(exc, WebSocketDisconnect):
                    log.info("Насосны WS салгагдлаа: %s", exc)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.warning("Насосны WS алдаа", exc_info=True)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await _close_pubsub(pubsub)
        with contextlib.suppress(Exception):
            await websocket.close()
