"""Pokretanje scenarija: python main.py scenarios/s1.json [--trace] [--dump-domain]

Prije pokretanja mora raditi XMPP server (u zasebnom terminalu: ``spade run``).
"""
import argparse
import asyncio
import json
import logging
import sys

import domain


async def run_scenario(path, trace, delay, timeout, delay_baza=None):
    import protocol as P
    from agents.nadzor import NadzorAgent
    from agents.recovery import RecoveryAgent

    with open(path, encoding="utf-8") as f:
        scenario = json.load(f)
    unknown = set(scenario["initial_state"]) - set(domain.PREDICATES)
    if unknown:
        print(f"Nepoznati predikati u scenariju: {sorted(unknown)}", file=sys.stderr)
        return 1

    P.log(f"SCENARIJ: {scenario['name']}")
    P.log(f"OPIS: {scenario.get('description', '')}")

    nadzor = NadzorAgent(P.JID_NADZOR, P.PASSWORD, scenario["initial_state"])
    baza = RecoveryAgent(P.JID_BAZA, P.PASSWORD, domain.AGENT_BAZA, domain.OPS_BAZA,
                        domain.G_BAZA, domain.EXTERNAL_BAZA, trace=trace, step_delay=delay if delay_baza is None else delay_baza)
    app = RecoveryAgent(P.JID_APP, P.PASSWORD, domain.AGENT_APP, domain.OPS_APP,
                        domain.G_APP, domain.EXTERNAL_APP, trace=trace, step_delay=delay)
    agents = [nadzor, baza, app]
    code = 1
    try:
        await nadzor.start(auto_register=True)      # Nadzor prvi
        await baza.start(auto_register=True)
        await app.start(auto_register=True)
        baza.go.set()
        app.go.set()
        await asyncio.wait_for(
            asyncio.gather(nadzor.finished.wait(), baza.done.wait(), app.done.wait()),
            timeout)
        code = 0 if nadzor.result["satisfied"] else 2
    except asyncio.TimeoutError:
        P.log(f"GLOBALNI TIMEOUT ({timeout} s): sustav nije završio")
        P.log(f"STANJE U TRENUTKU PREKIDA: {P.fmt_state(nadzor.state)}")
    finally:
        for ag in agents:
            if ag.is_alive():
                await ag.stop()
    if nadzor.result is not None:
        r = nadzor.result
        P.log("REZULTAT: " + ("USPJEH" if r["satisfied"]
                              else "NEOSTVARIVO: nedostaje " + P.fmt_state(r["missing"])))
    return code


def main():
    ap = argparse.ArgumentParser(description="Višeagentni oporavak IS-a (SPADE + STRIPS)")
    ap.add_argument("scenario", nargs="?", help="putanja do JSON scenarija")
    ap.add_argument("--dump-domain", action="store_true",
                    help="ispiši predikate, operatore i ciljeve u Markdownu")
    ap.add_argument("--trace", action="store_true", help="ispiši tijek STRIPS pretrage")
    ap.add_argument("--delay", type=float, default=0.05,
                    help="simulirano trajanje jedne akcije u sekundama (zadano 0.05)")
    ap.add_argument("--delay-baza", type=float, default=None,
                    help="zasebno trajanje akcije AgentBaza (za reprodukciju utrke)")
    ap.add_argument("--timeout", type=float, default=60, help="globalni timeout u sekundama")
    args = ap.parse_args()

    if args.dump_domain:
        print(domain.dump_domain())
        return 0
    if not args.scenario:
        ap.error("nedostaje putanja do scenarija")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logging.getLogger("spade").setLevel(logging.ERROR)

    import spade
    box = {}

    async def runner():
        box["code"] = await run_scenario(args.scenario, args.trace, args.delay, args.timeout,
                                         args.delay_baza)

    spade.run(runner())
    return box.get("code", 1)


if __name__ == "__main__":
    sys.exit(main())
