import sys

from fastapi.testclient import TestClient

from src.api.routes import app

client = TestClient(app)

print("=== 1. Testing Live Quotes ===")
for sym in ["AAPL", "RELIANCE", "CANBK", "NVDA", "TCS"]:
    r = client.get(f"/api/v1/quote/{sym}")
    assert r.status_code == 200, f"Failed {sym}: {r.status_code} {r.text}"
    data = r.json()
    print(
        f"OK Quote {sym:10} -> {data['symbol']:12} | Price: {data['price']} | Name: {data['name'][:25]}"
    )

print("\n=== 2. Testing DCF Endpoints ===")
for sym in ["AAPL", "RELIANCE", "NVDA"]:
    r = client.get(f"/api/v1/dcf/{sym}")
    assert r.status_code == 200, f"Failed DCF {sym}: {r.status_code} {r.text}"
    d = r.json()
    print(
        f"OK DCF {sym:10} -> Implied Fair Value: {d['currency']}{d['fair_value_per_share']:,.2f} vs CMP: {d['currency']}{d['cmp']:,.2f} ({d['upside_pct']:+.1f}%) | WACC: {d['wacc']}% | Rev: {d['currency']}{d['base_revenue']:,.1f} {d['unit']}"
    )

print("\n=== 3. Testing Ratios Endpoints ===")
for sym in ["AAPL", "RELIANCE", "CANBK"]:
    r = client.get(f"/api/v1/ratios/{sym}")
    assert r.status_code == 200, f"Failed Ratios {sym}: {r.status_code} {r.text}"
    d = r.json()
    print(
        f"OK Ratios {sym:10} -> P/E: {d['pe']} | P/B: {d['pb']} | ROE: {d['roe']} | D/E: {d['de']}"
    )

print("\n=== 4. Testing Unidentifiable Ticker Error Handling ===")
fake = "FAKEUNKNOWN999"
for path in [f"/api/v1/quote/{fake}", f"/api/v1/dcf/{fake}", f"/api/v1/ratios/{fake}"]:
    r = client.get(path)
    assert r.status_code == 404, f"Expected 404 for {path}, got {r.status_code}"
    detail = r.json().get("detail", "")
    assert "Unable to identify company or ticker" in detail, f"Wrong error detail: {detail}"
    print(f"OK 404 on {path:30} -> Detail: {detail}")

print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
