"""Tests for the A2UI (Agent-to-UI) System."""

import pytest
import asyncio
from nexus.a2a.a2ui import (
    A2UICard, A2UIBuilder, A2UIFactory, A2UIRegistry, get_a2ui_registry,
    CardType, ChartType, AlertLevel, UIAction, FormField,
)


class TestCardType:
    def test_all_types(self):
        assert CardType.FORM.value == "form"
        assert CardType.CHART.value == "chart"
        assert CardType.TABLE.value == "table"
        assert CardType.ALERT.value == "alert"
        assert CardType.CODE.value == "code"

    def test_type_count(self):
        assert len(CardType) >= 12


class TestUIAction:
    def test_create(self):
        a = UIAction(id="a1", label="Click Me", action_type="click")
        assert a.id == "a1"


class TestFormField:
    def test_create(self):
        f = FormField(name="email", label="Email", field_type="text", required=True)
        assert f.name == "email"


class TestA2UIBuilder:
    def test_build_card(self):
        card = (
            A2UIBuilder(CardType.ALERT, "Test")
            .with_data("message", "Hello")
            .build()
        )
        assert card.card_type == CardType.ALERT
        assert card.data["message"] == "Hello"


class TestA2UIFactory:
    def test_alert(self):
        c = A2UIFactory.alert("W", "msg", AlertLevel.WARNING)
        assert c.card_type == CardType.ALERT

    def test_chart(self):
        c = A2UIFactory.chart("S", ChartType.BAR, labels=["J"], datasets=[{"label": "R", "data": [1]}])
        assert c.card_type == CardType.CHART

    def test_table(self):
        c = A2UIFactory.table("U", columns=["N"], rows=[["A"]])
        assert c.card_type == CardType.TABLE

    def test_code(self):
        c = A2UIFactory.code("E", "print()")
        assert c.card_type == CardType.CODE

    def test_progress(self):
        c = A2UIFactory.progress("P", current=50, total=100)
        assert c.data["percentage"] == 50.0

    def test_form(self):
        c = A2UIFactory.form("F", [FormField(name="n", label="N", field_type="text")])
        assert c.card_type == CardType.FORM

    def test_button_group(self):
        c = A2UIFactory.button_group("B", [{"label": "OK", "action_id": "ok"}])
        assert c.card_type == CardType.BUTTON

    def test_dashboard(self):
        c = A2UIFactory.dashboard("D", [{"label": "CPU", "value": "23%"}])
        assert c.card_type == CardType.DASHBOARD


class TestA2UICard:
    def test_to_dict(self):
        c = A2UIFactory.alert("T", "M", AlertLevel.INFO)
        d = c.to_dict()
        assert d["card_type"] == "alert"


class TestA2UIRegistry:
    def setup_method(self):
        self.registry = A2UIRegistry()

    def test_register_handler(self):
        def my_handler(payload):
            return {"ok": True}
        self.registry.register_handler("test-action", my_handler)
        assert self.registry.get_handler("test-action") is my_handler

    def test_get_nonexistent(self):
        assert self.registry.get_handler("nope") is None

    def test_handle_action_sync(self):
        def handler(payload):
            return {"result": payload.get("input")}
        self.registry.register_handler("process", handler)
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.registry.handle_action("process", {"input": "hello"})
        )
        loop.close()
        assert result["success"] is True

    def test_handle_unknown_action(self):
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.registry.handle_action("unknown", {})
        )
        loop.close()
        assert "error" in result
