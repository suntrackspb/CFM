from textual.widget import Widget
from textual.widgets import Button, Static, Input
from textual.containers import Horizontal
from textual.message import Message
from textual import events

class DialogConfirm(Widget):
    class Result(Message):
        def __init__(self, result):
            super().__init__()
            self.result = result

    def __init__(self, text, yes="Yes", no="No", cancel=None):
        super().__init__()
        self.text = text
        self.yes = yes
        self.no = no
        self.cancel = cancel
        self._btn_yes = Button(self.yes, id="yes")
        self._btn_no = Button(self.no, id="no")
        self._btn_cancel = Button(self.cancel, id="cancel") if self.cancel else None

    def compose(self):
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
        def __init__(self, value, confirmed):
            super().__init__()
            self.value = value
            self.confirmed = confirmed

    def __init__(self, prompt, ok="OK", cancel="Cancel"):
        super().__init__()
        self.prompt = prompt
        self.ok = ok
        self.cancel = cancel
        self._input = Input(placeholder="", id="input")
        self._btn_ok = Button(self.ok, id="ok")
        self._btn_cancel = Button(self.cancel, id="cancel")

    def compose(self):
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