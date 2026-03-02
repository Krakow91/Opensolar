from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class OpenDTUClient:
    base_url: str
    username: str | None = None
    password: str | None = None
    verify_tls: bool = True
    timeout_seconds: int = 15

    def _auth(self) -> tuple[str, str] | None:
        if self.username and self.password:
            return (self.username, self.password)
        return None

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        response = requests.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
            auth=self._auth(),
            verify=self.verify_tls,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unerwartetes API-Format: JSON root ist kein Objekt")

        return payload

    def fetch_livedata_status(self) -> dict[str, Any]:
        return self._get_json("/api/livedata/status")

    def fetch_livedata_status_for_inverter(self, serial: str) -> dict[str, Any]:
        return self._get_json("/api/livedata/status", params={"inv": serial})

    def fetch_livedata_status_with_details(self) -> dict[str, Any]:
        payload = self.fetch_livedata_status()

        inverters = payload.get("inverters")
        if not isinstance(inverters, list) or not inverters:
            return payload

        merged_inverters: list[dict[str, Any]] = []
        for inverter in inverters:
            if not isinstance(inverter, dict):
                continue

            serial = inverter.get("serial")
            if not serial:
                merged_inverters.append(inverter)
                continue

            try:
                detail_payload = self.fetch_livedata_status_for_inverter(str(serial))
                detail_inverters = detail_payload.get("inverters", [])
                if isinstance(detail_inverters, list) and detail_inverters and isinstance(detail_inverters[0], dict):
                    merged = dict(inverter)
                    merged.update(detail_inverters[0])
                    merged_inverters.append(merged)
                else:
                    merged_inverters.append(inverter)
            except (requests.RequestException, ValueError):
                # Fallback auf Basisdaten, wenn Detailabruf fehlschlägt.
                merged_inverters.append(inverter)

        merged_payload = dict(payload)
        merged_payload["inverters"] = merged_inverters
        return merged_payload
