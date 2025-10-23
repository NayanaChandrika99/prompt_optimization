"""Placeholder monitoring script.

This script will eventually poll service metrics and trigger GEPA optimizations.
For now it simply logs that monitoring would start using current configuration.
"""

from __future__ import annotations

import os
import time


def main() -> None:
    interval = int(os.getenv("SIMULATION_INTERVAL_SECONDS", "300"))
    print(f"[monitor] Starting placeholder monitor loop (interval={interval}s).")
    print("[monitor] Press Ctrl+C to exit.")
    try:
        while True:
            # In future this will gather metrics and decide whether to trigger GEPA.
            print("[monitor] Metrics poll skipped (placeholder).")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[monitor] Exiting monitor loop.")


if __name__ == "__main__":
    main()
