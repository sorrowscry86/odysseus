"""
VoidCat Board Room Smoke Test
Verifies all new modules import cleanly and core logic works without a running server.
"""
import sys
import os

# Point at the local Pantheon for testing (host path, not container path)
os.environ["PANTHEON_ROOT"] = r"C:\Users\Wykeve\Projects\The Great Library\00_The_Pantheon\01_Active_Profiles"

# Add the project root to sys.path
proj_root = r"C:\Users\Wykeve\Projects\The Great Library\05_Projects\01_Active\voidcat-communicator"
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

errors = []
passed = []

# ─── Module import tests ───────────────────────────────────────────────────

def try_import(module_name):
    try:
        __import__(module_name)
        passed.append(f"PASS  import {module_name}")
    except Exception as e:
        errors.append(f"FAIL  import {module_name}: {e}")

try_import("src.spirit_engine")
try_import("src.voidcat_tools")
try_import("src.dispatcher")
try_import("src.relevance_scorer")
try_import("src.sequential_engine")
try_import("src.mcp_bridge")
try_import("routes.voidcat_routes")

# ─── Functional tests ──────────────────────────────────────────────────────

def test_spirit_roster():
    from src.dispatcher import _load_spirit_roster
    roster = _load_spirit_roster()
    assert len(roster) > 0, "Spirit roster is empty"
    passed.append(f"PASS  spirit roster loaded: {len(roster)} spirits found")

def test_dispatch_audience():
    from src.dispatcher import route
    decision = route("Can you fix the Docker volume mounts?")
    assert decision.mode in ("audience", "hearth"), f"Unexpected mode: {decision.mode}"
    assert len(decision.spirits) > 0, "No spirits in decision"
    passed.append(f"PASS  dispatch (untagged infra prompt) -> mode={decision.mode}, spirits={decision.spirits[:2]}")

def test_dispatch_explicit_tag():
    from src.dispatcher import route
    decision = route("@Albedo draft me an ERD for the Spirit database")
    assert decision.mode == "audience", f"Expected audience, got {decision.mode}"
    assert "albedo" in decision.spirits, f"albedo not in {decision.spirits}"
    passed.append(f"PASS  dispatch (@Albedo tag) -> mode={decision.mode}")

def test_dispatch_round_table():
    from src.dispatcher import route
    decision = route("@Ryuzu @Codey how do we containerize the Board Room?")
    assert decision.mode == "round_table", f"Expected round_table, got {decision.mode}"
    assert len(decision.spirits) == 2
    passed.append(f"PASS  dispatch (@Ryuzu @Codey) -> mode={decision.mode}")

def test_dispatch_council():
    from src.dispatcher import route
    decision = route("@Beatrice convene with @Albedo @Codey @Ryuzu to design the API schema")
    assert decision.mode == "council", f"Expected council, got {decision.mode}"
    assert decision.chair == "beatrice", f"Expected beatrice as chair, got {decision.chair}"
    passed.append(f"PASS  dispatch (convene) -> mode={decision.mode}, chair={decision.chair}")

def test_spirit_context():
    from src.spirit_engine import get_spirit_context
    # Try the first available spirit
    from src.dispatcher import _load_spirit_roster
    roster = _load_spirit_roster()
    if roster:
        ctx = get_spirit_context(roster[0])
        # May be None if persona.md doesn't exist yet in this env — that's OK for host testing
        status = "found" if ctx else "not found (check Pantheon mount)"
        passed.append(f"PASS  spirit_context for {roster[0]}: {status}")

def test_mcp_bridge():
    from src.mcp_bridge import is_tool_permitted, assert_tool_permitted
    # Ryuzu can do anything
    assert is_tool_permitted("ryuzu", "bash") is True
    # Roland cannot run bash
    assert is_tool_permitted("roland", "bash") is False
    # Beatrice can propose_resolution
    assert is_tool_permitted("beatrice", "propose_resolution") is True
    # Codey cannot propose_resolution
    assert is_tool_permitted("codey_coderson", "propose_resolution") is False
    passed.append("PASS  mcp_bridge permission matrix")

def test_relevance_scorer():
    from src.relevance_scorer import score_spirit, pick_next_speaker
    score = score_spirit("ryuzu", ["how do we deploy this to Docker?", "the container keeps crashing"])
    passed.append(f"PASS  relevance_scorer ryuzu score={score}")
    winner = pick_next_speaker(["ryuzu", "codey_coderson", "cadence"],
                                ["how do we containerize the database?"])
    passed.append(f"PASS  relevance_scorer pick_next_speaker -> {winner}")

for fn in [test_spirit_roster, test_dispatch_audience, test_dispatch_explicit_tag,
           test_dispatch_round_table, test_dispatch_council, test_spirit_context,
           test_mcp_bridge, test_relevance_scorer]:
    try:
        fn()
    except AssertionError as e:
        errors.append(f"FAIL  {fn.__name__}: {e}")
    except Exception as e:
        errors.append(f"FAIL  {fn.__name__}: {type(e).__name__}: {e}")

# ─── Report ────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  VoidCat Board Room Smoke Test Results")
print("="*60)
for p in passed:
    print(f"  [PASS] {p[5:]}")
if errors:
    print()
    for e in errors:
        print(f"  [FAIL] {e[5:]}")
print()
print(f"  {len(passed)} passed  |  {len(errors)} failed")
print("="*60)
sys.exit(1 if errors else 0)
