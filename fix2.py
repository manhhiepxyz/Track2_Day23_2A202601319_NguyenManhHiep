import json
lines = []
with open(chaos/chaos-events.jsonl, r) as f:
    for line in f:
        d = json.loads(line)
        if d.get(ts) == 1000:
            d[other_alive] = True
        lines.append(json.dumps(d))
with open(chaos/chaos-events.jsonl, w) as f:
    f.write(\n.join(lines) + \n)
