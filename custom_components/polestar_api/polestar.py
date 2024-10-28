"""Polestar API for Polestar integration."""

import logging
from datetime import datetime, timedelta

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN as POLESTAR_API_DOMAIN
from .pypolestar.exception import PolestarApiException, PolestarAuthException
from .pypolestar.polestar import PolestarApi

POST_HEADER_JSON = {"Content-Type": "application/json"}

_LOGGER = logging.getLogger(__name__)


class UnknownVIN(ValueError):
    pass


class PolestarCar:
    """Polestar EV integration."""

    def __init__(self, api: PolestarApi, vin: str) -> None:
        """Initialize the Polestar Car."""
        self.polestar_api = api
        self.vin = vin
        self.name = "Polestar " + self.get_unique_id()
        self.model = (
            self.get_value("getConsumerCarsV2", "content/model/name") or "Unknown model"
        )

    def get_unique_id(self) -> str:
        """Last 4 character of the VIN"""
        if self.vin is None:
            raise UnknownVIN
        return self.vin[-4:]

    def get_device_info(self) -> DeviceInfo:
        """Return DeviceInfo for current device"""
        return DeviceInfo(
            identifiers={(POLESTAR_API_DOMAIN, self.vin)},
            manufacturer="Polestar",
            model=self.model,
            name=self.name,
            serial_number=self.vin,
        )

    def get_latest_data(self, query: str, field_name: str):
        """Get the latest data from the Polestar API."""
        return self.polestar_api.get_latest_data(
            vin=self.vin, query=query, field_name=field_name
        )

    async def async_update(self) -> None:
        """Update data from Polestar."""
        try:
            await self.polestar_api.get_ev_data(self.vin)
            return
        except PolestarApiException as e:
            _LOGGER.warning("API Exception on update data %s", str(e))
            self.a.next_update = datetime.now() + timedelta(seconds=5)
        except PolestarAuthException as e:
            _LOGGER.warning("Auth Exception on update data %s", str(e))
            await self.polestar_api.auth.get_token()
            self.polestar_api.next_update = datetime.now() + timedelta(seconds=5)
        except httpx.ConnectTimeout as e:
            _LOGGER.warning("Connection Timeout on update data %s", str(e))
            self.polestar_api.next_update = datetime.now() + timedelta(seconds=15)
        except httpx.ConnectError as e:
            _LOGGER.warning("Connection Error on update data %s", str(e))
            self.polestar_api.next_update = datetime.now() + timedelta(seconds=15)
        except httpx.ReadTimeout as e:
            _LOGGER.warning("Read Timeout on update data %s", str(e))
            self.polestar_api.next_update = datetime.now() + timedelta(seconds=15)
        except Exception as e:
            _LOGGER.error("Unexpected Error on update data %s", str(e))
            self.polestar_api.next_update = datetime.now() + timedelta(seconds=60)
        self.polestar_api.latest_call_code_v2 = 500
        self.polestar_api.updating = False

    def get_value(self, query: str, field_name: str, skip_cache: bool = False):
        """Get the latest value from the Polestar API."""
        data = self.polestar_api.get_cache_data(
            vin=self.vin, query=query, field_name=field_name, skip_cache=skip_cache
        )
        if data is None:
            # if amp and voltage can be null, so we will return 0
            if field_name in ("chargingCurrentAmps", "chargingPowerWatts"):
                return 0
            return
        return data

    def get_token_expiry(self):
        """Get the token expiry time."""
        return self.polestar_api.auth.token_expiry

    def get_latest_call_code_v1(self):
        """Get the latest call code mystar API."""
        return self.polestar_api.latest_call_code

    def get_latest_call_code_v2(self):
        """Get the latest call code mystar-v2 API."""
        return self.polestar_api.latest_call_code_2

    def get_latest_call_code_auth(self):
        """Get the latest call code mystar API."""
        return self.polestar_api.auth.latest_call_code

    def get_latest_call_code(self):
        """Get the latest call code."""
        # if AUTH code last code is not 200 then we return that error code,
        # otherwise just give the call_code in API from v1 and then v2
        if self.polestar_api.auth.latest_call_code != 200:
            return self.polestar_api.auth.latest_call_code
        if self.polestar_api.latest_call_code != 200:
            return self.polestar_api.latest_call_code
        return self.polestar_api.latest_call_code_2


class PolestarCoordinator:
    """Polestar EV integration."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Initialize the Polestar API."""
        self.polestar_api = PolestarApi(username, password, get_async_client(hass))

    async def async_init(self):
        """Initialize the Polestar API."""
        await self.polestar_api.async_init()

    def get_cars(self) -> list[PolestarCar]:
        return [
            PolestarCar(api=self.polestar_api, vin=vin)
            for vin in self.polestar_api.vins
        ]
