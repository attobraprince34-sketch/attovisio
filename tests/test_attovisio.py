"""
Tests unitaires pour AttoVisio.
Lancez-les avec : pytest tests/ -v
"""

import pytest
import time
import os
import tempfile
import sys

# Ajout du chemin parent pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from attovisio.events import Event, EventBus
from attovisio.tracer import Tracer
from attovisio.narration import Narrator
from attovisio.visualization import Visualizer
from attovisio.io_observer import IOObserver
from attovisio.security_auditor import SecurityAuditor


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_bus():
    """Réinitialise le bus global avant chaque test."""
    EventBus.reset_global()
    yield
    EventBus.reset_global()


@pytest.fixture
def bus():
    return EventBus.get_global()


# ------------------------------------------------------------------
# Tests EventBus
# ------------------------------------------------------------------

class TestEventBus:

    def test_emit_and_get(self, bus):
        event = Event(kind="test", data={"x": 1})
        bus.emit(event)
        events = bus.get_events()
        assert len(events) == 1
        assert events[0].kind == "test"
        assert events[0].data["x"] == 1

    def test_filter_by_kind(self, bus):
        bus.emit(Event(kind="alpha", data={}))
        bus.emit(Event(kind="beta", data={}))
        bus.emit(Event(kind="alpha", data={}))
        alphas = bus.get_events(kind="alpha")
        assert len(alphas) == 2
        betas = bus.get_events(kind="beta")
        assert len(betas) == 1

    def test_subscribe_callback(self, bus):
        received = []
        bus.subscribe("my_event", lambda e: received.append(e))
        bus.emit(Event(kind="my_event", data={"msg": "hello"}))
        assert len(received) == 1
        assert received[0].data["msg"] == "hello"

    def test_subscribe_wildcard(self, bus):
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.emit(Event(kind="a", data={}))
        bus.emit(Event(kind="b", data={}))
        assert len(received) == 2

    def test_clear(self, bus):
        bus.emit(Event(kind="x", data={}))
        bus.clear()
        assert len(bus.get_events()) == 0

    def test_export_json(self, bus, tmp_path):
        bus.emit(Event(kind="test_export", data={"val": 42}))
        filepath = str(tmp_path / "events.json")
        bus.export_json(filepath)
        import json
        with open(filepath) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["kind"] == "test_export"

    def test_len(self, bus):
        assert len(bus) == 0
        bus.emit(Event(kind="x", data={}))
        assert len(bus) == 1

    def test_unsubscribe(self, bus):
        received = []
        cb = lambda e: received.append(e)
        bus.subscribe("x", cb)
        bus.unsubscribe("x", cb)
        bus.emit(Event(kind="x", data={}))
        assert len(received) == 0


# ------------------------------------------------------------------
# Tests Tracer
# ------------------------------------------------------------------

class TestTracer:

    def test_trace_basic(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

        events = bus.get_events()
        kinds = [e.kind for e in events]
        assert "function_call" in kinds
        assert "function_return" in kinds

    def test_trace_arguments_captured(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def multiply(x, y):
            return x * y

        multiply(4, 5)
        calls = bus.get_events(kind="function_call")
        assert len(calls) == 1
        args = calls[0].data.get("arguments", {})
        assert "x" in args or "4" in str(args)

    def test_trace_exception(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def boom():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            boom()

        errors = bus.get_events(kind="exception")
        assert len(errors) == 1
        assert errors[0].data["exception_type"] == "ValueError"
        assert "test error" in errors[0].data["exception_message"]

    def test_trace_return_value(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def greet(name):
            return f"Hello, {name}!"

        greet("Prince")
        returns = bus.get_events(kind="function_return")
        assert len(returns) == 1
        assert "Hello" in returns[0].data.get("return_value", "")

    def test_class_decorator(self, bus):
        """Test du décorateur de classe @Tracer.trace."""
        # Réinitialiser le singleton
        Tracer._default = None

        @Tracer.trace
        def demo(x):
            return x * 2

        result = demo(5)
        assert result == 10

    def test_duration_captured(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def slow():
            time.sleep(0.01)

        slow()
        returns = bus.get_events(kind="function_return")
        assert len(returns) == 1
        dur = returns[0].data.get("duration_ms", 0)
        assert dur >= 9  # au moins 9 ms

    def test_nested_calls(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def outer():
            return inner()

        @tracer.watch
        def inner():
            return 42

        outer()
        calls = bus.get_events(kind="function_call")
        assert len(calls) == 2

    def test_functools_wraps_preserved(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def documented_func():
            """Ma docstring."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "Ma docstring."


# ------------------------------------------------------------------
# Tests Narrator
# ------------------------------------------------------------------

class TestNarrator:

    def test_narrate_function_call(self, bus):
        from datetime import datetime
        event = Event(
            kind="function_call",
            data={"function": "test_fn", "arguments": {"x": "5"}, "depth": 0},
            timestamp=datetime.now(),
        )
        narrator = Narrator(bus=bus)
        sentence = narrator.narrate(event)
        assert "test_fn" in sentence
        assert "appelée" in sentence

    def test_narrate_exception(self, bus):
        from datetime import datetime
        event = Event(
            kind="exception",
            data={"function": "bad_fn", "exception_type": "TypeError", "exception_message": "oups"},
            timestamp=datetime.now(),
        )
        narrator = Narrator(bus=bus)
        sentence = narrator.narrate(event)
        assert "TypeError" in sentence

    def test_tell_empty(self, bus):
        narrator = Narrator(bus=bus)
        result = narrator.tell()
        assert "Aucun" in result

    def test_tell_with_events(self, bus):
        tracer = Tracer(bus=bus)

        @tracer.watch
        def fn():
            return 1

        fn()
        narrator = Narrator(bus=bus)
        story = narrator.tell()
        assert "fn" in story
        assert "appelée" in story

    def test_custom_template(self, bus):
        from datetime import datetime
        event = Event(kind="custom_event", data={"info": "test"}, timestamp=datetime.now())
        narrator = Narrator(bus=bus)
        narrator.add_template("custom_event", lambda d: f"Événement custom : {d['info']}")
        sentence = narrator.narrate(event)
        assert "Événement custom : test" in sentence

    def test_export_txt(self, bus, tmp_path):
        bus.emit(Event(kind="function_call", data={"function": "fn", "arguments": {}, "depth": 0}))
        narrator = Narrator(bus=bus)
        filepath = str(tmp_path / "story.txt")
        narrator.export_txt(filepath)
        assert os.path.exists(filepath)
        with open(filepath) as f:
            content = f.read()
        assert "fn" in content


# ------------------------------------------------------------------
# Tests IOObserver
# ------------------------------------------------------------------

class TestIOObserver:

    def test_manual_log(self, bus):
        observer = IOObserver(bus=bus)
        observer.log_open("/tmp/test.txt", mode="r")
        events = bus.get_events(kind="file_open")
        assert len(events) == 1
        assert events[0].data["path"] == "/tmp/test.txt"

    def test_manual_write(self, bus):
        observer = IOObserver(bus=bus)
        observer.log_write("/tmp/out.txt", size_bytes=100)
        events = bus.get_events(kind="file_write")
        assert len(events) == 1
        assert events[0].data["size_bytes"] == 100

    def test_manual_delete(self, bus):
        observer = IOObserver(bus=bus)
        observer.log_delete("/tmp/old.txt")
        events = bus.get_events(kind="file_delete")
        assert len(events) == 1

    def test_context_manager(self, bus):
        with IOObserver(bus=bus) as obs:
            obs.log_open("/tmp/x.txt")
        events = bus.get_events(kind="file_open")
        assert len(events) == 1


# ------------------------------------------------------------------
# Tests SecurityAuditor
# ------------------------------------------------------------------

class TestSecurityAuditor:

    def test_detects_sensitive_file(self, bus):
        auditor = SecurityAuditor(bus=bus)
        auditor.start()

        # Simuler un événement d'ouverture de fichier sensible
        bus.emit(Event(kind="file_open", data={"path": "/etc/passwd", "absolute_path": "/etc/passwd", "filename": "passwd", "extension": "", "mode": "r"}))

        alerts = auditor.get_alerts()
        assert len(alerts) >= 1
        assert any("passwd" in a["message"] for a in alerts)
        auditor.stop()

    def test_detects_ssh_key(self, bus):
        auditor = SecurityAuditor(bus=bus)
        auditor.start()
        bus.emit(Event(kind="file_open", data={"path": "/home/user/.ssh/id_rsa", "absolute_path": "/home/user/.ssh/id_rsa", "filename": "id_rsa", "extension": "", "mode": "r"}))

        alerts = auditor.get_alerts()
        assert len(alerts) >= 1
        auditor.stop()

    def test_report_no_alerts(self, bus):
        auditor = SecurityAuditor(bus=bus)
        report = auditor.report()
        assert "Aucune alerte" in report

    def test_context_manager(self, bus):
        with SecurityAuditor(bus=bus) as aud:
            bus.emit(Event(kind="file_open", data={"path": "/etc/shadow", "absolute_path": "/etc/shadow", "filename": "shadow", "extension": "", "mode": "r"}))
        assert len(aud.get_alerts()) >= 1


# ------------------------------------------------------------------
# Tests Visualizer
# ------------------------------------------------------------------

class TestVisualizer:

    def test_timeline_creates_file(self, bus, tmp_path):
        bus.emit(Event(kind="function_call", data={"function": "test", "arguments": {}, "depth": 0}))
        viz = Visualizer(bus=bus)
        fp = str(tmp_path / "timeline.html")
        result = viz.timeline(fp)
        assert os.path.exists(fp)
        with open(fp) as f:
            content = f.read()
        assert "AttoVisio" in content

    def test_dashboard_creates_file(self, bus, tmp_path):
        bus.emit(Event(kind="exception", data={"function": "fn", "exception_type": "E", "exception_message": "m", "depth": 0}))
        viz = Visualizer(bus=bus)
        fp = str(tmp_path / "dash.html")
        viz.dashboard(fp)
        assert os.path.exists(fp)

    def test_export_json(self, bus, tmp_path):
        bus.emit(Event(kind="test", data={"x": 99}))
        viz = Visualizer(bus=bus)
        fp = str(tmp_path / "out.json")
        viz.export_json(fp)
        import json
        with open(fp) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["data"]["x"] == 99

    def test_flamegraph_no_data(self, bus, tmp_path):
        viz = Visualizer(bus=bus)
        fp = str(tmp_path / "flame.html")
        viz.flamegraph(fp)
        assert os.path.exists(fp)


# ------------------------------------------------------------------
# Tests d'intégration
# ------------------------------------------------------------------

class TestIntegration:

    def test_full_workflow(self, bus):
        """Test complet : tracer → narrer → visualiser."""
        tracer = Tracer(bus=bus)

        @tracer.watch
        def compute(n):
            if n < 0:
                raise ValueError("Nombre négatif")
            return n ** 2

        compute(4)
        with pytest.raises(ValueError):
            compute(-1)

        events = bus.get_events()
        assert len(events) >= 3  # call, return, call, exception

        narrator = Narrator(bus=bus)
        story = narrator.tell()
        assert "compute" in story
        assert "ValueError" in story

    def test_event_serialization(self, bus):
        """Vérifie la sérialisation JSON des événements."""
        import json
        event = Event(kind="test", data={"key": "value", "num": 42})
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["kind"] == "test"
        assert data["data"]["num"] == 42
        assert "timestamp" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
