# Parro Scraper

Automatisch Parro-schoolberichten ophalen, samenvatten met AI en doorsturen naar Signal.

## Wat doet het?

1. **Scraper** — logt in op [talk.parro.com](https://talk.parro.com) en haalt de laatste berichten op per groep
2. **AI** — vat nieuwe berichten samen met Groq of Gemini (met datums en actiepunten bovenaan)
3. **Signal** — stuurt de samenvatting naar een Signal-groep
4. **Runner** — herhaalt dit automatisch elk uur

## Vereisten

- Python 3.10+
- Java 25 ([Eclipse Temurin](https://adoptium.net))
- [signal-cli 0.14.3](https://github.com/AsamK/signal-cli/releases)
- Een Groq API key ([console.groq.com](https://console.groq.com)) of Gemini API key ([aistudio.google.com](https://aistudio.google.com))

## Installatie

### 1. Repo downloaden
```
git clone https://github.com/MaBerninger/Parro.git
cd Parro
```

### 2. Dependencies installeren
```
pip install -r requirements.txt
playwright install chromium
```

### 3. Config aanmaken
```
copy config.env.example config.env
```
Open `config.env` en vul je eigen gegevens in:

```env
PARRO_EMAIL=jouw@email.nl
PARRO_PASSWORD=jouwwachtwoord
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
SIGNAL_GROUP=jouw_signal_groep_id=
SIGNAL_CONFIG=C:\bets\signal\linked
JAVA_EXE=C:\Program Files\Eclipse Adoptium\jdk-25.x.x.x-hotspot\bin\java.exe
SIGNAL_LIB=C:\bets\signal\lib
```

### 4. Signal koppelen

Installeer signal-cli en koppel het aan je telefoon:
```
signal-cli.bat -c "C:\bets\signal\linked" link -n "parro-pc"
```
Scan de QR-code in de Signal app: **Instellingen → Gekoppelde apparaten → +**

Zoek daarna je Signal groep-ID op:
```
python list_groups.py
```

### 5. Starten

Eenmalig testen:
```
python parro_scraper.py
python parro_ai.py
python parro_signal.py
```

Automatisch elk uur draaien:
```
python parro_runner.py
```

## Bestandsstructuur

```
Parro/
├── parro_scraper.py      # Stap 1: Parro berichten ophalen
├── parro_ai.py           # Stap 2: AI samenvatting maken
├── parro_signal.py       # Stap 3: Versturen naar Signal
├── parro_runner.py       # Stap 4: Automatische hourly runner
├── config.env.example    # Template voor configuratie
├── config.env            # Jouw configuratie (NIET op GitHub)
└── requirements.txt      # Python dependencies
```

## Output voorbeeld

```
Actiepunten:
- 28 mei: Filmdag — toestemmingsformulier invullen
- 18 mei: Schoolreis Buitenhuis (Lucas)

Berichten over Lucas:
- [14 mei] Schoolreis Buitenhuis op 18 mei
- [15 mei] Kamp september, meer info volgt

Berichten over Daniel:
- [13 mei] Gymles dinsdag — jas en gymtas meenemen
```
