import re

TYPES = ["A","AAAA","CNAME","MX","TXT","NS","SOA","SRV","CAA","PTR"]

def domain(text):
    m = re.search(r"(?<!@)\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\b", text)
    return m.group(0) if m else None

def ip(text):
    m = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    return m.group(0) if m else None

def record_type(text):
    u = text.upper()
    for t in TYPES:
        if t in u:
            return t
    aliases = {
        "مکس":"MX", "میل":"MX", "تکست":"TXT", "نیم":"NS",
        "سی نیم":"CNAME", "سی‌نیم":"CNAME", "آ":"A", "ای":"A"
    }
    for k, v in aliases.items():
        if k in text:
            return v
    return "A"
