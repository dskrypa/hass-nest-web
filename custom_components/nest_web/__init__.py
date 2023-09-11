"""
Initialize the Nest Web integration

:author: Doug Skrypa
"""

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from nest_client.client import NestWebClient

from .constants import DOMAIN, DATA_NEST_CONFIG
from .device import NestWebDevice


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nest components with dispatch between old/new flows."""
    hass.data[DOMAIN] = {}
    hass.data[DATA_NEST_CONFIG] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nest from legacy config entry."""
    conf = hass.data.get(DATA_NEST_CONFIG, {})

    if not (config_path := conf.get('config_path')):
        # Note: importlib.resources.files did not work for this, I assume due to the way HACS installs the integration
        config_path = Path(__file__).resolve().parent.joinpath('config', 'nest.cfg')
        if not config_path.is_file():
            config_path = None

    client = NestWebClient(config_path, overrides=conf.get('overrides'))
    hass.data[DOMAIN] = nest_web_device = NestWebDevice(hass, conf, client)
    success = await nest_web_device.initialize()
    if not success:
        return False

    for module in ('climate', 'sensor'):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, module))

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    nest_web_device = hass.data[DOMAIN]  # type: NestWebDevice
    await nest_web_device.aclose()
