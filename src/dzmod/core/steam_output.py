import re
from collections.abc import Callable
from typing import ClassVar


class SteamOutput:
    """Splits the SteamCMD output stream into lines and workshop events. SteamCMD writes `Downloading item … ...` and
    `Success. Downloaded item …` without line breaks; these are reported through `started` and `result`, all other
    text through `line` (complete lines) or `partial` (an unfinished line such as a password prompt)."""

    ANSI: ClassVar[re.Pattern[str]] = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
    STARTED: ClassVar[re.Pattern[str]] = re.compile(r"Downloading item (\d+) \.\.\.[ \t]*")
    SUCCESS: ClassVar[re.Pattern[str]] = re.compile(
        r'Success\. Downloaded item (\d+) to "[^"]*" \((\d+) bytes\)\.?[ \t]*')
    FAILED: ClassVar[re.Pattern[str]] = re.compile(r"ERROR! Download item (\d+) failed \(([^)]*)\)\.?[ \t]*")
    TIMEOUT: ClassVar[re.Pattern[str]] = re.compile(r"ERROR! Timeout downloading item (\d+)[ \t]*")
    EVENT_STARTS: ClassVar[tuple[str, ...]] = ("Downloading item", "Success. Downloaded", "ERROR!")

    def __init__(self, line: Callable[[str], None], partial: Callable[[str], None], started: Callable[[str], None],
                 result: Callable[[str, bool, int, str], None]) -> None:
        self.line = line
        self.partial = partial
        self.started = started
        self.result = result
        self.buffer = ""

    def feed(self, text: str) -> None:
        """Adds text (line endings normalized, escape sequences removed) and reports every complete event and line;
        an unfinished last line stays buffered."""

        self.buffer += self.ANSI.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
        while True:
            match = self._next_event()
            if match is None:
                break
            pattern, found = match
            self._lines(self.buffer[:found.start()])
            self.buffer = self.buffer[found.end():]
            self._event(pattern, found)

        head, newline, rest = self.buffer.rpartition("\n")
        if newline:
            self._lines(head)
            self.buffer = rest

    def idle(self) -> None:
        """Reports the buffered unfinished line as `partial` when SteamCMD waits (e.g. for a password), unless it is
        the beginning of a workshop event."""

        text = self.buffer.lstrip()
        if text and not any(text.startswith(start) or start.startswith(text) for start in self.EVENT_STARTS):
            self.partial(self.buffer)
            self.buffer = ""

    def finish(self) -> None:
        """Reports the remaining buffered text as lines."""

        self._lines(self.buffer)
        self.buffer = ""

    def _next_event(self) -> tuple[re.Pattern[str], re.Match[str]] | None:
        """Returns the workshop event that starts first in the buffer."""

        matches = [(pattern, found) for pattern in (self.STARTED, self.SUCCESS, self.FAILED, self.TIMEOUT)
                   if (found := pattern.search(self.buffer))]
        return min(matches, key=lambda match: match[1].start(), default=None)

    def _event(self, pattern: re.Pattern[str], found: re.Match[str]) -> None:
        """Calls `started` or `result` for a matched event."""

        if pattern is self.STARTED:
            self.started(found.group(1))
        elif pattern is self.SUCCESS:
            self.result(found.group(1), True, int(found.group(2)), "")
        elif pattern is self.FAILED:
            self.result(found.group(1), False, 0, found.group(2))
        else:
            self.result(found.group(1), False, 0, "Timeout")

    def _lines(self, text: str) -> None:
        """Reports every non-empty line of `text` without surrounding whitespace."""

        for line in text.split("\n"):
            if line.strip():
                self.line(line.strip())
