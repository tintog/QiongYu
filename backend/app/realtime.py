"""实时数据服务：起报状态、增量扫描与自动刷新。

设计要点
--------
演示系统需要表现「实时」：
1. 后台线程按固定间隔（默认 60s）扫描数据目录，发现新的起报时次或
   某个起报时次的时效数量增加时，记录一条「数据更新事件」；
2. 前端通过 `/api/realtime/status` 拉取状态，携带 `revision` 版本号；
3. 前端发现 `revision` 变化即触发全量刷新，实现无需重启的自动切换；
4. 同时对外暴露「距上次更新 / 距下次扫描」等时间信息，供大屏实时心跳展示。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app import qiongyu_data as qd

UTC8 = timezone(timedelta(hours=8))

SCAN_INTERVAL_SECONDS = 60.0


class RealtimeMonitor:
    """后台数据目录监控与状态发布。"""

    def __init__(self, root=None, interval: float = SCAN_INTERVAL_SECONDS):
        self.root = root or qd.DATA_ROOT
        self.interval = interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self.revision = 0
        self.started_at = datetime.now(UTC8)
        self.last_scan_at: datetime | None = None
        self.next_scan_at: datetime | None = None
        self.snapshot: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.scan_count = 0
        self.error: str | None = None

    # -- 生命周期 ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="qiongyu-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan(force=True)
            except Exception as exc:  # 监控线程不允许因异常退出
                with self._lock:
                    self.error = f"{type(exc).__name__}: {exc}"
            self._stop.wait(self.interval)

    # -- 扫描 -------------------------------------------------------------
    def scan(self, force: bool = False) -> dict[str, Any]:
        """扫描数据目录，检测新起报时次与时效增量。"""
        now = datetime.now(UTC8)
        det, ens = qd.resolve_latest(self.root)

        current: dict[str, Any] = {}
        for label, index in (("DF", det), ("ens", ens)):
            if index is None:
                current[label] = None
                continue
            current[label] = {
                "cycle": index.cycle,
                "leads": len(index.leads),
                "maxLead": index.leads[-1] if index.leads else 0,
                "files": index.file_count(),
                "version": index.product_version,
            }

        with self._lock:
            previous = self.snapshot
            changed = current != previous
            revision_before = self.revision

            if changed and previous:
                for label in ("DF", "ens"):
                    old, new = previous.get(label), current.get(label)
                    if not new:
                        continue
                    if not old:
                        self._push_event(now, "new_product",
                                         f"{label} 产品接入：起报 {new['cycle']}，"
                                         f"{new['leads']} 个时效")
                    elif old["cycle"] != new["cycle"]:
                        self._push_event(now, "new_cycle",
                                         f"{label} 起报时次更新：{old['cycle']} → {new['cycle']}，"
                                         f"共 {new['leads']} 个时效")
                    elif new["files"] > old["files"]:
                        self._push_event(now, "lead_append",
                                         f"{label} 起报 {new['cycle']} 时效追加："
                                         f"{old['leads']} → {new['leads']} 个")

            if changed:
                self.revision = revision_before + (1 if previous else 0)
                self.snapshot = current
                # 数据变化时清空读缓存，保证前端拿到最新场
                if previous and changed:
                    qd.FIELD_CACHE.clear()
                    qd.POINT_CACHE.clear()
                    qd.INDEX_CACHE.clear()

            self.last_scan_at = now
            self.next_scan_at = now + timedelta(seconds=self.interval)
            self.scan_count += 1
            self.error = None

        return current

    def _push_event(self, moment: datetime, kind: str, message: str) -> None:
        self.events.insert(0, {
            "time": moment.isoformat(),
            "kind": kind,
            "message": message,
        })
        del self.events[20:]

    # -- 状态 -------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            now = datetime.now(UTC8)
            last = self.last_scan_at
            return {
                "revision": self.revision,
                "running": bool(self._thread and self._thread.is_alive()),
                "scanIntervalSeconds": self.interval,
                "scanCount": self.scan_count,
                "startedAt": self.started_at.isoformat(),
                "lastScanAt": last.isoformat() if last else None,
                "nextScanAt": self.next_scan_at.isoformat() if self.next_scan_at else None,
                "secondsSinceScan": int((now - last).total_seconds()) if last else None,
                "secondsToNextScan": max(0, int((self.next_scan_at - now).total_seconds()))
                if self.next_scan_at else None,
                "products": self.snapshot,
                "events": list(self.events),
                "error": self.error,
                "serverTime": now.isoformat(),
            }


MONITOR = RealtimeMonitor()
