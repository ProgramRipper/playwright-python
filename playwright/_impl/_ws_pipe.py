import asyncio
from typing import Dict

from pyee.asyncio import AsyncIOEventEmitter
from websockets import ConnectionClosed, connect

from playwright._impl._transport import Transport


class WsPipeTransport(AsyncIOEventEmitter, Transport):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        ws_endpoint: str,
        timeout: float = None,
        slow_mo: float = None,
        headers: Dict[str, str] = None,
        expose_network: str = None,
    ) -> None:
        super().__init__(loop)
        Transport.__init__(self, loop)
        self._stop_event = asyncio.Event()

        self._ws_endpoint = ws_endpoint
        self._timeout = timeout
        self._slow_mo = slow_mo
        self._headers = headers
        self._expose_network = expose_network

    def request_stop(self) -> None:
        self._stop_event.set()

    def dispose(self) -> None:
        self.on_error_future.cancel()

    async def wait_until_stopped(self) -> None:
        await self._ws.wait_closed()

    async def connect(self) -> None:
        try:
            self._ws = await connect(
                self._ws_endpoint, additional_headers=self._headers, max_size=None
            )
        except Exception as e:
            self.on_error_future.set_exception(e)
            raise e

    async def run(self) -> None:
        wait = asyncio.create_task(self._stop_event.wait())

        while not self._stop_event.is_set():
            recv = asyncio.create_task(self._ws.recv(False))
            await asyncio.wait([recv, wait], return_when=asyncio.FIRST_COMPLETED)

            if self._stop_event.is_set():
                recv.cancel()
                break

            try:
                self.on_message(self.deserialize_message(recv.result()))
            except ConnectionClosed:
                if not self._stop_event.is_set():
                    self.on_error_future.set_exception(
                        Exception("Connection closed while reading from the driver")
                    )
                break

        wait.cancel()
        self.emit("close", "")
        await self._ws.close()

    def send(self, message: Dict) -> None:
        self._ws.protocol.send_binary(self.serialize_message(message))
        self._ws.send_data()
