#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parro_signal.py  -  Deel 3: Nieuwe AI-samenvattingen doorsturen naar Signal.
Leest parro_ai_log.json en stuurt entries met signal_sent=false naar de Signal-groep.
"""

from dotenv import load_dotenv
import json, os, re, subprocess, time
from datetime import datetime

DIR         = os.path.dirname(os.path.abspath(__file__))
AI_LOG_FILE = os.path.join(DIR, "parro_ai_log.json")
load_dotenv(os.path.join(DIR, "config.env"))

SIGNAL_CONFIG = os.environ["SIGNAL_CONFIG"]
SIGNAL_GROUP  = os.environ["SIGNAL_GROUP"]
JAVA_EXE      = os.environ["JAVA_EXE"]
SIGNAL_MAIN   = "org.asamk.signal.Main"
SIGNAL_JVM    = "--enable-native-access=ALL-UNNAMED"

_L = os.environ["SIGNAL_LIB"]
SIGNAL_CP = ";".join([
    rf"{_L}\signal-cli-0.14.3.jar", rf"{_L}\libsignal-cli-0.14.3.jar",
    rf"{_L}\bcprov-jdk18on-1.84.jar", rf"{_L}\jackson-core-2.20.2.jar",
    rf"{_L}\signal-service-java-2.15.3_unofficial_144.jar",
    rf"{_L}\jackson-module-kotlin-2.20.2.jar", rf"{_L}\jackson-databind-2.20.2.jar",
    rf"{_L}\argparse4j-0.9.0.jar", rf"{_L}\jul-to-slf4j-2.0.17.jar",
    rf"{_L}\logback-classic-1.5.32.jar", rf"{_L}\dbus-java-core-5.0.0.jar",
    rf"{_L}\micronaut-inject-5.0.0-M17.jar", rf"{_L}\HikariCP-7.0.2.jar",
    rf"{_L}\micronaut-core-5.0.0-M17.jar", rf"{_L}\slf4j-api-2.0.17.jar",
    rf"{_L}\core-3.5.4.jar", rf"{_L}\jackson-annotations-2.21.jar",
    rf"{_L}\logback-core-1.5.32.jar", rf"{_L}\sqlite-jdbc-3.53.0.0.jar",
    rf"{_L}\jakarta.inject-api-2.0.1.jar", rf"{_L}\jakarta.annotation-api-2.1.1.jar",
    rf"{_L}\models-jvm-2.15.3_unofficial_144.jar", rf"{_L}\util-jvm-2.15.3_unofficial_144.jar",
    rf"{_L}\libsignal-client-0.92.1.jar", rf"{_L}\kotlinx-coroutines-core-jvm-1.10.2.jar",
    rf"{_L}\kotlin-reflect-2.3.10.jar", rf"{_L}\rxkotlin-3.0.1.jar",
    rf"{_L}\wire-runtime-jvm-4.9.11.jar", rf"{_L}\kotlin-stdlib-jdk8-2.3.10.jar",
    rf"{_L}\okhttp-jvm-5.3.2.jar", rf"{_L}\kotlin-stdlib-2.3.10.jar",
    rf"{_L}\kotlinx-serialization-json-jvm-1.9.0.jar", rf"{_L}\okio-jvm-3.16.4.jar",
    rf"{_L}\rxjava-3.0.13.jar", rf"{_L}\reactive-streams-1.0.4.jar",
    rf"{_L}\libphonenumber-8.13.50.jar",
])


def _send_sectie(tekst):
    """Stuur één sectie (mag newlines bevatten) via Java direct. Geeft True bij succes."""
    if not tekst.strip():
        return True
    try:
        result = subprocess.run(
            [JAVA_EXE, SIGNAL_JVM, "-classpath", SIGNAL_CP, SIGNAL_MAIN,
             "-c", SIGNAL_CONFIG, "send", "-m", tekst, "-g", SIGNAL_GROUP],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  Signal fout: {result.stderr.strip()[:200]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  Signal timeout (60s)")
        return False
    except Exception as e:
        print(f"  Signal fout: {e}")
        return False


def send_signal(tekst):
    """
    Splits de samenvatting op lege regels in secties en stuurt elke sectie
    als apart Signal-bericht (met enters behouden).
    Geeft True terug als alles gelukt is.
    """
    if not tekst.strip():
        return True
    secties = [s.strip() for s in re.split(r'\n\s*\n', tekst) if s.strip()]
    ok = True
    for i, sectie in enumerate(secties):
        if not _send_sectie(sectie):
            ok = False
        if i < len(secties) - 1:
            time.sleep(0.4)
    if ok:
        print(f"  Signal: {len(secties)} bericht(en) verstuurd")
    return ok


def load_ai_log():
    if not os.path.isfile(AI_LOG_FILE):
        print(f"Geen {AI_LOG_FILE} gevonden. Eerst parro_ai.py draaien.")
        return None
    with open(AI_LOG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ai_log(log):
    with open(AI_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def run():
    ai_log = load_ai_log()
    if ai_log is None:
        return

    te_sturen = [e for e in ai_log if not e.get("signal_sent")]
    if not te_sturen:
        print("Geen nieuwe samenvattingen om te versturen.")
        return

    print(f"{len(te_sturen)} samenvatting(en) versturen naar Signal...")
    for entry in te_sturen:
        ts  = entry.get("timestamp", "?")
        msg = f"Parro update ({ts}):\n\n{entry['summary']}"
        print(f"\n--- Te versturen ---\n{msg}\n")
        ok = send_signal(msg)
        if ok:
            entry["signal_sent"]    = True
            entry["signal_sent_at"] = datetime.now().isoformat(timespec="seconds")
        else:
            print("  Versturen mislukt — wordt opnieuw geprobeerd bij volgende run.")

    save_ai_log(ai_log)
    print(f"\nAI log bijgewerkt -> {AI_LOG_FILE}")


if __name__ == "__main__":
    run()
