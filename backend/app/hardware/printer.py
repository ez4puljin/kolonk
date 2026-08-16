"""Receipt printer abstraction.

**v1 prints in the browser.**  The POS renders the receipt as HTML and calls
``window.print()`` against the workstation's 80 mm thermal printer, which keeps
the backend free of vendor SDKs and works over the network without a print
server.  The backend therefore uses :class:`NullPrinter`, which only records
that a receipt was requested.

The abstraction exists so a station with a serial/USB printer wired to the
server can drop in an ESC/POS driver later: implement :class:`PrinterDriver`
and return it from :func:`get_printer` (selected by a setting) — no caller
changes.

``payload`` is the receipt document produced by the sales layer:
``{"sale_no", "datetime", "station", "items": [...], "payments": [...],
"total", "vat", "ebarimt": {...}}`` — all money as strings, never floats.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger("kolonk.printer")


@runtime_checkable
class PrinterDriver(Protocol):
    async def print_receipt(self, payload: dict[str, Any]) -> None:
        """Render and cut one receipt.  Must never raise — a printer fault may
        not roll back a completed sale."""
        ...


class NullPrinter:
    """No-op printer: the browser owns printing in v1."""

    name = "null"

    async def print_receipt(self, payload: dict[str, Any]) -> None:
        log.info(
            "Баримт хэвлэх хүсэлт (хөтчөөр хэвлэнэ): sale_no=%s total=%s",
            payload.get("sale_no"),
            payload.get("total"),
        )


_printer: PrinterDriver | None = None


def get_printer() -> PrinterDriver:
    """Process-wide printer instance."""
    global _printer
    if _printer is None:
        _printer = NullPrinter()
    return _printer


def set_printer(printer: PrinterDriver | None) -> None:
    """Override the printer (tests, or a station with a server-side device)."""
    global _printer
    _printer = printer
