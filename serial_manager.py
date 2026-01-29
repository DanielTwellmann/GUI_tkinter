# serial_manager.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import threading

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
    HAS_SERIAL = True
except Exception:
    serial = None
    list_ports = None
    HAS_SERIAL = False


@dataclass
class SerialConfig:
    baudrate: int = 115200
    timeout_s: float = 0.1


class SerialManager:
    def __init__(self, cfg: SerialConfig | None = None):
        self.cfg = cfg or SerialConfig()
        self._ser = None
        self._lock = threading.Lock()

    @property
    def has_serial(self) -> bool:
        return HAS_SERIAL

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._ser is not None and getattr(self._ser, "is_open", False)

    def connect(self, port: str) -> None:
        if not HAS_SERIAL:
            raise RuntimeError("pyserial is not installed.")
        if not port:
            raise ValueError("Port is empty.")

        with self._lock:
            if self._ser is not None and getattr(self._ser, "is_open", False):
                return  # already connected

            self._ser = serial.Serial(
                port=port,
                baudrate=self.cfg.baudrate,
                timeout=self.cfg.timeout_s,
            )

    def disconnect(self) -> None:
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self._ser = None

    def list_ports_blocking(self) -> List[str]:
        """Blocking call. Use in a thread if you care about GUI responsiveness."""
        if not HAS_SERIAL:
            return []
        try:
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    def write(self, data: bytes) -> None:
        with self._lock:
            if not self.is_connected:
                raise RuntimeError("Not connected.")
            self._ser.write(data)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            if not self.is_connected:
                raise RuntimeError("Not connected.")
            return self._ser.read(n)
