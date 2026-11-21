"""RecoveryAgent: generički agent za oporavak (baza ili aplikacija).

Parametriziran je operatorima, lokalnim ciljem i vanjskim predikatima; plan
računa STRIPS-om iz stanja dohvaćenog od Nadzora i izvršava ga korak po korak.
"""
import asyncio

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour

import protocol as P
from strips import is_wait, strips, wait_target

MAX_REPLANS = 5
REPLY_TIMEOUT = 10     # s, čekanje odgovora Nadzora
WAIT_TIMEOUT = 45      # s, čekanje vanjskog predikata


class RecoveryAgent(Agent):
    def __init__(self, jid, password, name, ops, goal, external=(),
                 nadzor_jid=P.JID_NADZOR, trace=False, step_delay=0.0):
        super().__init__(jid, password)
        self.display_name = name
        self.ops = list(ops)
        self.goal = tuple(goal)
        self.external = frozenset(external)
        self.nadzor_jid = nadzor_jid
        self.trace = trace
        self.step_delay = step_delay
        self.db_event = asyncio.Event()   # stigla je DB_READY ili DB_UNREACHABLE
        self.db_unreachable = False
        self.goal_result = asyncio.Event()
        self.goal_lost = asyncio.Event()
        self.done = asyncio.Event()
        self.go = asyncio.Event()         # main.py ga postavlja kad su svi agenti spojeni

    def log(self, text):
        P.log(f"{self.display_name} {text}")

    class Obavijesti(CyclicBehaviour):
        """Asinkrone obavijesti Nadzora (DB_READY / DB_UNREACHABLE / GOAL_RESULT)."""

        async def run(self):
            m = await self.receive(timeout=1)
            if m is None:
                return
            P.log_received(self, m)
            mtype, _ = P.parse(m)
            if mtype == P.GOAL_RESULT:
                self.agent.goal_result.set()
                return
            if mtype == P.LOCAL_GOAL_LOST:
                self.agent.goal_lost.set()
                return
            if mtype == P.DB_UNREACHABLE:
                self.agent.db_unreachable = True
            self.agent.db_event.set()

    class Oporavak(OneShotBehaviour):
        """Petlja planiraj -> izvršavaj -> (replaniraj). Template: samo odgovori Nadzora."""

        async def ask(self, mtype, **body):
            a = self.agent
            await P.send(self, P.msg(a.nadzor_jid, mtype, **body))
            m = await self.receive(timeout=REPLY_TIMEOUT)
            if m is None:
                return None, {}
            P.log_received(self, m)
            return P.parse(m)

        def plan(self, state, n):
            a = self.agent
            trace = (lambda line: a.log(f"TRACE {line}")) if a.trace else None
            plan = strips(state, a.goal, a.ops, external=a.external, trace=trace)
            label = "PLAN" if n == 0 else f"REPLAN #{n}"
            a.log(f"{label} iz stanja {P.fmt_state(state)}")
            a.log(f"{label}: " + ("None (cilj nije ostvariv)" if plan is None
                                  else "[" + ", ".join(plan) + "]"))
            return plan

        async def recover(self):
            """Vrati (uspjeh, razlog)."""
            a = self.agent
            for n in range(MAX_REPLANS + 1):
                mtype, body = await self.ask(P.GET_STATE)
                if mtype != P.STATE:
                    return False, "Nadzor ne odgovara na GET_STATE"
                plan = self.plan(set(body["state"]), n)
                if plan is None:
                    return False, f"STRIPS nije našao plan za cilj {list(a.goal)}"
                replan = False
                for step in plan:
                    if is_wait(step):
                        a.log(f"ČEKAM vanjski predikat {wait_target(step)}")
                        try:
                            await asyncio.wait_for(a.db_event.wait(), WAIT_TIMEOUT)
                        except asyncio.TimeoutError:
                            return False, f"istek čekanja na {wait_target(step)}"
                        if a.db_unreachable:
                            return False, "baza nije dostupna (DB_UNREACHABLE)"
                        a.db_event.clear()
                        # stanje se u međuvremenu promijenilo => uvijek replaniraj
                        a.log("čekanje gotovo, replaniram iz svježeg stanja")
                        replan = True
                        break
                    if a.step_delay:
                        await asyncio.sleep(a.step_delay)   # simulirano trajanje akcije
                    mtype, body = await self.ask(P.ACTION_REQUEST,
                                                 agent=a.display_name, action=step)
                    if mtype == P.ACTION_CONFIRM:
                        a.log(f"IZVRŠENO {step}")
                    elif mtype == P.ACTION_REJECT:
                        a.log(f"ODBIJENO {step}: {body.get('reason')}"
                              f" (nedostaje {body.get('missing')}); replaniram")
                        replan = True
                        break
                    else:
                        return False, f"Nadzor ne odgovara na ACTION_REQUEST {step}"
                if not replan:
                    return True, ""
            return False, f"prekoračen broj replaniranja ({MAX_REPLANS})"

        async def run(self):
            a = self.agent
            await a.go.wait()   # da se nijedna obavijest ne izgubi prije spajanja svih agenata
            a.log(f"LOKALNI CILJ: {list(a.goal)}"
                  + (f", vanjski predikati: {sorted(a.external)}" if a.external else ""))
            while True:
                a.goal_lost.clear()
                ok, reason = await self.recover()
                if ok:
                    a.log("lokalni cilj postignut")
                    await P.send(self, P.msg(a.nadzor_jid, P.LOCAL_GOAL_DONE,
                                             agent=a.display_name))
                else:
                    a.log(f"ODUSTAJEM: {reason}")
                    await P.send(self, P.msg(a.nadzor_jid, P.PLAN_FAILED,
                                             agent=a.display_name, reason=reason))
                await P.send(self, P.msg(a.nadzor_jid, P.GOAL_CHECK, agent=a.display_name))
                res = asyncio.ensure_future(a.goal_result.wait())
                lost = asyncio.ensure_future(a.goal_lost.wait())
                done, pending = await asyncio.wait({res, lost}, timeout=WAIT_TIMEOUT,
                                                   return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                if not done:
                    a.log("nema GOAL_RESULT od Nadzora")
                if ok and a.goal_lost.is_set() and not a.goal_result.is_set():
                    a.log("Nadzor javlja da lokalni cilj više ne vrijedi -> ponovni oporavak")
                    continue
                break
            a.done.set()

    async def setup(self):
        self.add_behaviour(self.Obavijesti(),
                           P.template(P.DB_READY, P.DB_UNREACHABLE, P.GOAL_RESULT, P.LOCAL_GOAL_LOST))
        self.add_behaviour(self.Oporavak(),
                           P.template(P.STATE, P.ACTION_CONFIRM, P.ACTION_REJECT))
