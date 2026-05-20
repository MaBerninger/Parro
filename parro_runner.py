#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parro_runner.py  -  Deel 4: Elk uur Parro controleren en Signal-updates sturen.
Draait parro_scraper -> parro_ai -> parro_signal in volgorde, wacht dan 1 uur.
"""

import subprocess, sys, os, time
from datetime import datetime

DIR     = os.path.dirname(os.path.abspath(__file__))
PYTHON  = sys.executable
STAPPEN = [
    ("Scraper", os.path.join(DIR, "parro_scraper.py")),
    ("AI",      os.path.join(DIR, "parro_ai.py")),
    ("Signal",  os.path.join(DIR, "parro_signal.py")),
]
INTERVAL = 3600  # seconden (1 uur)


def run_stap(naam, script):
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Stap: {naam}")
    print(f"{'='*60}")
    result = subprocess.run([PYTHON, script])
    if result.returncode != 0:
        print(f"  {naam} afgebroken met exitcode {result.returncode}")
        return False
    return True


def run():
    print(f"Parro runner gestart. Interval: {INTERVAL // 60} minuten.")
    while True:
        print(f"\n{'#'*60}")
        print(f"Run gestart: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")

        for naam, script in STAPPEN:
            ok = run_stap(naam, script)
            if not ok and naam == "Scraper":
                print("Scraper mislukt - AI en Signal overgeslagen tot volgende run.")
                break

        volgende = datetime.now().strftime('%H:%M')
        print(f"\nVolgende run over {INTERVAL // 60} minuten (ca. {volgende} + {INTERVAL // 60}min).")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
