"""Domena oporavka IS-a: predikati, operatori, vlasništvo akcija i ciljevi.

Zatvoreni svijet: stanje je skup istinitih predikata, sve ostalo je neistina.
STRIPS nema negaciju, pa su "zaustavljeno" i "pokrenuto" zasebni predikati.
"""
from strips import make_op

AGENT_BAZA = "AgentBaza"
AGENT_APP = "AgentAplikacija"
AGENT_NADZOR = "AgentNadzor"

PREDICATES_BAZA = {
    "BazaPokrenuta": "Proces baze podataka radi.",
    "BazaZaustavljena": "Proces baze je zaustavljen (preduvjet za zahvate održavanja).",
    "DiskIspravan": "Disk na kojem su podaci baze je ispravan.",
    "RezervniDisk": "Dostupan je rezervni disk (resurs; troši se zamjenom).",
    "PodaciIspravni": "Podaci baze su konzistentni i neoštećeni.",
    "BackupBaze": "Dostupna je sigurnosna kopija podataka baze (resurs).",
    "ReplikaDostupna": "Dostupna je ispravna replika podataka (resurs).",
    "KonfigBazeIspravna": "Konfiguracija baze je ispravna.",
    "IntegritetPotvrden": "Provjera integriteta provedena je nad pokrenutom bazom s ispravnim podacima.",
    "BazaSpremna": "Baza je službeno spremna za rad (pokrenuta i provjerena).",
}

PREDICATES_APP = {
    "AplikacijaPokrenuta": "Proces aplikacijskog servisa radi.",
    "AplikacijaZaustavljena": "Proces aplikacije je zaustavljen.",
    "InstalacijaIspravna": "Instalacija aplikacije je ispravna.",
    "RepoPaketa": "Dostupan je repozitorij instalacijskih paketa (resurs).",
    "KonfigAppIspravna": "Konfiguracija aplikacije je ispravna.",
    "BackupKonfigApp": "Dostupna je sigurnosna kopija konfiguracije aplikacije (resurs).",
    "PredlozakKonfigApp": "Dostupan je predložak konfiguracije aplikacije (resurs).",
    "VezaUspostavljena": "Aplikacija ima uspostavljenu vezu sa spremnom bazom.",
    "AplikacijaDostupna": "Aplikacija je provjereno dostupna korisnicima (end-to-end provjera prošla).",
}

PREDICATES = {**PREDICATES_BAZA, **PREDICATES_APP}

# Redoslijed preduvjeta je bitan: planer ih postiže tim redom (heuristika).
OPS_BAZA = [
    make_op("ZaustaviBazu", ["BazaPokrenuta"], ["BazaZaustavljena"],
            ["BazaPokrenuta", "IntegritetPotvrden", "BazaSpremna",
             "VezaUspostavljena", "AplikacijaDostupna"]),
    make_op("ZamijeniDisk", ["BazaZaustavljena", "RezervniDisk"], ["DiskIspravan"],
            ["RezervniDisk"]),
    make_op("ObnoviIzBackupa", ["BazaZaustavljena", "DiskIspravan", "BackupBaze"],
            ["PodaciIspravni"]),
    make_op("ObnoviIzReplike", ["BazaZaustavljena", "DiskIspravan", "ReplikaDostupna"],
            ["PodaciIspravni"]),
    make_op("PopraviKonfigBaze", ["BazaZaustavljena"], ["KonfigBazeIspravna"]),
    make_op("PokreniBazu", ["BazaZaustavljena", "DiskIspravan", "KonfigBazeIspravna"],
            ["BazaPokrenuta"], ["BazaZaustavljena"]),
    make_op("ProvjeriIntegritet", ["PodaciIspravni", "BazaPokrenuta"],
            ["IntegritetPotvrden"]),
    make_op("OznaciSpremnom", ["IntegritetPotvrden", "BazaPokrenuta"], ["BazaSpremna"]),
]

OPS_APP = [
    make_op("ZaustaviAplikaciju", ["AplikacijaPokrenuta"], ["AplikacijaZaustavljena"],
            ["AplikacijaPokrenuta", "VezaUspostavljena", "AplikacijaDostupna"]),
    make_op("ReinstalirajAplikaciju", ["AplikacijaZaustavljena", "RepoPaketa"],
            ["InstalacijaIspravna"], ["KonfigAppIspravna"]),
    make_op("VratiKonfigIzBackupa",
            ["AplikacijaZaustavljena", "InstalacijaIspravna", "BackupKonfigApp"],
            ["KonfigAppIspravna"]),
    make_op("GenerirajKonfigIzPredloska",
            ["AplikacijaZaustavljena", "InstalacijaIspravna", "PredlozakKonfigApp"],
            ["KonfigAppIspravna"]),
    make_op("PokreniAplikaciju",
            ["AplikacijaZaustavljena", "InstalacijaIspravna", "KonfigAppIspravna"],
            ["AplikacijaPokrenuta"], ["AplikacijaZaustavljena"]),
    make_op("PoveziSBazom", ["KonfigAppIspravna", "AplikacijaPokrenuta", "BazaSpremna"],
            ["VezaUspostavljena"]),
    make_op("ProvjeriRadSustava", ["VezaUspostavljena", "AplikacijaPokrenuta", "BazaSpremna"],
            ["AplikacijaDostupna"]),
]

ALL_OPS = {op.name: op for op in OPS_BAZA + OPS_APP}

# Vlasništvo akcija: Nadzor odbija akciju koju traži agent koji joj nije vlasnik.
OWNER = {op.name: AGENT_BAZA for op in OPS_BAZA}
OWNER.update({op.name: AGENT_APP for op in OPS_APP})

# Lokalni ciljevi (uređeni: redoslijed je redoslijed postizanja) i zajednički cilj.
G_BAZA = ("BazaSpremna", "PodaciIspravni", "KonfigBazeIspravna")
G_APP = ("KonfigAppIspravna", "InstalacijaIspravna", "AplikacijaDostupna", "BazaSpremna")
G = set(G_BAZA) | set(G_APP)

# Predikati koje agent ne može sam postići, nego ih samo čeka.
EXTERNAL_BAZA = frozenset()
EXTERNAL_APP = frozenset({"BazaSpremna"})


def _ops_table(ops):
    j = lambda xs: ", ".join(xs) if xs else "–"
    lines = ["| Akcija | Preduvjeti | Dodaje (+) | Briše (–) |", "|---|---|---|---|"]
    for op in ops:
        lines.append(f"| {op.name} | {j(op.pre)} | {j(sorted(op.add))} | {j(sorted(op.dele))} |")
    return lines


def _pred_table(preds):
    lines = ["| Predikat | Značenje |", "|---|---|"]
    lines += [f"| {p} | {d} |" for p, d in preds.items()]
    return lines


def dump_domain():
    """Markdown ispis domene (generira se iz istih struktura koje koriste agenti)."""
    j = lambda xs: "{" + ", ".join(xs) + "}"
    out = ["### Predikati – baza", ""] + _pred_table(PREDICATES_BAZA)
    out += ["", "### Predikati – aplikacija", ""] + _pred_table(PREDICATES_APP)
    out += ["", f"### Operatori – {AGENT_BAZA}", ""] + _ops_table(OPS_BAZA)
    out += ["", f"### Operatori – {AGENT_APP}", ""] + _ops_table(OPS_APP)
    out += ["", "### Ciljevi", "",
            f"- G_BAZA = {j(G_BAZA)}",
            f"- G_APP = {j(G_APP)}",
            f"- G = G_BAZA ∪ G_APP = {j(sorted(G))}",
            f"- EXTERNAL_APP = {j(sorted(EXTERNAL_APP))}"]
    return "\n".join(out)
