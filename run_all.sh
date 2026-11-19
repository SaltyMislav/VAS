#!/usr/bin/env bash
# Pokrene sva 4 scenarija i spremi izlaze u examples/s{n}.log (bez ANSI boja).
# Ako XMPP server ne radi na portu 5222, privremeno ga pokrene (spade run).
cd "$(dirname "$0")" || exit 1
[ -f .venv/bin/activate ] && source .venv/bin/activate
export NO_COLOR=1 PYTHONUNBUFFERED=1
mkdir -p examples

port_open() { (exec 3<>/dev/tcp/127.0.0.1/5222) 2>/dev/null; }

SERVER_PID=""
if ! port_open; then
    echo "XMPP server ne radi; pokrećem 'spade run' ..."
    spade run --memory >/dev/null 2>&1 &
    SERVER_PID=$!
    trap '[ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null' EXIT
    for _ in $(seq 1 50); do port_open && break; sleep 0.2; done
    port_open || { echo "XMPP server se nije pokrenuo." >&2; exit 1; }
fi

for n in 1 2 3 4; do
    python main.py "scenarios/s$n.json" "$@" 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' > "examples/s$n.log"
    echo "s$n: $(grep -m1 'KONAČNI REZULTAT' "examples/s$n.log" | sed 's/.*KONAČNI REZULTAT: //' || true)"
done
