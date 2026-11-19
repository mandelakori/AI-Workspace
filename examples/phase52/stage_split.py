"""Stage the reviewed syntax split and public probes without supplying implementations."""
from pathlib import Path
import json
import shutil
import sys

from aiwork.controller import write_json

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=False)
prior = Path(".aiwork/phase51/ledger-trial").resolve()
policy = json.loads((prior/"project.json").read_bytes())
assets = Path(__file__).resolve().parent
for file in prior.iterdir():
    if file.is_file() and file.name not in ("syntax.c","project.json","tree.json"):
        shutil.copyfile(file, root/file.name)
# Review preserves enum declarations and interfaces, and adds a bounded lexical transport.
with (root/"contract.h").open("a", encoding="ascii") as header:
    header.write("""
typedef struct {char words[3][96]; int count; int invalid;} TokenStream;
TokenStream tokenize_chunk(const char *chunk);
Command validate_tokens(TokenStream stream);
""")
with (root/"main.c").open("a", encoding="ascii") as main:
    main.write("""
Command parse_chunk(const char *chunk) {
    return validate_tokens(tokenize_chunk(chunk));
}
""")
shutil.copyfile(assets/"syntax_probe.c",root/"syntax_probe.c")
nodes=policy["components"]
nodes.pop("syntax")
for name in ("framing","balance"):
    nodes[name]["timeout"]=160
    nodes[name]["interface"] += (" Use the C stream API that preserves unread bytes beyond the newline."
                                if name=="framing" else " Check the operation and amount before arithmetic.")
# A tokenizer classifies lexical boundaries only. Validation owns the command vocabulary and arity.
nodes["tokenize"]={
    "role":"implementation",
    "interface":"Write tokenize.c defining TokenStream tokenize_chunk(const char *chunk). Split at C whitespace "
    "only. Copy at most three word tokens to words, each NUL terminated. Set count to the number copied, "
    "zero for blank input. Set invalid to 1 if more than three tokens occur or a token cannot fit in 96 bytes; "
    "otherwise invalid is zero. Preserve the text of words, including signs. Do not validate command grammar.",
    "inputs":["contract.h","syntax_probe.c","tokenize-public.json"],
    "outputs":["tokenize.c"],"needs":["analysis","behavior"],
    "imports":{"analysis":["syntax.json"],"behavior":["behavior-verdict.json"]},
    "source_context":["contract.h"],"public_cases":"tokenize-public.json","timeout":160,
    "checks":[{"argv":["gcc","-std=c11","-O2","-DTOKENIZE","syntax_probe.c","tokenize.c","-o","probe"]},
              {"argv":["./probe"],"timeout":5}],
}
nodes["validation"]={
    "role":"implementation",
    "interface":"Write validation.c defining Command validate_tokens(TokenStream stream). Return SKIP for "
    "count zero; BAD for invalid or any malformed command. Words must match add, take, reset or show exactly. "
    "Show/reset need exactly one token. Add/take need exactly two tokens, the operand a complete signed "
    "decimal integer in INT_MIN..INT_MAX. Return the verb enum and integer amount; balance owns 0..1000. "
    "Reject signs without digits, suffixes and surplus tokens. The token stream is immutable.",
    "inputs":["contract.h","syntax_probe.c","validation-public.json"],
    "outputs":["validation.c"],"needs":["tokenize"],
    "imports":{"tokenize":["tokenize.c"]},"source_context":["contract.h"],
    "public_cases":"validation-public.json","timeout":160,
    "checks":[{"argv":["gcc","-std=c11","-O2","syntax_probe.c",".handoff/tokenize/tokenize.c",
                       "validation.c","-I.","-o","probe"]},{"argv":["./probe"],"timeout":5}],
}
nodes["testing"]["needs"]=["framing","tokenize","validation","balance","output"]
nodes["testing"]["checks"][0]["argv"]=["{python}","verify_public.py","test",*nodes["testing"]["needs"]]
def case(name, text, expected):
    return {"name":name,"stdin":text,"stdout":expected+"\n","stderr":"","code":0,"argv":[]}
token_cases=[
    ("empty","","0|0"),("blank"," \f\v\r\n","0|0"),("two","add +031\n","2|0|add|+031"),
    ("tabs","\t take\t-8 \f","2|0|take|-8"),("three","add 4 junk","3|0|add|4|junk"),
    ("four","add 3 x y","3|1|add|3|x"),("word","reset","1|0|reset"),
    ("boundary","?"*95,"1|0|"+"?"*95),("prefix","showmore","1|0|showmore"),
]
write_json(root/"tokenize-public.json",[case(*item) for item in token_cases])
old=json.loads((root/"syntax-public.json").read_bytes())
old += [case("reject-signed-overflow","add 2147483648","bad"),
        case("reject-negative-overflow","take -2147483649","bad"),
        case("extra-on-reset","reset now","bad"),case("digits-then-junk","add 01x","bad")]
write_json(root/"validation-public.json",old)
# Approved public commands are fixed recipes, executable only inside the existing offline image.
driver = """import json,subprocess,sys
part=sys.argv[1]
cfg=json.load(open(part+'-recipe.json'))
build=subprocess.run(cfg['build'],capture_output=True,text=True)
if build.returncode:
 print(build.stderr[-1600:]); sys.exit(1)
passed=0
for row in json.load(open(part+'-public.json')):
 observed=subprocess.run(['./probe',*row.get('argv',[])],input=row.get('stdin','').encode(),capture_output=True,timeout=4)
 actual={'stdout':observed.stdout.decode('utf-8','replace'),'stderr':observed.stderr.decode('utf-8','replace'),'code':observed.returncode}
 expected={key:row.get(key,0 if key=='code' else '') for key in actual}
 if actual==expected: passed+=1
 else: print(json.dumps({'case':row['name'],'input':row['stdin'],'argv':row.get('argv',[]),'expected':expected,'observed':actual}))
print('Public cases passed',passed)
sys.exit(0 if passed==len(json.load(open(part+'-public.json'))) else 1)
"""
(root/"component_check.py").write_text(driver,encoding="ascii")
for name in ("framing","tokenize","validation","balance"):
    node=nodes[name]
    write_json(root/f"{name}-recipe.json",{"build":node["checks"][0]["argv"]})
    node["inputs"] += ["component_check.py",f"{name}-recipe.json"]
    node["commands"]=[{"argv":["{python}","component_check.py",name],"timeout":30},
                      node["checks"][0]]
policy["max_attempts"]=3
write_json(root/"reviewed-project.json",policy)
write_json(root/"reviewed-tree.json",{"id":"reviewed-ledger","children":[
    {"id":"evidence","children":[{"component":"analysis"},{"component":"behavior"}]},
    {"id":"lexical","children":[{"component":"tokenize"},{"component":"validation"}]},
    {"id":"stateful","children":[{"component":"framing"},{"component":"balance"},{"component":"output"}]},
    {"id":"release","children":[{"component":"testing"},{"component":"integration"}]},
]})
for mode in ("source","tools"):
    variant=json.loads(json.dumps(policy))
    if mode=="tools":
        for name in ("framing","tokenize","validation","balance"):
            variant["components"][name].pop("source_context")
    write_json(root/f"{mode}-project.json",variant)
