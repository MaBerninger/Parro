#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parro_ai.py  -  Deel 2: Nieuwe berichten samenvatten met AI (Groq / Gemini).
Leest parro_messages.json, verwerkt alleen berichten met ai_processed=false,
slaat de samenvatting op in parro_ai_log.json.
"""

from dotenv import load_dotenv
import json, os, re, requests
from datetime import datetime

DIR           = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(DIR, "parro_messages.json")
AI_LOG_FILE   = os.path.join(DIR, "parro_ai_log.json")
load_dotenv(os.path.join(DIR, "config.env"))

GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

_AI_SYSTEEM = (
    "Je bent een behulpzame assistent voor ouders. "
    "Vat Parro-schoolberichten samen in het Nederlands. Gebruik korte zinnen. "
    "Structureer de samenvatting als volgt:\n"
    "1. DATUMS & ACTIEPUNTEN: vermeld ALTIJD de verzenddatum van elk bericht (staat tussen []), "
    "en haal alle concrete datums, deadlines en gebeurtenissen eruit (bijv. uitstapjes, gym, kamp, formulieren). "
    "Zet ze op chronologische volgorde met datum erbij.\n"
    "2. SAMENVATTING PER GROEP: korte opsomming per groep.\n"
    "Geen overbodige inleiding, gewoon meteen de inhoud."
)


def _strip_md(tekst):
    tekst = re.sub(r'\*+', '', tekst)
    tekst = re.sub(r'#+\s?', '', tekst)
    tekst = re.sub(r'`+', '', tekst)
    return tekst.strip()


def _vraag_groq(tekst, model="llama-3.3-70b-versatile"):
    r = requests.post(GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": model,
              "messages": [{"role": "system", "content": _AI_SYSTEEM},
                           {"role": "user",   "content": tekst}],
              "max_tokens": 1000}, timeout=30)
    if r.status_code == 429:
        raise Exception("RATE_LIMIT")
    r.raise_for_status()
    return _strip_md(r.json()["choices"][0]["message"]["content"])


def _vraag_gemini(tekst, model="gemini-2.5-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={
        "system_instruction": {"parts": [{"text": _AI_SYSTEEM}]},
        "contents": [{"parts": [{"text": tekst}]}],
        "generationConfig": {"maxOutputTokens": 1000}}, timeout=30)
    if r.status_code == 429:
        raise Exception("RATE_LIMIT")
    r.raise_for_status()
    return _strip_md(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def vraag_ai(tekst):
    for naam, fn in [
        ("Groq Llama3",  lambda t: _vraag_groq(t, "llama-3.3-70b-versatile")),
        ("Groq Mixtral", lambda t: _vraag_groq(t, "mixtral-8x7b-32768")),
        ("Gemini Flash", lambda t: _vraag_gemini(t, "gemini-2.5-flash")),
        ("Gemini Lite",  lambda t: _vraag_gemini(t, "gemini-2.5-flash-lite")),
    ]:
        try:
            antwoord = fn(tekst)
            print(f"[AI] {naam}")
            return antwoord
        except Exception as e:
            print(f"[!] {naam} mislukt: {e}")
    return "(AI niet beschikbaar)"


def load_messages():
    if not os.path.isfile(MESSAGES_FILE):
        print(f"Geen {MESSAGES_FILE} gevonden. Eerst parro_scraper.py draaien.")
        return None
    with open(MESSAGES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_messages(data):
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_ai_log():
    if not os.path.isfile(AI_LOG_FILE):
        return []
    with open(AI_LOG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ai_log(log):
    with open(AI_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def run():
    data = load_messages()
    if data is None:
        return

    messages     = data.get("messages", [])
    new_messages = [m for m in messages if not m.get("ai_processed")]

    if not new_messages:
        print("Geen nieuwe berichten om te verwerken.")
        return

    print(f"{len(new_messages)} nieuwe berichten gevonden, AI samenvatting maken...")

    # Groepeer per label voor een overzichtelijke prompt
    groups = {}
    for m in new_messages:
        groups.setdefault(m["group_label"], []).append(m)

    regels = []
    for label, msgs in groups.items():
        regels.append(f"\n## {label}")
        for m in msgs:
            regel = f"- [{m['created']}] {m['owner']}: {m['title']}"
            if m.get("contents"):
                regel += f": {m['contents']}"
            regels.append(regel)

    vandaag = datetime.now().strftime("%d %B %Y")
    prompt = (
        f"Vandaag is {vandaag}. "
        "Hieronder staan nieuwe Parro-schoolberichten per groep (verzenddatum staat tussen []). "
        "Vat ze samen. Vermeld de verzenddatum bij elk bericht en haal alle genoemde datums eruit.\n"
        + "\n".join(regels)
    )

    samenvatting = vraag_ai(prompt)
    print("\nSamenvatting:")
    print(samenvatting)

    # Sla samenvatting op in AI log
    ai_log = load_ai_log()
    ai_log.append({
        "timestamp":   datetime.now().isoformat(timespec="seconds"),
        "message_ids": [m["id"] for m in new_messages],
        "summary":     samenvatting,
        "signal_sent": False,
    })
    save_ai_log(ai_log)
    print(f"\nAI log opgeslagen -> {AI_LOG_FILE}")

    # Markeer berichten als verwerkt
    processed_ids = {m["id"] for m in new_messages}
    for m in messages:
        if m["id"] in processed_ids:
            m["ai_processed"] = True
    save_messages(data)
    print(f"parro_messages.json bijgewerkt (ai_processed=true voor {len(processed_ids)} berichten)")


if __name__ == "__main__":
    run()
