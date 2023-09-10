"""
Nest Web thermostat control

:author: Doug Skrypa
"""

import logging
from asyncio import sleep
from datetime import datetime

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW
from homeassistant.components.climate.const import SUPPORT_FAN_MODE, FAN_AUTO, FAN_ON, FAN_OFF
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF
from homeassistant.components.climate.const import PRESET_AWAY, PRESET_NONE, SUPPORT_PRESET_MODE
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_RANGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from nest_client.exceptions import NestException
from nest_client.entities import Structure, ThermostatDevice, Shared

from .constants import DOMAIN, SIGNAL_NEST_UPDATE, ACTION_NEST_TO_HASS, FAN_MODES_NEST_TO_HASS
from .constants import NEST_MODE_HEAT_COOL, MODE_HASS_TO_NEST, MODE_NEST_TO_HASS, TEMP_UNIT_MAP
from .device import NestWebDevice

__all__ = ['NestThermostat', 'async_setup_entry']
log = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Nest climate device based on a config entry."""
    # temp_unit = hass.config.units.temperature_unit
    nest_web_dev = hass.data[DOMAIN]  # type: NestWebDevice
    all_devices = [
        NestThermostat(nest_web_dev, structure, device, shared)
        for structure, device, shared in nest_web_dev.struct_thermostat_groups
    ]
    async_add_entities(all_devices, True)


class NestThermostat(ClimateEntity):  # noqa
    def __init__(
        self,
        nest_web_dev: NestWebDevice,
        structure: Structure,
        device: ThermostatDevice,
        shared: Shared,
    ):
        self.nest_web_dev = nest_web_dev
        self.structure = structure
        self.device = device
        self.shared = shared
        self._fan_modes = [FAN_ON, FAN_AUTO, FAN_OFF]
        self._support_flags = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
        if shared.can_heat and shared.can_cool:
            self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF]
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE_RANGE
        elif shared.can_heat:
            self._operation_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        elif shared.can_cool:
            self._operation_list = [HVAC_MODE_COOL, HVAC_MODE_OFF]
        else:
            self._operation_list = [HVAC_MODE_OFF]

        self._has_fan = self.device.has['fan']
        if self._has_fan:
            self._support_flags |= SUPPORT_FAN_MODE

        # self._temperature_scale = TEMP_UNIT_MAP[self.device.client.config.temp_unit]
        self._update_attrs()

    def _update_attrs(self):
        device, shared = self.device, self.shared
        self._location = device.where
        self._name = device.name
        self._humidity = device.humidity
        self._hvac_state = shared.hvac_state
        # self._fan_running = shared.hvac_fan_state
        self._fan_mode = device.fan.get('mode')
        self._away = self.structure.away
        self._temperature = shared._current_temperature
        self._mode = mode = shared.target_temperature_type
        self._target_temperature = shared._target_temp_range if mode == 'range' else shared._target_temperature
        self._action = shared.hvac_state
        # self._min_temperature, self._max_temperature = shared.allowed_temp_range

    @property
    def should_poll(self) -> bool:
        return True

    async def async_added_to_hass(self):
        """Register update signal handler."""

        async def async_update_state():
            """Update device state."""
            await self.async_update_ha_state(True)

        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_NEST_UPDATE, async_update_state))

    @property
    def supported_features(self):
        return self._support_flags

    @property
    def unique_id(self):
        return self.device.serial

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.serial)},
            manufacturer='Nest',
            model='Thermostat',
            name=self.device.description,
            sw_version=self.device.software_version,
        )

    @property
    def name(self):
        return self._name

    # region Temperature Properties

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS
        # return self._temperature_scale

    @property
    def min_temp(self):
        return 9
        # return self._min_temperature

    @property
    def max_temp(self):
        return 32
        # return self._max_temperature

    @property
    def current_temperature(self):
        return self._temperature

    @property
    def target_temperature(self):
        return self._target_temperature if self._mode != NEST_MODE_HEAT_COOL else None

    @property
    def target_temperature_low(self):
        return self._target_temperature[0] if self._mode == NEST_MODE_HEAT_COOL else None

    @property
    def target_temperature_high(self):
        return self._target_temperature[1] if self._mode == NEST_MODE_HEAT_COOL else None

    # endregion

    # region HVAC / Preset / Fan Mode Properties

    @property
    def hvac_modes(self):
        return self._operation_list

    @property
    def hvac_mode(self):
        return MODE_NEST_TO_HASS[self._mode]

    @property
    def hvac_action(self):
        return ACTION_NEST_TO_HASS[self._action]

    @property
    def preset_mode(self):
        return PRESET_AWAY if self._away else PRESET_NONE

    @property
    def preset_modes(self) -> list[PRESET_NONE, PRESET_AWAY]:
        return [PRESET_NONE, PRESET_AWAY]

    @property
    def fan_mode(self):
        if self._has_fan:
            if self._hvac_state == 'fan running':
                return FAN_ON
            else:
                return FAN_MODES_NEST_TO_HASS.get(self._fan_mode)
        # No Fan available so disable slider
        return None

    @property
    def fan_modes(self):
        return self._fan_modes if self._has_fan else None

    # endregion

    # region Setter Methods

    async def _register_state_changed(self):
        self.nest_web_dev.last_command = datetime.now()
        await sleep(5)
        self.schedule_update_ha_state(True)
        await sleep(self.nest_web_dev.refresh_interval.total_seconds() + 0.5)
        self.schedule_update_ha_state(True)

    async def async_set_temperature(self, **kwargs):
        try:
            await self._set_temp(
                kwargs.get(ATTR_TARGET_TEMP_LOW), kwargs.get(ATTR_TARGET_TEMP_HIGH), kwargs.get(ATTR_TEMPERATURE)
            )
        except NestException as e:
            log.error(f'An error occurred while setting temperature: {e}')
        await self._register_state_changed()

    async def _set_temp(self, low, high, temp):
        if self._mode == NEST_MODE_HEAT_COOL and low is not None and high is not None:
            await self.shared.set_temp_range(low, high, convert=False)
        elif temp is not None:
            await self.shared.set_temp(temp, convert=False)
        else:
            log.debug(f'Invalid set_temperature args for mode={self._mode} - {low=} {high=} {temp=}')

    async def async_set_hvac_mode(self, hvac_mode: str):
        await self.shared.set_mode(MODE_HASS_TO_NEST[hvac_mode])
        await self._register_state_changed()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode == self.preset_mode:
            return

        need_away = preset_mode == PRESET_AWAY
        is_away = self._away
        if is_away != need_away:
            await self.structure.set_away(need_away)
            await self._register_state_changed()

    async def async_set_fan_mode(self, fan_mode: str):
        if self._has_fan:
            if fan_mode == FAN_ON:
                await self.device.start_fan()  # TODO: Set/Configure duration
            else:
                await self.device.stop_fan()
            await self._register_state_changed()

    # endregion

    async def async_update(self):
        if await self.nest_web_dev.maybe_refresh():
            self._update_attrs()
