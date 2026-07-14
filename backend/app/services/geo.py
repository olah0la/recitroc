"""Geocoding, weather and air-quality via the Open-Meteo APIs (free, no key).

TEACHING NOTE — why an external HTTP call demands async:
a call to another service takes 50–500ms, an eternity for a CPU. A sync
endpoint would pin a worker thread doing literally nothing for that time.
An async endpoint `await`s the response, and the event loop serves other
requests meanwhile. This is the single strongest reason to reach for
`async def` in a web app.
"""

import math
from dataclasses import dataclass

import httpx

from app.core.config import settings

# Human-readable text for WMO weather interpretation codes (subset).
WMO_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    51: "light drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    95: "thunderstorm",
}

# European AQI bands as published by the EEA.
AQI_BANDS = [
    (20, "good"),
    (40, "fair"),
    (60, "moderate"),
    (80, "poor"),
    (100, "very poor"),
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometers.

    TEACHING NOTE — this is the EXACT distance, computed in Python for
    the handful of rows a page returns. The SQL side (crud/posting.py)
    deliberately uses a cruder, arithmetic-only approximation instead:
    it only needs to ORDER candidates, must run on both postgres and
    SQLite (whose builds often lack trig functions), and touches every
    candidate row. Precision where it's shown, portability where it's
    hot — that split is the design.
    """
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


# TEACHING NOTE — frozen dataclasses as return types: the rest of the app
# gets typed attributes (location.latitude) instead of digging through
# provider-specific JSON. If we ever switch providers, only this file
# changes.
@dataclass(frozen=True)
class GeoLocation:
    name: str
    country: str | None
    latitude: float
    longitude: float


@dataclass(frozen=True)
class CurrentWeather:
    temperature_c: float
    wind_speed_kmh: float
    weather_code: int

    @property
    def conditions(self) -> str:
        return WMO_WEATHER_CODES.get(self.weather_code, "mixed conditions")


@dataclass(frozen=True)
class AirQuality:
    european_aqi: int | None

    @property
    def rating(self) -> str:
        if self.european_aqi is None:
            return "unknown"
        for threshold, label in AQI_BANDS:
            if self.european_aqi <= threshold:
                return label
        return "extremely poor"


class GeoClient:
    """Async client for Open-Meteo.

    TEACHING NOTE — it wraps a SHARED httpx.AsyncClient (created once in
    the app lifespan, see main.py). A shared client reuses TCP/TLS
    connections (keep-alive) across requests; creating a client per
    request would redo the TLS handshake every time — the most common
    httpx performance mistake.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def geocode(self, city: str) -> GeoLocation | None:
        """Resolve a city name to coordinates. None if the city is unknown."""
        response = await self._http.get(
            f"{settings.GEOCODING_API_URL}/search",
            params={"name": city, "count": 1},
        )
        # raise_for_status turns HTTP 4xx/5xx from the provider into an
        # exception here, so callers handle ONE failure mode (httpx.HTTPError)
        # instead of inspecting status codes everywhere.
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None
        hit = results[0]
        return GeoLocation(
            name=hit["name"],
            country=hit.get("country"),
            latitude=hit["latitude"],
            longitude=hit["longitude"],
        )

    async def current_weather(
        self, latitude: float, longitude: float
    ) -> CurrentWeather:
        response = await self._http.get(
            f"{settings.WEATHER_API_URL}/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code,wind_speed_10m",
            },
        )
        response.raise_for_status()
        current = response.json()["current"]
        return CurrentWeather(
            temperature_c=current["temperature_2m"],
            wind_speed_kmh=current["wind_speed_10m"],
            weather_code=current["weather_code"],
        )

    async def air_quality(self, latitude: float, longitude: float) -> AirQuality:
        response = await self._http.get(
            f"{settings.AIR_QUALITY_API_URL}/air-quality",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "european_aqi",
            },
        )
        response.raise_for_status()
        return AirQuality(european_aqi=response.json()["current"].get("european_aqi"))
