"""Tests for the journey-status client. Run: python -m unittest discover -s tests"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import httpx

from togpuls.clients import journey_status as js

OSLO = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=OSLO)


class WindowTest(unittest.TestCase):
    def test_midday(self):
        self.assertEqual(js.window(NOW, 90, 90), ("10:30", "13:30"))

    def test_over_midnight(self):  # AE4
        now = datetime(2026, 11, 6, 23, 10, tzinfo=OSLO)
        self.assertEqual(js.window(now, 90, 90), ("21:40", "00:40"))

    def test_utc_input_formats_in_oslo_time(self):
        now = datetime(2026, 11, 6, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(js.window(now, 90, 90), ("12:30", "15:30"))

    def test_dst_spring_forward(self):
        now = datetime(2027, 3, 28, 3, 30, tzinfo=OSLO)
        self.assertEqual(js.window(now, 90, 90), ("01:00", "05:00"))


class FetchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        js._recent.clear()
        self.requests: list[httpx.Request] = []

    def _client(self, handler) -> httpx.AsyncClient:
        def record(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        return httpx.AsyncClient(transport=httpx.MockTransport(record))

    async def _fetch(self, handler, from_stop="NSR:StopPlace:337", to_stop="NSR:StopPlace:11"):
        async with self._client(handler) as client:
            return await js.fetch_journey_status(client, from_stop, to_stop, NOW, 90, 90)

    async def test_happy_path_returns_body_unchanged(self):
        body = {"now": "2026-11-06T11:00:00Z", "trains": [{"level": "red"}], "summary": None}
        result = await self._fetch(lambda r: httpx.Response(200, json=body))
        self.assertEqual(result, body)
        req = self.requests[0]
        self.assertEqual(req.url.path, "/notification-api/v1/journey-status")
        self.assertEqual(
            dict(req.url.params),
            {"from_stop": "NSR:StopPlace:337", "to_stop": "NSR:StopPlace:11",
             "begin": "10:30", "end": "13:30"},
        )
        self.assertEqual(req.headers["ET-Client-Name"], "kengu-togpuls")

    async def test_error_statuses_return_none(self):  # AE2
        for resp in (
            httpx.Response(422, json={"detail": "same place"}),
            httpx.Response(429, headers={"Retry-After": "30"}),
            httpx.Response(503, json={"reason": "plan_not_loaded"}),
        ):
            js._recent.clear()
            with self.subTest(status=resp.status_code):
                self.assertIsNone(await self._fetch(lambda r, resp=resp: resp))

    async def test_transport_error_and_timeout_return_none(self):
        for exc in (httpx.ConnectError("down"), httpx.ReadTimeout("slow")):
            js._recent.clear()

            def handler(request, exc=exc):
                raise exc

            with self.subTest(exc=type(exc).__name__):
                self.assertIsNone(await self._fetch(handler))

    async def test_non_json_and_non_object_bodies_return_none(self):
        for resp in (httpx.Response(200, text="<html>oops</html>"), httpx.Response(200, json=[1, 2])):
            js._recent.clear()
            with self.subTest(body=resp.text):
                self.assertIsNone(await self._fetch(lambda r, resp=resp: resp))

    async def test_rate_guard_caps_reads_per_pair(self):
        ok = lambda r: httpx.Response(200, json={"trains": []})  # noqa: E731
        clock = [1000.0]
        with mock.patch.object(js, "_clock", lambda: clock[0]):
            for _ in range(6):
                self.assertIsNotNone(await self._fetch(ok))
            self.assertIsNone(await self._fetch(ok))
            self.assertEqual(len(self.requests), 6)  # the 7th sent nothing

            self.assertIsNotNone(await self._fetch(ok, to_stop="NSR:StopPlace:418"))

            clock[0] += 60
            self.assertIsNotNone(await self._fetch(ok))


if __name__ == "__main__":
    unittest.main()
