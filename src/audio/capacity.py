import asyncio
import shutil
from pathlib import Path

from src.config import settings
from src.utils.telemetry import record_recording_refused, set_recording_capacity


PCM16_STEREO_BYTES_PER_SECOND = 16_000 * 2 * 2


class RecordingCapacityGuard:
    def __init__(
        self,
        recordings_path: str | Path,
        *,
        max_call_seconds: int | None = None,
        min_free_percent: float | None = None,
        resume_free_percent: float | None = None,
        headroom_bytes: int | None = None,
    ):
        self.path = Path(recordings_path)
        self.max_call_seconds = max_call_seconds or settings.RECORDING_MAX_CALL_SECONDS
        self.min_free_percent = settings.RECORDING_MIN_FREE_PERCENT if min_free_percent is None else min_free_percent
        self.resume_free_percent = settings.RECORDING_RESUME_FREE_PERCENT if resume_free_percent is None else resume_free_percent
        self.headroom_bytes = settings.RECORDING_PROCESSING_HEADROOM_BYTES if headroom_bytes is None else headroom_bytes
        self._reservations: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self.degraded = False

    @property
    def bytes_per_call(self) -> int:
        return PCM16_STEREO_BYTES_PER_SECOND * self.max_call_seconds

    @property
    def reserved_bytes(self) -> int:
        return sum(self._reservations.values())

    @property
    def remaining_reserved_bytes(self) -> int:
        remaining = 0
        for call_id, reservation in self._reservations.items():
            materialized = 0
            for call_dir in self.path.glob(f"*/{call_id}"):
                for item in call_dir.iterdir():
                    try:
                        materialized += item.stat().st_size if item.is_file() else 0
                    except FileNotFoundError:
                        continue
            remaining += max(0, reservation - materialized)
        return remaining

    @property
    def pending_processing_bytes(self) -> int:
        pending = 0
        for call_dir in self.path.glob("*/*"):
            if not call_dir.is_dir():
                continue
            for channel in ("tx", "rx"):
                raw = call_dir / f"{channel}.raw"
                wav = call_dir / f"{channel}.wav"
                temporary = call_dir / f"{channel}.tmp.wav"
                if wav.exists() or not raw.exists():
                    continue
                try:
                    raw_size = raw.stat().st_size
                    temporary_size = temporary.stat().st_size if temporary.exists() else 0
                except FileNotFoundError:
                    continue
                pending += max(0, raw_size - temporary_size)
        return pending

    async def reserve(self, call_id: str) -> bool:
        async with self._lock:
            if call_id in self._reservations:
                return True
            usage = shutil.disk_usage(self.path)
            projected = (
                usage.used
                + self.remaining_reserved_bytes
                + self.pending_processing_bytes
                + self.bytes_per_call
                + self.headroom_bytes
            )
            free_percent = max(0.0, 100 * (usage.total - projected) / usage.total)
            threshold = self.resume_free_percent if self.degraded else self.min_free_percent
            if free_percent < threshold:
                self.degraded = True
                record_recording_refused()
                set_recording_capacity(
                    used_bytes=usage.used,
                    reserved_bytes=self.remaining_reserved_bytes,
                    total_bytes=usage.total,
                    degraded=True,
                )
                return False
            self.degraded = False
            self._reservations[call_id] = self.bytes_per_call
            set_recording_capacity(
                used_bytes=usage.used,
                reserved_bytes=self.remaining_reserved_bytes,
                total_bytes=usage.total,
                degraded=False,
            )
            return True

    async def release(self, call_id: str) -> bool:
        async with self._lock:
            return self._reservations.pop(call_id, None) is not None
