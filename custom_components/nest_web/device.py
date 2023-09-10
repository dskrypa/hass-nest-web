"""
:author: Doug Skrypa
"""

import logging
from asyncio import Lock
from datetime import datetime, timedelta

from homeassistant.const import CONF_STRUCTURE
from homeassistant.core import HomeAssistant

from nest_client.client import NestWebClient
from nest_client.entities import Structure
from nest_client.exceptions import NestException
from nest_client.utils import format_duration

from .constants import DOMAIN

__all__ = ['NestWebDevice']
log = logging.getLogger(__name__)

MIN_REFRESH_INTERVAL = timedelta(seconds=15)
DEFAULT_REFRESH_INTERVAL = 180


class NestWebDevice:
    def __init__(self, hass: HomeAssistant, conf, nest: NestWebClient):
        """Init Nest Devices."""
        self.hass = hass
        self.nest = nest
        self.refresh_interval = timedelta(seconds=int(conf.get('refresh_interval', DEFAULT_REFRESH_INTERVAL)))
        if self.refresh_interval < MIN_REFRESH_INTERVAL:
            log.warning(f'Invalid {DOMAIN}.refresh_interval = {self.refresh_interval} - using default')
            self.refresh_interval = timedelta(seconds=DEFAULT_REFRESH_INTERVAL)
        self.local_structure = conf.get(CONF_STRUCTURE)
        self.structures = []
        self.struct_thermostat_groups = []
        self.refresh_lock = Lock()
        self.last_refresh = datetime.now()
        self.last_command = datetime.now()

    async def initialize(self):
        log.info('Beginning NestWebDevice.initialize')
        try:
            init_id_obj_map = await self.nest.get_init_objects()
            structures = [obj for obj in init_id_obj_map.values() if isinstance(obj, Structure)]
            structure_names = {obj.name for obj in structures}
            if self.local_structure is None:
                self.local_structure = structure_names
                self.structures = structures
            else:
                for structure in structures:
                    if structure.name not in self.local_structure:
                        log.debug(f'Ignoring {structure=} - not in {self.local_structure}')
                    else:
                        self.structures.append(structure)

            for structure in self.structures:
                for device, shared in (await structure.thermostats_and_shared()):
                    self.struct_thermostat_groups.append((structure, device, shared))
        except NestException as e:
            log.error(f'Connection error while attempting to access the Nest web service: {e}')
            return False
        log.info('Finished NestWebDevice.initialize')
        return True

    def needs_refresh(self) -> bool:
        # now = datetime.now()
        # return (now - self.last_refresh) >= self.refresh_interval or (now - self.last_command) >= MIN_REFRESH_INTERVAL
        return (datetime.now() - self.last_refresh) >= self.refresh_interval or self.last_command > self.last_refresh

    async def maybe_refresh(self) -> bool:
        if not self.needs_refresh():
            # log.debug('Refresh is not currently necessary')
            return False
        else:
            await self.refresh()
            return True

    async def refresh(self):
        async with self.refresh_lock:  # Multiple threads may try at once; if late to acquire lock, return immediately
            delta = datetime.now() - self.last_refresh
            too_soon = delta < MIN_REFRESH_INTERVAL
            if self.last_command < self.last_refresh and too_soon:
                # log.debug(f'Skipping refresh - last_refresh={self.last_refresh.isoformat(" ")}')
                return

            cmd_info = f', but last_command={self.last_command.isoformat(" ")}' if too_soon else ''
            delta_str = format_duration(delta.total_seconds())
            log.info(f'Refreshing known objects - last refresh was {delta_str} ago{cmd_info}')
            await self.nest.refresh_known_objects()
            self.last_refresh = datetime.now()

    async def aclose(self):
        await self.nest.aclose()
