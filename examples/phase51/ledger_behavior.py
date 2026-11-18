"""Check a declarative ledger contract against already approved whole-program observations."""
import hashlib
import json
import re
from pathlib import Path

DECIMAL = re.compile(r"[+-]?[0-9]+\Z")
WHITESPACE = " \t\n\r\f\v"


def chunks(text, width):
    while text:
        end = text.find("\n", 0, width)
        size = end + 1 if end >= 0 else width
        yield text[:size]
        text = text[size:]


def check(model_path, observation_path, static_path):
    model = json.loads(model_path.read_bytes())
    evidence = json.loads(static_path.read_bytes())
    symbols = evidence["syntax"]["tokens"]
    calls = evidence["framing"]["calls"]
    grammar, state, replies = (model[k] for k in ("grammar", "state", "replies"))
    widths = {int(match, 0) - 1 for call in calls
              for match in re.findall(r",\s*(0x[0-9a-fA-F]+|[1-9][0-9]*)\s*,", call)}
    if (model["target_sha256"] != evidence["target_sha256"] or widths != {grammar["chunk_bytes"]}
            or not {*grammar["operands"], replies["invalid"].strip(), replies["denied"].strip()} <= set(symbols)):
        raise ValueError("model lacks matching static evidence")
    observations = json.loads(observation_path.read_bytes())
    for case in observations:
        if not case["stdin"].isascii() and case["stdin"]:
            raise ValueError("the public ledger model is limited to ASCII inputs")
        balance = state["initial"]
        outcome = []
        for chunk in chunks(case["stdin"], grammar["chunk_bytes"]):
            token_text = chunk.strip(WHITESPACE)
            if not token_text:
                outcome.append(replies["silent"])
                continue
            op, *args = re.split(r"[ \t\n\r\f\v]+", token_text)
            arity = grammar["operands"].get(op)
            if arity != len(args) or args and not DECIMAL.fullmatch(args[0]):
                outcome.append(replies["invalid"])
                continue
            rule = state["transitions"][op]
            if args:
                amount = int(args[0])
                if not state["amount_min"] <= amount <= state["amount_max"]:
                    outcome.append(replies["invalid"])
                    continue
                proposed = balance + amount * rule["coefficient"]
                if not state["min"] <= proposed <= state["max"]:
                    outcome.append(replies["denied"])
                    continue
                balance = proposed
            elif "assign" in rule:
                balance = rule["assign"]
            outcome.append(replies["value"].format(balance))
        if ("".join(outcome), replies["stderr"], replies["exit_code"]) != (
            case["stdout"], case["stderr"], case["code"]
        ):
            raise ValueError(f"behavior disagrees with public observation {case['name']}")
    return {"target_sha256": model["target_sha256"], "public_agreement": len(observations),
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "static_assertions": ["target identity", "96-byte fgets buffer", "observable command/error tokens"],
            "inference_requests": 0}


if __name__ == "__main__":
    receipt = check(Path("behavior.json"), Path("observations.json"), Path("behavior-static.json"))
    Path("behavior-verdict.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
