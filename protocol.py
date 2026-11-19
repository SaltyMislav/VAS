"""Protokol poruka: tipovi, izrada poruka i jedinstveno logiranje.

Tijelo svake poruke je JSON; tip poruke je dodatno u ``metadata["type"]``
kako bi ga SPADE ``Template`` mogao filtrirati.
"""
import json
import sys
from datetime import datetime

from spade.message import Message
from spade.template import Template

GET_STATE = "GET_STATE"
STATE = "STATE"
ACTION_REQUEST = "ACTION_REQUEST"
ACTION_CONFIRM = "ACTION_CONFIRM"
ACTION_REJECT = "ACTION_REJECT"
DB_READY = "DB_READY"
DB_UNREACHABLE = "DB_UNREACHABLE"
PLAN_FAILED = "PLAN_FAILED"
LOCAL_GOAL_DONE = "LOCAL_GOAL_DONE"
GOAL_CHECK = "GOAL_CHECK"
GOAL_RESULT = "GOAL_RESULT"

JID_NADZOR = "nadzor@localhost"
JID_BAZA = "baza@localhost"
JID_APP = "aplikacija@localhost"
PASSWORD = "tajna"

# lokalni dio JID-a -> ime agenta u ispisu
NAMES = {"nadzor": "AgentNadzor", "baza": "AgentBaza", "aplikacija": "AgentAplikacija"}


def agent_name(jid):
    node = str(jid).split("@")[0]
    return NAMES.get(node, node)


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(text):
    print(f"[{ts()}] {text}", flush=True)
    sys.stdout.flush()


def fmt_state(state):
    return "{" + ", ".join(sorted(state)) + "}"


def msg(to, mtype, **body):
    """Nova poruka zadanog tipa; tijelo je JSON od ``body``."""
    m = Message(to=str(to))
    m.set_metadata("type", mtype)
    m.body = json.dumps({"type": mtype, **body}, ensure_ascii=False)
    return m


def reply(original, mtype, **body):
    """Odgovor pošiljatelju poruke ``original``."""
    return msg(original.sender.bare, mtype, **body)


def parse(message):
    """Vrati (tip, tijelo-bez-tipa) primljene poruke."""
    body = json.loads(message.body)
    mtype = body.pop("type", None) or message.get_metadata("type")
    return mtype, body


def template(*types):
    """Template koji prihvaća bilo koji od navedenih tipova (OR)."""
    t = Template(metadata={"type": types[0]})
    for mtype in types[1:]:
        t = t | Template(metadata={"type": mtype})
    return t


def _body_str(message):
    _, body = parse(message)
    return json.dumps(body, ensure_ascii=False)


async def send(behaviour, message):
    """Pošalji i zabilježi: POŠILJATELJ -> PRIMATELJ TYPE {body}"""
    me = agent_name(behaviour.agent.jid)
    log(f"{me} -> {agent_name(message.to)} {message.get_metadata('type')} {_body_str(message)}")
    await behaviour.send(message)


def log_received(behaviour, message):
    """Zabilježi primitak: PRIMATELJ <- POŠILJATELJ TYPE {body}"""
    me = agent_name(behaviour.agent.jid)
    log(f"{me} <- {agent_name(message.sender)} {message.get_metadata('type')} {_body_str(message)}")
