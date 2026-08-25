import json
with open("chaos/chaos-events.jsonl", "a") as f:
    f.write(json.dumps({"ts": 1000, "iso": "2026-08-25T00:00:00", "action": "kill", "region": "a", "mode": "netblock"}) + "\n")
with open("reports/drill-1-nodr.jsonl", "w") as f:
    f.write(json.dumps({"ts": 999, "ok": True}) + "\n")
    f.write(json.dumps({"ts": 1001, "ok": False, "served_by": "a"}) + "\n")
