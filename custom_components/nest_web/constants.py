from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF
from homeassistant.components.climate.const import CURRENT_HVAC_COOL, CURRENT_HVAC_HEAT, CURRENT_HVAC_IDLE
from homeassistant.components.climate.const import CURRENT_HVAC_FAN, PRESET_AWAY, PRESET_ECO, PRESET_NONE
from homeassistant.components.climate.const import FAN_AUTO, FAN_ON, FAN_OFF
from homeassistant.const import TEMP_FAHRENHEIT, TEMP_CELSIUS

DOMAIN = 'nest_web'
DATA_NEST_CONFIG = 'nest_web_config'
SIGNAL_NEST_UPDATE = 'nest_web_update'

TEMP_UNIT_MAP = {'c': TEMP_CELSIUS, 'f': TEMP_FAHRENHEIT}

# Note: Not sure what actual mode values exist other than 'auto'
FAN_MODES_NEST_TO_HASS = {'auto': FAN_AUTO, 'off': FAN_OFF, 'on': FAN_ON}

# region Climate Control
NEST_MODE_HEAT_COOL = 'range'
MODE_HASS_TO_NEST = {
    HVAC_MODE_AUTO: NEST_MODE_HEAT_COOL,
    HVAC_MODE_HEAT: 'heat',
    HVAC_MODE_COOL: 'cool',
    HVAC_MODE_OFF: 'off',
}

MODE_NEST_TO_HASS = {v: k for k, v in MODE_HASS_TO_NEST.items()}
ACTION_NEST_TO_HASS = {
    'off': CURRENT_HVAC_IDLE,
    'heating': CURRENT_HVAC_HEAT,
    'cooling': CURRENT_HVAC_COOL,
    'fan running': CURRENT_HVAC_FAN,
}
PRESET_AWAY_AND_ECO = 'Away and Eco'
PRESET_MODES = [PRESET_NONE, PRESET_AWAY, PRESET_ECO, PRESET_AWAY_AND_ECO]
# endregion
