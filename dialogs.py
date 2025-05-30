from __future__ import annotations
from typing import Any, Optional
from textual.widget import Widget
from textual.widgets import Button, Static, Input
from textual.containers import Horizontal
from textual.message import Message
from textual import events

class DialogConfirm(Widget):
    class Result(Message):
        def __init__(self, result: str) -> None:
            super().__init__()
            self.result: str = result

    def __init__(self, text: str, yes: str = "Yes", no: str = "No", cancel: Optional[str] = None) -> None:
        super().__init__()
        self.text: str = text
        self.yes: str = yes
        self.no: str = no
        self.cancel: Optional[str] = cancel
        self._btn_yes: Button = Button(self.yes, id="yes")
        self._btn_no: Button = Button(self.no, id="no")
        self._btn_cancel: Optional[Button] = Button(self.cancel, id="cancel") if self.cancel else None

    def compose(self) -> Any:
        yield Static(self.text)
        btns = [self._btn_yes, self._btn_no]
        if self._btn_cancel:
            btns.append(self._btn_cancel)
        yield Horizontal(*btns)
        hint = f"Press Y for {self.yes}, N for {self.no}"
        if self.cancel:
            hint += f", C for {self.cancel}"
        yield Static(hint, classes="hint")

    async def on_mount(self) -> None:
        self._btn_yes.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.post_message(self.Result(event.button.id))

    async def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key == self.yes[0].lower() or key == "enter":
            self.post_message(self.Result("yes"))
        elif key == self.no[0].lower():
            self.post_message(self.Result("no"))
        elif self.cancel and (key == self.cancel[0].lower() or key == "escape"):
            self.post_message(self.Result("cancel"))

class DialogInput(Widget):
    class Result(Message):
        def __init__(self, value: str, confirmed: bool) -> None:
            super().__init__()
            self.value: str = value
            self.confirmed: bool = confirmed

    def __init__(self, prompt: str, ok: str = "OK", cancel: str = "Cancel") -> None:
        super().__init__()
        self.prompt: str = prompt
        self.ok: str = ok
        self.cancel: str = cancel
        self._input: Input = Input(placeholder="", id="input")
        self._btn_ok: Button = Button(self.ok, id="ok")
        self._btn_cancel: Button = Button(self.cancel, id="cancel")

    def compose(self) -> Any:
        yield Static(self.prompt)
        yield self._input
        yield Horizontal(self._btn_ok, self._btn_cancel)

    async def on_mount(self) -> None:
        self._input.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.post_message(self.Result(self._input.value, True))
        else:
            self.post_message(self.Result(self._input.value, False))

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self.post_message(self.Result(self._input.value, True))
        elif event.key == "escape":
            self.post_message(self.Result(self._input.value, False)) 