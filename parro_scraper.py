#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parro_scraper.py  -  Deel 1: Parro berichten scrapen en opslaan in parro_messages.json.
"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os, time, re, sys, json, hashlib
from datetime import datetime

DIR           = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(DIR, "parro_messages.json")
load_dotenv(os.path.join(DIR, "config.env"))

EMAIL    = os.environ["PARRO_EMAIL"]
PASSWORD = os.environ["PARRO_PASSWORD"]
URL      = "https://talk.parro.com/"
API_BASE = "https://rest-v2.parro.com/rest/v2"
API_CONTENT_TYPE  = "application/vnd.topicus.geon+json;version=217"
PARRO_APP_VERSION = "web:2.23.2"
FALLBACK_ROLE     = "GUARDIAN:128571455"
DEBUG_EVENTS = False
KNOWN_GROUPS = [
    ("Hobbitstee", "5351136730", "de Hobbitstee"),
    ("Daniel",     "5353690352", "4. Pepijnstee"),
    ("Lucas",      "5361337884", "7. Dwalinstee"),
]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def is_event_url(url):
    return "rest-v2.parro.com/rest/v2/event?dtype=event.RAnnouncementEventPrimer" in url


def short_header_value(name, value):
    if name.lower() in {"cookie", "authorization"} and value:
        return value[:80] + ("..." if len(value) > 80 else "")
    return value


def log_event_request(request):
    if not DEBUG_EVENTS:
        return
    if not is_event_url(request.url):
        return
    print("\n[EVENT REQUEST]")
    print(f"  {request.method} {request.url}")
    try:
        headers = request.headers
        for name in sorted(headers):
            if name.lower() in {"accept", "content-type", "origin", "parro-app-version",
                                 "parro-authorization-role", "range", "referer"}:
                print(f"  {name}: {short_header_value(name, headers.get(name, ''))}")
    except Exception as e:
        print(f"  request headers lezen mislukt: {e}")


def log_event_response(response, api_cache):
    if not DEBUG_EVENTS:
        return
    if not is_event_url(response.url):
        return
    print("[EVENT RESPONSE]")
    print(f"  status={response.status} url={response.url}")
    match = re.search(r"[?&]group=([^&]+)", response.url)
    group_id = match.group(1) if match else "?"
    print(f"  group={group_id} cached={group_id in api_cache.get('events', {})}")
    if response.status >= 400:
        try:
            print(f"  body={response.text()[:500]}")
        except Exception as e:
            print(f"  body lezen mislukt: {e}")


def click_flutter_view(page, label="flutter-view"):
    try:
        view = page.locator("flutter-view").first
        view.wait_for(state="visible", timeout=15000)
        box = view.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        else:
            view.click(timeout=5000, force=True)
        print(f"Geklikt op {label}")
        time.sleep(1)
    except Exception as e:
        print(f"{label} klik overgeslagen: {e}")


def enable_flutter_accessibility(page):
    print("Flutter accessibility activeren...")
    try:
        placeholder = page.locator('flt-semantics-placeholder[aria-label="Enable accessibility"]').first
        placeholder.evaluate("""el => {
            el.focus(); el.click();
            el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('click',     { bubbles: true, cancelable: true, view: window }));
        }""")
        page.keyboard.press("Enter")
        time.sleep(2)
        print("Flutter semantics geactiveerd")
    except Exception as e:
        print(f"Flutter semantics activatie overgeslagen: {e}")


def click_initial_login(page):
    print("Klikken op eerste Inloggen knop...")
    enable_flutter_accessibility(page)
    for locator in (
        page.get_by_role("button", name=re.compile(r"^\s*Inloggen\s*$", re.I)),
        page.locator('[role="button"][aria-label="Inloggen"]').first,
        page.locator('[aria-label="Inloggen"]').first,
        page.locator("flt-semantics:has-text('Inloggen')").first,
        page.locator("text=Inloggen").first,
    ):
        try:
            locator.click(timeout=4000, force=True)
            print("Eerste Inloggen knop geklikt")
            time.sleep(2)
            return
        except Exception:
            pass
    print("Eerste Inloggen knop niet gevonden")


def debug_page_state(page, label):
    print(f"\n{'='*60}\nDEBUG: {label}\n{'='*60}")
    try:
        print(f"URL: {page.url}")
    except Exception:
        pass


def cache_parro_response(response, api_cache):
    url = response.url
    if "rest-v2.parro.com/rest/v2/" not in url:
        return
    print(f"  [API] {response.status} {url[:120]}")
    if response.status not in (200, 206):
        return
    try:
        data = response.json()
    except Exception:
        return
    if "/account/me" in url:
        api_cache["account_me"] = data
    elif "/group?dtype=identity.RHomeGroup" in url:
        api_cache["groups"] = data
    elif "/child" in url:
        api_cache["children"] = data
    elif "/identity/unreadcounts" in url:
        api_cache["unreadcounts"] = data
    elif "/event?dtype=event.RAnnouncementEventPrimer" in url:
        match = re.search(r"[?&]group=([^&]+)", url)
        if match:
            api_cache.setdefault("events", {})[match.group(1)] = data


def fetch_parro_json(page, path, role=None, extra_headers=None):
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    headers = {
        "accept": API_CONTENT_TYPE,
        "content-type": API_CONTENT_TYPE,
        "parro-app-version": PARRO_APP_VERSION,
        "origin": "https://talk.parro.com",
        "referer": "https://talk.parro.com/",
        "accept-language": "nl-NL,nl;q=0.9",
    }
    if role:
        headers["parro-authorization-role"] = role
    if extra_headers:
        headers.update(extra_headers)
    response = page.context.request.get(url, headers=headers)
    if response.status < 200 or response.status >= 300:
        raise RuntimeError(f"Parro API fout {response.status}: {response.text()[:500]}")
    return response.json()


def list_items(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("items", "data", "results", "content", "entities"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    lists = []
    def walk(value):
        if isinstance(value, list):
            lists.append(value)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)
    walk(data)
    return max(lists, key=len) if lists else []


def link_id(item):
    for link in item.get("links", []) if isinstance(item, dict) else []:
        if link.get("rel") == "self" and link.get("id") is not None:
            return str(link["id"])
    for link in item.get("links", []) if isinstance(item, dict) else []:
        if link.get("id") is not None:
            return str(link["id"])
    if isinstance(item, dict) and item.get("id") is not None:
        return str(item["id"])
    return ""


def get_guardian_role(account):
    identity = account.get("identity", {}) if isinstance(account, dict) else {}
    for guardian in identity.get("guardians", []):
        guardian_id = link_id(guardian)
        if guardian_id:
            return f"GUARDIAN:{guardian_id}"
    return None


def compact_text(text, limit=260):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit - 3].rstrip() + "..."


def owner_name(event):
    owner = event.get("owner", {}) if isinstance(event, dict) else {}
    name = f"{owner.get('firstname', '')} {owner.get('surname', '')}".strip()
    return name or "-"


def load_missing_events_via_page_fetch(page, api_cache, role):
    print("\nParro events laden via groep-klikken...")
    missing = [(lbl, gid, nm) for lbl, gid, nm in KNOWN_GROUPS if gid not in api_cache.get("events", {})]
    if not missing:
        print("  Alle events al in cache.")
        return True

    GROUP_COORDS = {
        "5351136730": (171, 224),
        "5353690352": (165, 278),
        "5361337884": (168, 332),
    }
    print("  Even wachten tot Flutter UI klaar is...")
    time.sleep(4)

    for label, group_id, group_name in missing:
        xy = GROUP_COORDS.get(group_id)
        if xy is None:
            print(f"  {label}: geen coordinaten bekend, overslaan")
            continue
        for attempt, dy in enumerate([0, 8, 16, 24]):
            click_xy = (xy[0], xy[1] + dy)
            print(f"  klikken: {label} ({group_name}) op {click_xy} (poging {attempt+1})")
            page.mouse.click(click_xy[0], click_xy[1])
            deadline = time.time() + 20
            while time.time() < deadline:
                time.sleep(1)
                if group_id in api_cache.get("events", {}):
                    print(f"    events ontvangen voor {label}")
                    break
            if group_id in api_cache.get("events", {}):
                break
            print(f"    geen events na 20s, opnieuw proberen...")
            time.sleep(1)
        if group_id not in api_cache.get("events", {}):
            print(f"  timeout: {label} events niet ontvangen na alle pogingen")
        time.sleep(2)

    return all(gid in api_cache.get("events", {}) for _, gid, _ in KNOWN_GROUPS)


def targets_from_groups(groups):
    targets = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        name = group.get("name", "")
        group_id = link_id(group)
        low = name.lower()
        if "hobbitstee" in low and group.get("type") == "SCHOOLWIDE":
            targets.append(("Hobbitstee", group_id, name))
        elif "pepijnstee" in low or low.startswith("4."):
            targets.append(("Daniel", group_id, name))
        elif "dwalinstee" in low or low.startswith("7."):
            targets.append(("Lucas", group_id, name))
    seen = set()
    clean = []
    for label, group_id, name in targets:
        if group_id and group_id not in seen:
            seen.add(group_id)
            clean.append((label, group_id, name))
    found_labels = {label for label, _, _ in clean}
    for fallback in KNOWN_GROUPS:
        if fallback[0] not in found_labels:
            clean.append(fallback)
    return clean


def wait_for_parro_api_ready(page, api_cache, timeout=60):
    print("Wachten tot Parro API-data geladen heeft...")
    start = time.time()
    last_status = 0
    while time.time() - start < timeout:
        account_ready = bool(api_cache.get("account_me"))
        groups_ready  = bool(api_cache.get("groups"))
        if account_ready and groups_ready:
            print("Parro API-data geladen.")
            return True
        elapsed = int(time.time() - start)
        if elapsed - last_status >= 5:
            last_status = elapsed
            try:
                url = page.url
            except Exception:
                url = "-"
            print(f"  {elapsed}s | account={account_ready} groups={groups_ready} | {url[:80]}")
        if elapsed >= 5:
            try:
                fetch_parro_json(page, "/group?dtype=identity.RHomeGroup", role=FALLBACK_ROLE)
                print("Parro API bereikbaar via fallback-role.")
                return True
            except Exception:
                pass
        time.sleep(1)
    print("Parro API timeout. Doorgaan met beschikbare data.")
    return False


# =========================
# JSON opslaan
# =========================

def _event_id(group_id, event):
    key = f"{group_id}|{event.get('createdAt') or event.get('sortDate') or ''}|{event.get('title') or ''}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def save_messages_to_json(api_cache, targets):
    existing_by_id    = {}
    existing_by_group = {}
    if os.path.isfile(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for m in data.get("messages", []):
                existing_by_id[m["id"]] = m
                existing_by_group.setdefault(m["group_id"], []).append(m)
        except Exception:
            pass

    now_str = datetime.now().isoformat(timespec="seconds")
    updated_messages = []
    new_count = 0

    for label, group_id, group_name in targets:
        event_data = api_cache.get("events", {}).get(group_id)
        if event_data is None:
            # Geen nieuwe data — bewaar bestaande berichten voor deze groep
            for m in existing_by_group.get(group_id, []):
                updated_messages.append(m)
            print(f"  {label}: geen nieuwe events, bestaande berichten bewaard.")
            continue

        events = list_items(event_data)
        for event in events[:5]:
            eid = _event_id(group_id, event)
            if eid in existing_by_id:
                updated_messages.append(existing_by_id[eid])
            else:
                new_count += 1
                created  = event.get("createdAt") or event.get("sortDate") or "-"
                title    = compact_text(event.get("title") or "(geen titel)", 120)
                contents = compact_text(event.get("contents") or event.get("richTextContents") or "", 320)
                msg = {
                    "id":           eid,
                    "group_label":  label,
                    "group_id":     group_id,
                    "group_name":   group_name,
                    "created":      created,
                    "owner":        owner_name(event),
                    "title":        title,
                    "contents":     contents,
                    "ai_processed": False,
                    "signal_sent":  False,
                    "scraped_at":   now_str,
                }
                updated_messages.append(msg)
                print(f"  NIEUW: [{label}] {title}")

    out = {"last_scraped": now_str, "messages": updated_messages}
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\nJSON opgeslagen: {len(updated_messages)} berichten ({new_count} nieuw) -> {MESSAGES_FILE}")
    return new_count


def scrape_messages(page, api_cache):
    print("\n" + "=" * 80)
    print("Parro berichten scrapen")
    print("=" * 80)
    try:
        account = api_cache.get("account_me")
        role = get_guardian_role(account) or FALLBACK_ROLE
        print(f"API role: {role}")

        load_missing_events_via_page_fetch(page, api_cache, role)

        group_data = api_cache.get("groups") or fetch_parro_json(page, "/group?dtype=identity.RHomeGroup", role=role)
        groups = list_items(group_data)
        if not groups:
            print("Geen groepen gevonden.")
            return

        targets = targets_from_groups(groups)
        if not targets:
            print("Geen bekende groepen herkend.")
            return

        for label, group_id, group_name in targets:
            print(f"\n--- {label} - {group_name} ---")
            event_data = api_cache.get("events", {}).get(group_id)
            if event_data is None:
                print(f"  Geen events voor {label}")
                continue
            for i, event in enumerate(list_items(event_data)[:5], 1):
                created  = event.get("createdAt") or event.get("sortDate") or "-"
                title    = compact_text(event.get("title") or "(geen titel)", 120)
                contents = compact_text(event.get("contents") or event.get("richTextContents") or "", 320)
                print(f"  {i}. {created} | {owner_name(event)} | {title}")
                if contents:
                    print(f"     {contents}")

        save_messages_to_json(api_cache, targets)

    except Exception as e:
        print(f"Scrapen mislukt: {e}")
    print("=" * 80)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        api_cache = {}
        page.on("request", log_event_request)

        def handle_response(response):
            cache_parro_response(response, api_cache)
            log_event_response(response, api_cache)

        page.on("response", handle_response)

        print(f"Navigeren naar {URL} ...")
        page.goto(URL, wait_until="domcontentloaded")
        print("8 seconden wachten tot Parro/Flutter geladen is...")
        time.sleep(8)
        debug_page_state(page, "na openen en 8s wachten")

        click_flutter_view(page, "eerste flutter-view")
        click_initial_login(page)
        debug_page_state(page, "na eerste Inloggen klikpoging")

        print("Wachten op e-mailadres veld...")
        page.wait_for_selector('input[data-testid="e-mailadres"]', timeout=20000)
        print("Invullen e-mailadres...")
        page.fill('input[data-testid="e-mailadres"]', EMAIL)
        time.sleep(0.4)
        print("Invullen wachtwoord...")
        page.fill('input[data-testid="wachtwoord"]', PASSWORD)
        time.sleep(0.4)
        print("Klikken op Inloggen...")
        page.locator('a.authenticator--button:has-text("Inloggen"), #id3').first.click(timeout=10000)
        time.sleep(2)

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        print(f"Huidige URL: {page.url}")
        click_flutter_view(page, "flutter-view na login")
        wait_for_parro_api_ready(page, api_cache, timeout=75)

        scrape_messages(page, api_cache)

        print("\nScraper klaar. Browser wordt gesloten.")
        browser.close()


if __name__ == "__main__":
    run()
