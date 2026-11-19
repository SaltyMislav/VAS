"""AgentNadzor: jedini drži i mijenja službeno stanje okoline."""
import asyncio

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

import protocol as P
from domain import AGENT_BAZA, ALL_OPS, G, OWNER


class NadzorAgent(Agent):
    def __init__(self, jid, password, initial_state, app_jid=P.JID_APP,
                 expected_agents=(AGENT_BAZA, "AgentAplikacija")):
        super().__init__(jid, password)
        self.state = frozenset(initial_state)
        self.app_jid = app_jid
        self.expected_agents = set(expected_agents)
        self.outcomes = {}            # agent -> LOCAL_GOAL_DONE | PLAN_FAILED
        self.result = None            # {"satisfied": bool, "missing": [...]}
        self.pending_goal_checks = [] # GOAL_CHECK upiti pristigli prije konačnog ishoda
        self.finished = asyncio.Event()

    def log(self, text):
        P.log(f"{P.agent_name(self.jid)} {text}")

    def goal_status(self):
        missing = sorted(G - self.state)
        return {"satisfied": not missing, "missing": missing}

    class Obrada(CyclicBehaviour):
        """Jedan ciklički behaviour obrađuje poruke slijedno => akcije su atomarne."""

        async def run(self):
            m = await self.receive(timeout=1)
            if m is None:
                return
            P.log_received(self, m)
            mtype, body = P.parse(m)
            handler = getattr(self, f"on_{mtype}", None)
            if handler is None:
                self.agent.log(f"nepoznat tip poruke: {mtype}")
                return
            await handler(m, body)

        async def on_GET_STATE(self, m, body):
            await P.send(self, P.reply(m, P.STATE, state=sorted(self.agent.state)))

        async def on_ACTION_REQUEST(self, m, body):
            a = self.agent
            who, action = body.get("agent"), body.get("action")
            op = ALL_OPS.get(action)
            reason, missing = None, []
            if op is None:
                reason = f"nepoznata akcija '{action}'"
            elif P.agent_name(m.sender) != who:
                reason = f"pošiljatelj {P.agent_name(m.sender)} se predstavlja kao {who}"
            elif OWNER[action] != who:
                reason = f"akcija pripada agentu {OWNER[action]}, a ne {who}"
            elif not op.applicable(a.state):
                missing = [p for p in op.pre if p not in a.state]
                reason = "preduvjeti nisu ispunjeni"
            if reason:
                # stanje se NE mijenja
                a.log(f"ODBIJENO {action} ({who}): {reason}"
                      + (f"; nedostaje {missing}" if missing else ""))
                await P.send(self, P.reply(m, P.ACTION_REJECT, action=action, reason=reason,
                                           missing=missing, state=sorted(a.state)))
                return
            was_ready = "BazaSpremna" in a.state
            a.state = op.apply(a.state)
            a.log(f"POTVRĐENO {action} ({who}): +{sorted(op.add)} -{sorted(op.dele)}"
                  f" => {P.fmt_state(a.state)}")
            await P.send(self, P.reply(m, P.ACTION_CONFIRM, action=action, state=sorted(a.state)))
            if not was_ready and "BazaSpremna" in a.state:
                await P.send(self, P.msg(a.app_jid, P.DB_READY, state=sorted(a.state)))

        async def on_LOCAL_GOAL_DONE(self, m, body):
            await self.outcome(body.get("agent"), P.LOCAL_GOAL_DONE)

        async def on_PLAN_FAILED(self, m, body):
            who = body.get("agent")
            if who == AGENT_BAZA:
                await P.send(self, P.msg(self.agent.app_jid, P.DB_UNREACHABLE,
                                         reason=body.get("reason", "")))
            await self.outcome(who, P.PLAN_FAILED)

        async def on_GOAL_CHECK(self, m, body):
            # Konačan odgovor ima smisla tek kad oba agenta jave ishod.
            if self.agent.result is None:
                self.agent.pending_goal_checks.append(m)
            else:
                await P.send(self, P.reply(m, P.GOAL_RESULT, **self.agent.result))

        async def outcome(self, who, kind):
            a = self.agent
            a.outcomes[who] = kind
            if a.result is not None or not a.expected_agents <= set(a.outcomes):
                return
            a.result = a.goal_status()
            a.log(f"ISHODI AGENATA: {a.outcomes}")
            a.log(f"ZAVRŠNO STANJE: {P.fmt_state(a.state)}")
            if a.result["satisfied"]:
                a.log("KONAČNI REZULTAT: USPJEH (zajednički cilj G ⊆ stanje)")
            else:
                a.log("KONAČNI REZULTAT: NEOSTVARIVO: nedostaje "
                      + P.fmt_state(a.result["missing"]))
            for pending in a.pending_goal_checks:
                await P.send(self, P.reply(pending, P.GOAL_RESULT, **a.result))
            a.pending_goal_checks.clear()
            a.finished.set()

    async def setup(self):
        self.log(f"POČETNO STANJE: {P.fmt_state(self.state)}")
        self.log(f"ZAJEDNIČKI CILJ G: {P.fmt_state(G)}")
        self.add_behaviour(self.Obrada())
