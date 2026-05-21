from __future__ import annotations

__all__ = ["TransferService", "transfer_service"]


def __getattr__(name: str):
    if name in __all__:
        from .service import TransferService, transfer_service

        values = {
            "TransferService": TransferService,
            "transfer_service": transfer_service,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
