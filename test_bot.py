import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

os.environ.setdefault("HELIUS_RPC_URL", "https://test.rpc.url")
os.environ.setdefault("STARTING_BALANCE_USD", "1000")
os.environ.setdefault("MIN_PROFIT_PCT", "0.5")

from config import Config
from paper_trader import (
    load_state, save_state, execute_paper_trade,
    check_circuit_breaker, reset_circuit_breaker,
    process_opportunities, get_summary, record_learning, _default_state
)

SAMPLE_OPPORTUNITIES = [
    {
        "pair": "SOL/USDC", "buy_dex": "Orca", "sell_dex": "Raydium",
        "buy_price": 179.50, "sell_price": 180.20,
        "trade_size_usd": 100.0, "net_spread_pct": 1.0,
    },
    {
        "pair": "JUP/USDC", "buy_dex": "Meteora", "sell_dex": "Orca",
        "buy_price": 0.85, "sell_price": 0.86,
        "trade_size_usd": 50.0, "net_spread_pct": 1.15,
    },
]


def test_config():
    print("\n🧪 Config validation...")
    from config import validate_config
    validate_config()
    assert Config.STARTING_BALANCE_USD > 0
    assert len(Config.PAIRS) > 0
    print("   ✅ Config OK")


def test_state():
    print("\n🧪 State persistence...")
    import paper_trader as pt
    orig = pt.STATE_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp = f.name
    pt.STATE_PATH = temp
    try:
        state = load_state()
        assert state["balance_usd"] == Config.STARTING_BALANCE_USD
        print("   ✅ Fresh state OK")
        
        state["balance_usd"] = 1500.0
        save_state(state)
        assert load_state()["balance_usd"] == 1500.0
        print("   ✅ Save/reload OK")
        
        with open(temp, 'w') as f:
            f.write("")
        assert load_state()["balance_usd"] == Config.STARTING_BALANCE_USD
        print("   ✅ Empty file handled")
        
        with open(temp, 'w') as f:
            f.write("not json{{{")
        assert load_state()["balance_usd"] == Config.STARTING_BALANCE_USD
        print("   ✅ Corrupted file handled")
    finally:
        pt.STATE_PATH = orig
        os.unlink(temp)
    print("   ✅ State passed")


def test_trade():
    print("\n🧪 Paper trade execution...")
    import paper_trader as pt
    orig = pt.STATE_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(_default_state(), f)
        temp = f.name
    pt.STATE_PATH = temp
    try:
        state = load_state()
        trade = execute_paper_trade(state, SAMPLE_OPPORTUNITIES[0])
        assert trade is not None
        print(f"   ✅ Trade: {trade['status']}, ${trade['profit_usd']}")
        
        state["balance_usd"] = 0.5
        assert execute_paper_trade(state, SAMPLE_OPPORTUNITIES[0]) is None
        print("   ✅ Low balance skipped")
    finally:
        pt.STATE_PATH = orig
        os.unlink(temp)
    print("   ✅ Trade passed")


def test_breaker():
    print("\n🧪 Circuit breaker...")
    import paper_trader as pt
    orig = pt.STATE_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(_default_state(), f)
        temp = f.name
    pt.STATE_PATH = temp
    try:
        state = load_state()
        assert not check_circuit_breaker(state)
        print("   ✅ Not tripped initially")
        
        state["consecutive_losses"] = 3
        assert check_circuit_breaker(state)
        print("   ✅ Trips after 3 losses")
        
        reset_circuit_breaker(state)
        assert not state["circuit_breaker_tripped"]
        print("   ✅ Reset works")
    finally:
        pt.STATE_PATH = orig
        os.unlink(temp)
    print("   ✅ Breaker passed")


def test_batch():
    print("\n🧪 Batch processing...")
    import paper_trader as pt
    orig = pt.STATE_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(_default_state(), f)
        temp = f.name
    pt.STATE_PATH = temp
    try:
        state, executed = process_opportunities(SAMPLE_OPPORTUNITIES)
        assert isinstance(executed, list)
        print(f"   ✅ Processed {len(SAMPLE_OPPORTUNITIES)} opps, {len(executed)} executed")
        summary = get_summary(state)
        print(f"   ✅ Summary: ${summary['balance_usd']:.2f}, ROI={summary['roi_pct']:.3f}%")
    finally:
        pt.STATE_PATH = orig
        os.unlink(temp)
    print("   ✅ Batch passed")


def test_learn():
    print("\n🧪 Learning memory...")
    import paper_trader as pt
    orig = pt.STATE_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(_default_state(), f)
        temp = f.name
    pt.STATE_PATH = temp
    try:
        state = load_state()
        record_learning(state, "Test note")
        assert len(state["learnings"]) == 1
        print("   ✅ Learning recorded")
        for i in range(60):
            record_learning(state, f"Note {i}")
        assert len(state["learnings"]) <= 50
        print("   ✅ Limit enforced (max 50)")
    finally:
        pt.STATE_PATH = orig
        os.unlink(temp)
    print("   ✅ Learnings passed")


def run_all():
    print("=" * 60)
    print("🧪 ARB BOT TEST SUITE")
    print("=" * 60)
    tests = [
        ("Config", test_config), ("State", test_state),
        ("Trade", test_trade), ("Breaker", test_breaker),
        ("Batch", test_batch), ("Learnings", test_learn),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Bot is ready.")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
