from dzmod.core.steam_output import SteamOutput


def collect() -> tuple[SteamOutput, list[tuple]]:
    """Creates a SteamOutput that records every callback as a tuple."""

    events: list[tuple] = []
    output = SteamOutput(
        lambda line: events.append(("line", line)),
        lambda text: events.append(("partial", text)),
        lambda mod_id: events.append(("started", mod_id)),
        lambda mod_id, ok, size, reason: events.append(("result", mod_id, ok, size, reason)),
    )
    return output, events


def test_events_without_line_breaks_are_split() -> None:
    output, events = collect()
    output.feed("Waiting for user info...OK\nDownloading item 1559212036 ...")
    output.feed('Success. Downloaded item 1559212036 to "/home/u/Steam/steamapps/workshop/content/221100/1559212036"'
                ' (538560 bytes) Downloading item 1564026768 ...')
    output.feed("ERROR! Download item 1564026768 failed (Failure).\n")
    output.finish()

    assert events == [
        ("line", "Waiting for user info...OK"),
        ("started", "1559212036"),
        ("result", "1559212036", True, 538560, ""),
        ("started", "1564026768"),
        ("result", "1564026768", False, 0, "Failure"),
    ]


def test_event_split_across_chunks_waits_for_the_rest() -> None:
    output, events = collect()
    output.feed('Success. Downloaded item 1 to "/a"')
    output.idle()
    output.feed(" (10 bytes)\n")

    assert events == [("result", "1", True, 10, "")]


def test_prompt_is_reported_as_partial_when_idle() -> None:
    output, events = collect()
    output.feed("Logging in user 'karnes' to Steam Public...\npassword: ")
    output.idle()

    assert events == [("line", "Logging in user 'karnes' to Steam Public..."), ("partial", "password: ")]


def test_carriage_returns_and_escape_codes_are_normalized() -> None:
    output, events = collect()
    output.feed("\x1b[0m[  0%] Checking for available updates...\r[----] Verifying installation...\r\n")

    assert events == [("line", "[  0%] Checking for available updates..."),
                      ("line", "[----] Verifying installation...")]
