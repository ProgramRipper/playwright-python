import asyncio
from pathlib import Path
from typing import Dict

from playwright._impl._driver import compute_driver_executable, get_driver_env
from playwright._impl._transport import Transport


class FakePipeTransport(Transport):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop)

    def request_stop(self) -> None:
        self._stopped_future.set_result(None)

    async def wait_until_stopped(self) -> None:
        await self._stopped_future

    async def connect(self) -> None:
        self._stopped_future = asyncio.Future()

    async def run(self) -> None:
        await self._stopped_future

    def send(self, message: Dict) -> None:
        if message["method"] != "initialize":
            try:
                for path in compute_driver_executable():
                    Path(path).stat()
            except FileNotFoundError as e:
                return self.on_error_future.set_exception(e)

            return self.on_error_future.set_exception(FileNotFoundError)

        for type_, initializer, guid in [
            (
                "BrowserType",
                {"executablePath": "", "name": name},
                f"browser-type@{name}",
            )
            for name in ["chromium", "firefox", "webkit"]
        ] + [
            ("LocalUtils", {"deviceDescriptors": []}, "localUtils"),
            (
                "Playwright",
                {
                    name: {"guid": f"browser-type@{name}"}
                    for name in ["chromium", "firefox", "webkit"]
                }
                | {
                    "utils": {"guid": "localUtils"},
                },
                "Playwright",
            ),
        ]:
            self.on_message(
                {
                    "guid": "",
                    "method": "__create__",
                    "params": {
                        "type": type_,
                        "initializer": initializer,
                        "guid": guid,
                    },
                }
            )

        self.on_message(
            {"id": message["id"], "result": {"playwright": {"guid": "Playwright"}}}
        )

