# Njord A – Isoleringsliste Lookup v2.0

Utstyrssøk-app for Njord A med **live-deling mellom PC og telefon**.

## Ny funksjon: Sesjons-deling

Søk opp og fest utstyr på PC-en, og få det opp på telefonen når du går ut i felt.

### Slik fungerer det

1. **På PC-en:** Søk og fest utstyr som vanlig. Trykk del-ikonet (↑) og klikk **"Start deling"**
2. Du får en sesjonskode (f.eks. `FISK-42`) og en QR-kode
3. **På telefonen:** Skann QR-koden, eller åpne appen og skriv inn koden manuelt via **"Koble til"**
4. Festede utstyr synkroniseres automatisk — telefonen poller serveren hvert 3. sekund

### Teknisk

- Pins lagres i **SQLite** på serveren (i Docker-volume `njord-data`)
- Sesjoner lever i **24 timer**, deretter ryddes de automatisk
- Sesjonskoder er norske ord + tall (`TROLL-77`, `LAKS-42`, `FJORD-15`)
- Ingen login — bare en kort kode
- QR-koden inneholder URL med `?session=KODE` som auto-kobler telefonen

### API-endepunkter (nye)

| Metode | Endepunkt | Beskrivelse |
|--------|-----------|-------------|
| POST | `/api/session` | Opprett ny sesjon (med valgfrie pins) |
| GET | `/api/session/<kode>` | Hent pins for en sesjon |
| POST | `/api/session/<kode>/pin` | Legg til én pin |
| DELETE | `/api/session/<kode>/pin` | Fjern én pin |
| POST | `/api/session/<kode>/sync` | Full sync — erstatt alle pins |

## Deployment

```bash
docker compose up -d --build
```

Appen kjører på port **5055**. SQLite-databasen persistes i Docker-volumet `njord-data`.

### Filer som er endret

- `app.py` — Ny backend med SQLite session-håndtering
- `templates/index.html` — Nytt deling-panel med QR, kode-input, polling
- `docker-compose.yml` — Lagt til volume for datalagring
- `Dockerfile` — Lagt til entrypoint for data-katalog-håndtering

---
Laget av Fredrik Karlsen — 2026
