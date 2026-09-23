import sys, time, threading, platform, datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QFileDialog
)
from .dns_engine import DNSEngine, RECORD_TYPES
from .parser import domain, ip, record_type
from .reports import export_json
from .zone import ZoneBuilder
from .voice import Voice
from .ui import CoreWidget, HudPanel, StatusRow, GlowBar, label

STYLE = """
QMainWindow, QWidget { background:#050807; color:#b9ffe5; }
QLabel { color:#73ffc5; }
QLineEdit, QTextEdit, QComboBox {
 background:#07110e; border:1px solid #00c982; color:#d7fff0;
 padding:8px; font-family:Consolas;
}
QComboBox QAbstractItemView {
 background:#07110e; color:#d7fff0; selection-background-color:#0c3024;
}
QPushButton {
 background:#071a14; color:#67ffc0; border:1px solid #00e892;
 padding:9px 14px; font-family:Consolas; font-weight:bold;
}
QPushButton:hover { background:#0c3024; }
QTextEdit { font-family:Consolas; }
"""

MAX_LATENCY_SCALE_MS = 250.0  # bar fills fully at/above this latency


class Main(QMainWindow):
    voice_result = Signal(str)
    voice_error = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DNS AI // CYBERPUNK COMMAND CENTER")
        self.resize(1300, 800)
        self.setStyleSheet(STYLE)
        self.engine = DNSEngine()
        self.voice = Voice()
        self.last_domain = None

        # live session stats (real data, not decorative)
        self.stats = {"queries": 0, "success": 0, "latency_sum": 0.0}

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(16, 14, 16, 14)
        main.setSpacing(12)

        # ---- header ------------------------------------------------
        header = QHBoxLayout()
        title = label("◉  D N S   A I", 22, "#8bfff0")
        subtitle = label("AI DNS ASSISTANT  //  LISTENING  //  SPEAKING  //  EXECUTING", 10, "#49f6ff")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(subtitle)
        main.addLayout(header)

        # ---- body: left / center / right ---------------------------
        body = QHBoxLayout()
        body.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(14)

        # One continuous HUD panel holding all left-side sections,
        # matching the reference (single frame, multiple inner sections).
        left_panel = HudPanel()
        sys_section = left_panel.add_section("SYSTEM STATUS")
        self.row_engine = StatusRow("DNS ENGINE", "ONLINE", icon="server")
        self.row_resolver = StatusRow("DNS RESOLVER", "READY", icon="speech")
        self.row_voice = StatusRow("VOICE (SPEECH)", "READY", icon="mic")
        self.row_ai = StatusRow("AI COMMAND", "READY", icon="ai")
        for r in (self.row_engine, self.row_resolver, self.row_voice, self.row_ai):
            sys_section.addWidget(r)

        env_section = left_panel.add_section("ENVIRONMENT")
        self.row_server = StatusRow("DNS SERVER", self.engine.server, icon="server")
        self.row_platform = StatusRow("PLATFORM", platform.system(), icon="platform")
        self.row_time = StatusRow("LOCAL TIME", datetime.datetime.now().strftime("%H:%M:%S"), icon="clock")
        for r in (self.row_server, self.row_platform, self.row_time):
            env_section.addWidget(r)

        stats_section = left_panel.add_section("SESSION STATS")
        self.bar_queries = GlowBar("QUERIES RUN")
        self.bar_latency = GlowBar("AVG LATENCY")
        self.bar_success = GlowBar("SUCCESS RATE")
        for bar in (self.bar_queries, self.bar_latency, self.bar_success):
            stats_section.addWidget(bar)
        self._refresh_stats()

        left.addWidget(left_panel)
        left.addStretch()

        clock = QTimer(self)
        clock.timeout.connect(self._tick_clock)
        clock.start(1000)

        center = QVBoxLayout()
        self.core = CoreWidget()
        center.addWidget(self.core, 1)
        last_action_panel = HudPanel()
        la_section = last_action_panel.add_section("LAST ACTION")
        la_row = QHBoxLayout()
        prompt = label(">_", 12, "#49f6ff")
        prompt.setFixedWidth(24)
        self.core_info = label("READY // WAITING FOR YOUR COMMAND", 10, "#79e6cf")
        la_row.addWidget(prompt)
        la_row.addWidget(self.core_info, 1)
        la_section.addLayout(la_row)
        center.addWidget(last_action_panel)

        right = QVBoxLayout()
        right.setSpacing(14)

        ops_panel = HudPanel()
        ops_section = ops_panel.add_section("DNS OPERATIONS")
        self.types = QComboBox()
        self.types.addItems(RECORD_TYPES)
        ops_section.addWidget(self.types)
        for text, fn in [
            ("QUERY", self.query), ("FULL INSPECT", self.inspect),
            ("REVERSE DNS", self.reverse), ("DNSSEC CHECK", self.dnssec),
            ("BUILD ZONE", self.zone), ("EXPORT JSON", self.report)
        ]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            ops_section.addWidget(b)
        right.addWidget(ops_panel)
        right.addStretch()

        body.addLayout(left, 1)
        body.addLayout(center, 2)
        body.addLayout(right, 1)
        main.addLayout(body, 1)

        # ---- command row --------------------------------------------
        cmd_panel = HudPanel()
        cmd_section = cmd_panel.add_section("COMMAND CENTER")
        row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setPlaceholderText("مثال: بررسی DNS example.com یا Reverse DNS برای 8.8.8.8")
        run = QPushButton("EXECUTE")
        run.clicked.connect(self.command_run)
        mic = QPushButton("🎤 VOICE")
        mic.clicked.connect(self.listen)
        row.addWidget(self.command, 1)
        row.addWidget(run)
        row.addWidget(mic)
        cmd_section.addLayout(row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.setStyleSheet("border:1px solid #0e5a49; background:#03100c;")
        cmd_section.addWidget(self.log)
        main.addWidget(cmd_panel)

        self.voice_result.connect(self.on_voice_result)
        self.voice_error.connect(self.on_voice_error)

        self.write("DNS AI ONLINE // ONLY DNS OPERATIONS")

    # ---- helpers -------------------------------------------------
    def _tick_clock(self):
        self.row_time.set_state(datetime.datetime.now().strftime("%H:%M:%S"))

    def _refresh_stats(self):
        q = self.stats["queries"]
        s = self.stats["success"]
        avg_ms = (self.stats["latency_sum"] / q) if q else 0.0
        success_pct = (s / q * 100.0) if q else 0.0
        latency_pct = min(100.0, (avg_ms / MAX_LATENCY_SCALE_MS) * 100.0)
        queries_pct = min(100.0, q * 5.0)  # fills up over ~20 queries

        self.bar_queries.set_value(queries_pct, f"{q}")
        self.bar_latency.set_value(latency_pct, f"{avg_ms:.0f} ms")
        self.bar_success.set_value(success_pct, f"{success_pct:.0f}%")

    def _record(self, r):
        self.stats["queries"] += 1
        if not r.error:
            self.stats["success"] += 1
        self.stats["latency_sum"] += r.latency_ms
        self._refresh_stats()

    def write(self, text):
        self.log.append(text)

    def get_domain(self):
        d = domain(self.command.text())
        if not d:
            self.write("ERROR // DOMAIN NOT FOUND")
        return d

    # ---- DNS actions -----------------------------------------------
    def query(self):
        d = self.get_domain()
        if not d: return
        t = self.types.currentText() or record_type(self.command.text())
        self.core_info.setText(f"QUERYING // {d} // {t}")
        self.core.set_status(f"QUERY // {t}")
        r = self.engine.query(d, t)
        self.last_domain = d
        self._record(r)
        self.write(f"[{t}] {d} // {r.latency_ms:.1f} ms // TTL={r.ttl}")
        if r.error: self.write("ERROR // " + r.error)
        for v in r.values: self.write("  → " + v)
        self.core_info.setText(f"ONLINE // {d} // {t} // {r.latency_ms:.1f}ms")
        self.core.set_status("CORE ONLINE")

    def inspect(self):
        d = self.get_domain()
        if not d: return
        self.core_info.setText(f"FULL INSPECT // {d}")
        self.core.set_status("FULL INSPECT")
        results = self.engine.inspect(d)
        self.last_domain = d
        for t, r in results.items():
            state = "OK" if not r.error else "ERR"
            self.write(f"{state} // {t} // TTL={r.ttl} // {r.latency_ms:.1f}ms")
            for v in r.values: self.write("  → " + v)
            self._record(r)
        self.core_info.setText(f"INSPECT COMPLETE // {d}")
        self.core.set_status("CORE ONLINE")

    def reverse(self):
        address = ip(self.command.text())
        if not address:
            self.write("ERROR // IP NOT FOUND"); return
        self.core.set_status("REVERSE DNS")
        r = self.engine.reverse(address)
        self._record(r)
        self.write(f"[PTR] {address} // {r.latency_ms:.1f} ms")
        if r.error: self.write("ERROR // " + r.error)
        for v in r.values: self.write("  → " + v)
        self.core.set_status("CORE ONLINE")

    def dnssec(self):
        d = self.get_domain()
        if not d: return
        self.core.set_status("DNSSEC CHECK")
        ok, ms, msg = self.engine.dnssec(d)
        self.write(f"DNSSEC // {d} // {'DNSKEY DETECTED' if ok else 'NOT CONFIRMED'} // {ms:.1f}ms")
        self.write(msg)
        self.core.set_status("CORE ONLINE")

    def zone(self):
        d = self.get_domain() or "example.com"
        path, _ = QFileDialog.getSaveFileName(self, "Save Zone", f"{d}.zone", "Zone (*.zone)")
        if not path: return
        z = ZoneBuilder(d)
        z.add("@", "SOA", f"ns1.{d}. hostmaster.{d}. 1 3600 600 604800 3600")
        z.add("@", "NS", f"ns1.{d}.")
        z.add("@", "NS", f"ns2.{d}.")
        z.add("www", "A", "192.0.2.10")
        open(path, "w", encoding="utf-8").write(z.render())
        self.write("ZONE CREATED // " + path)

    def report(self):
        d = self.get_domain()
        if not d: return
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", f"{d}_dns.json", "JSON (*.json)")
        if not path: return
        export_json(path, d, self.engine.inspect(d))
        self.write("REPORT EXPORTED // " + path)

    def command_run(self):
        text = self.command.text()
        if "reverse" in text.lower() or "معکوس" in text or "برعکس" in text:
            self.reverse()
        elif "inspect" in text.lower() or "بررسی کامل" in text:
            self.inspect()
        elif "dnssec" in text.lower():
            self.dnssec()
        elif "zone" in text.lower() or "زون" in text:
            self.zone()
        else:
            t = record_type(text)
            self.types.setCurrentText(t)
            self.query()

    def listen(self):
        # Runs on a background thread: only does I/O (microphone capture +
        # speech recognition), never touches widgets directly. Results are
        # sent back via Qt signals, which Qt auto-delivers on the main/UI
        # thread (queued connection), so anything the slot does — including
        # opening a QFileDialog from command_run() for BUILD ZONE / EXPORT
        # JSON — is safe.
        self.core_info.setText("LISTENING // SPEAK NOW")
        self.core.set_status("LISTENING")
        self.row_voice.set_state("LISTENING")
        def work():
            try:
                text = self.voice.listen()
                self.voice_result.emit(text)
            except Exception as e:
                self.voice_error.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def on_voice_result(self, text):
        self.command.setText(text)
        self.core_info.setText("VOICE RECEIVED // EXECUTING")
        self.row_voice.set_state("READY")
        self.command_run()
        self.voice.speak("عملیات DNS انجام شد")

    def on_voice_error(self, msg):
        self.write("VOICE ERROR // " + msg)
        self.core_info.setText("VOICE ERROR")
        self.core.set_status("CORE ONLINE")
        self.row_voice.set_state("ERROR", ok=False)

def main():
    app = QApplication(sys.argv)
    w = Main()
    w.show()
    sys.exit(app.exec())
