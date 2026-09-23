from dns_ai.parser import domain, ip, record_type

def test_parser():
    assert domain("check example.com") == "example.com"
    assert ip("reverse 8.8.8.8") == "8.8.8.8"
    assert record_type("example.com MX") == "MX"
