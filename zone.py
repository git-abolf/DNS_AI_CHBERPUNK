from dataclasses import dataclass

@dataclass
class ZoneRecord:
    name: str
    rtype: str
    value: str
    ttl: int = 3600

class ZoneBuilder:
    def __init__(self, origin, ttl=3600):
        self.origin = origin.rstrip(".") + "."
        self.ttl = ttl
        self.records = []

    def add(self, name, rtype, value, ttl=None):
        self.records.append(ZoneRecord(name, rtype, value, ttl or self.ttl))

    def render(self):
        lines = [f"$ORIGIN {self.origin}", f"$TTL {self.ttl}", ""]
        for r in self.records:
            lines.append(f"{r.name} {r.ttl} IN {r.rtype} {r.value}")
        return "\n".join(lines) + "\n"
