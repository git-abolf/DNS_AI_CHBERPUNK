import json
from datetime import datetime, timezone

def export_json(path, domain, results):
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "records": {}
    }
    for rtype, r in results.items():
        data["records"][rtype] = {
            "values": r.values,
            "ttl": r.ttl,
            "latency_ms": round(r.latency_ms, 2),
            "error": r.error
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
