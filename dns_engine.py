from dataclasses import dataclass
import time
import dns.resolver
import dns.reversename
import dns.dnssec
import dns.name

RECORD_TYPES = ["A","AAAA","CNAME","MX","TXT","NS","SOA","SRV","CAA","PTR"]

@dataclass
class Result:
    domain: str
    record_type: str
    values: list[str]
    ttl: int | None
    latency_ms: float
    error: str | None = None

class DNSEngine:
    def __init__(self, timeout=3.0, lifetime=5.0, nameserver=None):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = lifetime
        if nameserver:
            self.resolver.nameservers = [nameserver]
        self.request_count = 0

    @property
    def server(self):
        return ", ".join(self.resolver.nameservers)

    def query(self, domain, rtype="A"):
        domain = domain.strip().rstrip(".")
        start = time.perf_counter()
        self.request_count += 1
        try:
            answer = self.resolver.resolve(domain, rtype)
            values = [r.to_text() for r in answer]
            ttl = answer.rrset.ttl if answer.rrset else None
            return Result(domain, rtype, values, ttl,
                          (time.perf_counter()-start)*1000)
        except Exception as exc:
            return Result(domain, rtype, [], None,
                          (time.perf_counter()-start)*1000, str(exc))

    def reverse(self, ip):
        try:
            name = str(dns.reversename.from_address(ip))
            return self.query(name, "PTR")
        except Exception as exc:
            return Result(ip, "PTR", [], None, 0, str(exc))

    def inspect(self, domain):
        return {t: self.query(domain, t) for t in RECORD_TYPES if t != "PTR"}

    def dnssec(self, domain):
        r = dns.resolver.Resolver()
        start = time.perf_counter()
        try:
            r.resolve(domain, "DNSKEY")
            return True, (time.perf_counter()-start)*1000, "DNSKEY موجود است (این فقط وجود کلید را نشان می‌دهد، نه اعتبارسنجی کامل زنجیره‌ی امضا)"
        except Exception as exc:
            return False, (time.perf_counter()-start)*1000, str(exc)
