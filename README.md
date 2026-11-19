# Kooperativni oporavak informacijskog sustava (SPADE + STRIPS)

Višeagentna simulacija oporavka baze podataka i aplikacijskog servisa nakon kvara.
Tri SPADE agenta:

- **AgentBaza** – samostalno planira (STRIPS) i izvršava oporavak baze.
- **AgentAplikacija** – samostalno planira (STRIPS) i izvršava oporavak aplikacije.
- **AgentNadzor** – jedini drži i mijenja službeno stanje okoline: provjerava preduvjete,
  primjenjuje akcije, šalje obavijesti i provjerava zajednički cilj.

Sve je simulacija: nema stvarne baze ni poslužitelja, stanje svijeta je skup istinitih predikata.

## Struktura

| Datoteka | Sadržaj |
|---|---|
| `domain.py` | predikati, operatori, vlasništvo akcija (`OWNER`), ciljevi, vanjski predikati |
| `strips.py` | goal-stack STRIPS planer, potpuno neovisan o domeni |
| `protocol.py` | tipovi poruka, izrada poruka (`msg`, `reply`), logiranje |
| `agents/nadzor.py` | `NadzorAgent` |
| `agents/recovery.py` | `RecoveryAgent` – jedna klasa za oba agenta oporavka, parametrizirana operatorima, ciljem i vanjskim predikatima |
| `scenarios/s1.json` … `s4.json` | početna stanja četiriju scenarija |
| `main.py` | pokretanje jednog scenarija |
| `run_all.sh` | pokreće sva 4 scenarija, logovi u `examples/` |
| `tests/test_planner.py` | testovi planera i domene |
| `examples/s1.log` … `s4.log` | primjeri izvršavanja |

## Pokretanje

Potrebno: Python 3.11+ (razvijano na 3.12, SPADE 4.1.4), Linux/WSL.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # ili: pip install spade pytest greenlet
```

> `greenlet` treba instalirati eksplicitno: ugrađeni XMPP server (pyjabber) koristi
> SQLAlchemy asyncio, a `pip install spade` ga ovdje nije povukao sam.

SPADE 4 ima ugrađeni XMPP server. Pokrenite ga u **zasebnom terminalu**:

```bash
source .venv/bin/activate
spade run            # sluša na localhost:5222; --memory ako ne želite datoteku server.db
```

Zatim:

```bash
python main.py scenarios/s1.json           # jedan scenarij
python main.py scenarios/s3.json --trace   # + tijek STRIPS pretrage (stog, pokušaji, backtrack)
python main.py --dump-domain               # tablice predikata, operatora i ciljeva (Markdown)
./run_all.sh                               # sva 4 scenarija -> examples/s{1..4}.log
pytest                                     # testovi planera (ne trebaju XMPP server)
```

Dodatne opcije `main.py`: `--delay S` (simulirano trajanje akcije, zadano 0.05 s), `--timeout S`
(globalni timeout, zadano 60 s). Izlazni kod: 0 = USPJEH, 2 = NEOSTVARIVO, 1 = greška/timeout.

`run_all.sh` sam privremeno pokrene `spade run --memory` ako na portu 5222 ništa ne sluša.
Agenti se registriraju automatski (`nadzor@localhost`, `baza@localhost`, `aplikacija@localhost`).

## Ontologija

Stanje je skup istinitih predikata uz **pretpostavku zatvorenog svijeta** (što nije u skupu, nije
istina). STRIPS nema negaciju u preduvjetima, pa su „pokrenuto” i „zaustavljeno” zasebni predikati
(`BazaPokrenuta` / `BazaZaustavljena`); operatori ih održavaju međusobno isključivima.

Predikati tipa `BackupBaze`, `ReplikaDostupna`, `RezervniDisk`, `RepoPaketa`, `BackupKonfigApp`,
`PredlozakKonfigApp` su **resursi**: nijedan operator ih ne dodaje, pa o njima ovisi koji je put
oporavka moguć (i je li ikoji moguć).

Tablice u nastavku generirane su naredbom `python main.py --dump-domain`, dakle iz istih
struktura podataka koje koriste agenti.

### Predikati – baza

| Predikat | Značenje |
|---|---|
| BazaPokrenuta | Proces baze podataka radi. |
| BazaZaustavljena | Proces baze je zaustavljen (preduvjet za zahvate održavanja). |
| DiskIspravan | Disk na kojem su podaci baze je ispravan. |
| RezervniDisk | Dostupan je rezervni disk (resurs; troši se zamjenom). |
| PodaciIspravni | Podaci baze su konzistentni i neoštećeni. |
| BackupBaze | Dostupna je sigurnosna kopija podataka baze (resurs). |
| ReplikaDostupna | Dostupna je ispravna replika podataka (resurs). |
| KonfigBazeIspravna | Konfiguracija baze je ispravna. |
| IntegritetPotvrden | Provjera integriteta provedena je nad pokrenutom bazom s ispravnim podacima. |
| BazaSpremna | Baza je službeno spremna za rad (pokrenuta i provjerena). |

### Predikati – aplikacija

| Predikat | Značenje |
|---|---|
| AplikacijaPokrenuta | Proces aplikacijskog servisa radi. |
| AplikacijaZaustavljena | Proces aplikacije je zaustavljen. |
| InstalacijaIspravna | Instalacija aplikacije je ispravna. |
| RepoPaketa | Dostupan je repozitorij instalacijskih paketa (resurs). |
| KonfigAppIspravna | Konfiguracija aplikacije je ispravna. |
| BackupKonfigApp | Dostupna je sigurnosna kopija konfiguracije aplikacije (resurs). |
| PredlozakKonfigApp | Dostupan je predložak konfiguracije aplikacije (resurs). |
| VezaUspostavljena | Aplikacija ima uspostavljenu vezu sa spremnom bazom. |
| AplikacijaDostupna | Aplikacija je provjereno dostupna korisnicima (end-to-end provjera prošla). |

### Operatori – AgentBaza

| Akcija | Preduvjeti | Dodaje (+) | Briše (–) |
|---|---|---|---|
| ZaustaviBazu | BazaPokrenuta | BazaZaustavljena | AplikacijaDostupna, BazaPokrenuta, BazaSpremna, IntegritetPotvrden, VezaUspostavljena |
| ZamijeniDisk | BazaZaustavljena, RezervniDisk | DiskIspravan | RezervniDisk |
| ObnoviIzBackupa | BazaZaustavljena, DiskIspravan, BackupBaze | PodaciIspravni | – |
| ObnoviIzReplike | BazaZaustavljena, DiskIspravan, ReplikaDostupna | PodaciIspravni | – |
| PopraviKonfigBaze | BazaZaustavljena | KonfigBazeIspravna | – |
| PokreniBazu | BazaZaustavljena, DiskIspravan, KonfigBazeIspravna | BazaPokrenuta | BazaZaustavljena |
| ProvjeriIntegritet | PodaciIspravni, BazaPokrenuta | IntegritetPotvrden | – |
| OznaciSpremnom | IntegritetPotvrden, BazaPokrenuta | BazaSpremna | – |

### Operatori – AgentAplikacija

| Akcija | Preduvjeti | Dodaje (+) | Briše (–) |
|---|---|---|---|
| ZaustaviAplikaciju | AplikacijaPokrenuta | AplikacijaZaustavljena | AplikacijaDostupna, AplikacijaPokrenuta, VezaUspostavljena |
| ReinstalirajAplikaciju | AplikacijaZaustavljena, RepoPaketa | InstalacijaIspravna | KonfigAppIspravna |
| VratiKonfigIzBackupa | AplikacijaZaustavljena, InstalacijaIspravna, BackupKonfigApp | KonfigAppIspravna | – |
| GenerirajKonfigIzPredloska | AplikacijaZaustavljena, InstalacijaIspravna, PredlozakKonfigApp | KonfigAppIspravna | – |
| PokreniAplikaciju | AplikacijaZaustavljena, InstalacijaIspravna, KonfigAppIspravna | AplikacijaPokrenuta | AplikacijaZaustavljena |
| PoveziSBazom | KonfigAppIspravna, AplikacijaPokrenuta, BazaSpremna | VezaUspostavljena | – |
| ProvjeriRadSustava | VezaUspostavljena, AplikacijaPokrenuta, BazaSpremna | AplikacijaDostupna | – |

### Ciljevi

- G_BAZA = {BazaSpremna, PodaciIspravni, KonfigBazeIspravna}
- G_APP = {KonfigAppIspravna, InstalacijaIspravna, AplikacijaDostupna, BazaSpremna}
- G = G_BAZA ∪ G_APP = {AplikacijaDostupna, BazaSpremna, InstalacijaIspravna, KonfigAppIspravna, KonfigBazeIspravna, PodaciIspravni}
- EXTERNAL_APP = {BazaSpremna}

Redoslijed preduvjeta u tablici je bitan: planer ih postiže tim redom, pa je to heuristika
(npr. `BazaZaustavljena` prije `DiskIspravan`, jer `ZamijeniDisk` traži zaustavljenu bazu).

### Međuovisnosti agenata

- `ZaustaviBazu` briše `BazaSpremna`, `VezaUspostavljena` i `AplikacijaDostupna` – zahvat na bazi
  ruši vezu aplikacije (scenarij 3).
- `ZaustaviAplikaciju` briše `VezaUspostavljena` i `AplikacijaDostupna`.
- `ReinstalirajAplikaciju` briše `KonfigAppIspravna` – nova instalacija dolazi bez konfiguracije.
- `PoveziSBazom` i `ProvjeriRadSustava` traže `BazaSpremna`, koji može postići samo AgentBaza.

### Lokalni i zajednički cilj

Samo pokretanje procesa **ne znači** da je servis oporavljen:

- `BazaPokrenuta` kaže samo da proces radi. Baza je oporavljena tek kad je `BazaSpremna`
  (pokrenuta + `IntegritetPotvrden`, a integritet se može potvrditi samo nad ispravnim podacima),
  uz `PodaciIspravni` i `KonfigBazeIspravna`.
- `AplikacijaPokrenuta` kaže samo da proces radi. Aplikacija s krivom konfiguracijom ili bez veze
  na bazu radi, ali ne služi korisnike. Oporavljena je tek kad je `AplikacijaDostupna`, što daje
  jedino `ProvjeriRadSustava` (end-to-end provjera: veza uspostavljena, aplikacija pokrenuta,
  baza spremna), uz ispravnu instalaciju i konfiguraciju.

`G_APP` sadrži `BazaSpremna` jer aplikacija ne smije potvrditi oporavak dok baza nije spremna.
`BazaSpremna` je za aplikaciju **vanjski predikat** (`EXTERNAL_APP`): ne može ga postići, samo čekati.
Zajednički cilj je `G = G_BAZA ∪ G_APP`; provjerava ga isključivo Nadzor nad službenim stanjem.

## STRIPS algoritam (`strips.py`)

Klasični STRIPS sa **stogom ciljeva** i **povratnim pretraživanjem** (backtracking). Planer ne
zna ništa o domeni: prima stanje, uređeni cilj, listu operatora i skup vanjskih predikata.

Na stogu su tri vrste elemenata:

- `goal p` – jednostavan cilj;
- `conj (p1,…,pn)` – provjera konjunkcije;
- `op O` – operator koji treba primijeniti.

Na početku se na stog stave svi ciljevi redom i ispod njih provjera cijele konjunkcije. Zatim se
obrađuje vrh stoga:

1. **`goal p`, p vrijedi u stanju** → skini sa stoga.
2. **`goal p`, p je vanjski** → u plan se doda pseudo-korak `WAIT:p`, a planer nastavlja kao da p
   vrijedi. Tako agent može isplanirati i korake *nakon* čekanja.
3. **`goal p`, p je već među precima** (ciljevima zbog kojih ga pokušavamo postići) →
   **ciklus**, grana propada.
4. **`goal p` inače** → redom se isprobavaju operatori koji imaju p u listi dodavanja. Za odabrani
   operator na stog idu: njegovi preduvjeti (vanjski na kraj), zatim `conj(preduvjeti)`, zatim
   `op`. Ako grana ne uspije, **backtrack** na sljedeći operator. Ako nijedan ne uspije, cilj je
   neostvariv.
5. **`conj`** → ako svi ciljevi i dalje vrijede, skini; inače (postizanje jednog cilja pokvarilo je
   drugi) ponovno stavi na stog one koji nedostaju.
6. **`op O`** → ako je primjenjiv, primijeni ga na simulirano stanje (`(s − del) ∪ add`) i dodaj u
   plan; inače grana propada.

Prazan stog znači gotov plan; iscrpljene mogućnosti daju `None`. Dubinu ograničava `max_steps`.
S `--trace` ispisuju se sadržaj stoga, pokušaji operatora, WAIT koraci i svaki backtrack.

## Protokol poruka

Tijelo je JSON, npr. `{"type": "ACTION_REQUEST", "agent": "AgentBaza", "action": "ZaustaviBazu"}`.
Tip je i u `metadata["type"]` pa ga behaviouri filtriraju SPADE `Template`-om.

| Poruka | Smjer | Sadržaj / značenje |
|---|---|---|
| `GET_STATE` → `STATE` | agent → Nadzor → agent | `{state}` – trenutno službeno stanje |
| `ACTION_REQUEST` | agent → Nadzor | `{agent, action}` |
| `ACTION_CONFIRM` | Nadzor → agent | `{action, state}` – akcija primijenjena, novo stanje |
| `ACTION_REJECT` | Nadzor → agent | `{action, reason, missing, state}` – stanje nepromijenjeno |
| `DB_READY` | Nadzor → Aplikacija | `BazaSpremna` je prešao iz neistine u istinu |
| `DB_UNREACHABLE` | Nadzor → Aplikacija | AgentBaza je javio `PLAN_FAILED` |
| `LOCAL_GOAL_DONE` | agent → Nadzor | `{agent}` – lokalni plan izvršen do kraja |
| `PLAN_FAILED` | agent → Nadzor | `{agent, reason}` – plan ne postoji ili se ne može izvršiti |
| `GOAL_CHECK` → `GOAL_RESULT` | agent → Nadzor → agent | `{satisfied, missing}` – provjera zajedničkog cilja |

**Nadzor** obrađuje poruke u jednom `CyclicBehaviour`-u, slijedno, pa su akcije atomarne. Akciju
odbija ako ne postoji, ako ju ne traži njezin vlasnik (`OWNER`) ili ako preduvjeti ne vrijede; pri
odbijanju se stanje ne mijenja. Stanje se mijenja *isključivo* primjenom potvrđene akcije – nikad
zato što je agent nešto javio. Kad oba agenta jave ishod, Nadzor provjeri `G ⊆ stanje`, ispiše
završno stanje i `USPJEH` ili `NEOSTVARIVO: nedostaje {...}`. Na `GOAL_CHECK` odgovara tek tada
(raniji upiti čekaju), pa `GOAL_RESULT` uvijek nosi konačan rezultat.

**RecoveryAgent** ne čita scenarij; stanje dobiva samo od Nadzora:

1. `GET_STATE`, izračun plana, ispis plana;
2. ako plana nema → `PLAN_FAILED`;
3. izvršavanje korak po korak preko `ACTION_REQUEST`;
4. na `ACTION_REJECT` → replaniranje iz svježeg stanja;
5. na `WAIT:BazaSpremna` čeka `DB_READY` / `DB_UNREACHABLE` (zaseban behaviour postavlja
   `asyncio.Event`); nakon `DB_READY` **uvijek** replanira, jer se stanje promijenilo; nakon
   `DB_UNREACHABLE` šalje `PLAN_FAILED`;
6. kad plan prođe do kraja → `LOCAL_GOAL_DONE`, zatim `GOAL_CHECK`.

Najviše 5 replaniranja; nakon toga `PLAN_FAILED`.

### Format ispisa

```
[HH:MM:SS.mmm] POŠILJATELJ -> PRIMATELJ TYPE {body}     poslana poruka
[HH:MM:SS.mmm] PRIMATELJ <- POŠILJATELJ TYPE {body}     primljena poruka
[HH:MM:SS.mmm] Agent PLAN / REPLAN #n / POTVRĐENO / ODBIJENO / ZAVRŠNO STANJE / KONAČNI REZULTAT ...
```

## Scenariji

Planovi u nastavku su stvarni izlazi iz `examples/s{n}.log`.

### Scenarij 1 – oštećeni podaci i neispravna konfiguracija

S0 = {BazaZaustavljena, DiskIspravan, BackupBaze, AplikacijaPokrenuta, InstalacijaIspravna, BackupKonfigApp}

- Baza: `ObnoviIzBackupa, PopraviKonfigBaze, PokreniBazu, ProvjeriIntegritet, OznaciSpremnom`
- Aplikacija: `ZaustaviAplikaciju, VratiKonfigIzBackupa, PokreniAplikaciju, WAIT:BazaSpremna, PoveziSBazom, ProvjeriRadSustava`
- Aplikacija izvrši tri pripremna koraka dok se baza još oporavlja, pa čeka. Nakon `DB_READY`
  replan: `PoveziSBazom, ProvjeriRadSustava`.
- Rezultat: **USPJEH**

### Scenarij 2 – neispravan disk i oštećena instalacija

S0 = {BazaZaustavljena, RezervniDisk, ReplikaDostupna, KonfigBazeIspravna, AplikacijaZaustavljena, RepoPaketa, PredlozakKonfigApp}

- Baza: `ZamijeniDisk, ObnoviIzReplike, PokreniBazu, ProvjeriIntegritet, OznaciSpremnom`
- Aplikacija: `ReinstalirajAplikaciju, GenerirajKonfigIzPredloska, PokreniAplikaciju, WAIT:BazaSpremna, PoveziSBazom, ProvjeriRadSustava`
- Nakon `DB_READY` replan: `PoveziSBazom, ProvjeriRadSustava`.
- Rezultat: **USPJEH**. Drugi resursi → drugi put oporavka nego u scenariju 1 (replika umjesto
  backupa, predložak umjesto backupa konfiguracije, zamjena diska, reinstalacija).

### Scenarij 3 – pokrenuti servisi i gubitak veze

S0 = {BazaPokrenuta, DiskIspravan, BackupBaze, KonfigBazeIspravna, AplikacijaPokrenuta, InstalacijaIspravna, KonfigAppIspravna, VezaUspostavljena}

- Baza: `ZaustaviBazu, ObnoviIzBackupa, PokreniBazu, ProvjeriIntegritet, OznaciSpremnom`
- Aplikacija, početni plan: `WAIT:BazaSpremna, ProvjeriRadSustava` (veza u tom trenutku još postoji).
- `ZaustaviBazu` u međuvremenu obriše `VezaUspostavljena`. Nakon `DB_READY` aplikacija replanira
  iz novog stanja: `PoveziSBazom, ProvjeriRadSustava`. Početni plan bi bio odbijen; replan ga
  ispravlja.
- Rezultat: **USPJEH**

### Scenarij 4 – neostvariv oporavak

S0 = {BazaZaustavljena, DiskIspravan, KonfigBazeIspravna, AplikacijaPokrenuta, InstalacijaIspravna, KonfigAppIspravna}

- Baza: plan `None` – `PodaciIspravni` se može dobiti samo iz backupa ili replike, a nema nijednog
  → `PLAN_FAILED`.
- Aplikacija: `WAIT:BazaSpremna, PoveziSBazom, ProvjeriRadSustava`; čeka, dobije `DB_UNREACHABLE`
  i javi `PLAN_FAILED`.
- Rezultat: **NEOSTVARIVO: nedostaje {AplikacijaDostupna, BazaSpremna, PodaciIspravni}**. Stanje
  ostaje netaknuto, uspjeh se ne prijavljuje.

## Kako se vidi da planove generiraju agenti, a ne hardkod

- U kodu nema nijednog popisa akcija po scenariju. `strips.py` ne uvozi `domain.py` i ne spominje
  nijedan predikat ni akciju; `agents/recovery.py` ne zna koji se scenarij izvodi i ne čita
  datoteku scenarija – stanje dobiva porukom `GET_STATE`.
- Scenarij je samo JSON s početnim stanjem. Promijenite ga i plan se mijenja bez diranja koda;
  npr. u `s1.json` zamijenite `BackupBaze` s `ReplikaDostupna` i baza će planirati `ObnoviIzReplike`.
- Testovi (`pytest`) to provjeravaju: isti planer i isti operatori daju različite planove za
  različita stanja, simulirana primjena svakog plana zaista postiže cilj, a planer radi i na
  posve drugoj (izmišljenoj) domeni.
- Svaki log prije plana ispisuje stanje iz kojeg je plan izračunan (`PLAN iz stanja {...}`), a
  `--trace` pokazuje cijelu pretragu: stog ciljeva, isprobane operatore i backtracking.
- Replan u scenariju 3 ne bi bio moguć s unaprijed zadanim planom: nastaje jer je drugi agent
  promijenio stanje tijekom izvršavanja.
