"""Platform for Eforsyning sensor integration."""
from __future__ import annotations
from typing import Any, cast
#from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_NAME
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

import logging
_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN

from homeassistant.const import (TEMP_CELSIUS,
                                 DEVICE_CLASS_ENERGY, DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_GAS, DEVICE_CLASS_MONETARY,
                                 ENERGY_KILO_WATT_HOUR, VOLUME_CUBIC_METERS)
from homeassistant.components.sensor import (SensorEntity, STATE_CLASS_MEASUREMENT, STATE_CLASS_TOTAL,
                                            STATE_CLASS_TOTAL_INCREASING)

import uuid

async def async_setup_entry(
    hass:HomeAssistant,
    config:ConfigEntry,
    async_add_entities:AddEntitiesCallback) -> None:
    """Set up the sensor platform."""
    # Use the name for the unique id of each sensor. eforsyning_<supplierid>?
    #name: str = config.data[CONF_NAME]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config.entry_id]["coordinator"]
    # coordinator has a 'data' field.  This is set to the returned API data value.
    # _async_update_data updates the field.
    # From this field the sensors will get their values afterwards.

    # What data is available here:
    #_LOGGER.fatal(f"Config: {config.as_dict()}")
    
    ## Sensors so far for regional heating data:
    # Year, Month, Day? We'll fetch data once per day.
    # NOTE: Measurement type?
    #   measurement     : The current value, right now.
    #   total           : accumulated in/de-crease of a value. The absolute value is not interesting
    #                     Can be "manually" reset using "last_reset".  Maybe this is useful here along with
    #                     the billing period.
    #   total_increasing: accumulated monotonically increasing value. The absolute value is not interesting
    #                     Also a decreasing value automatically becomes a signal that a new metering cycle has begun.
    # So, for a statistic where the daily, montly or yearly spend is more important than knowing the absolute value
    # then total or total_increasing is good for this.
    # For now well make all of it "measurement", and see how that goes.
    #
    # As the data looks like, the metering data never resets, warranting a "total" + "last_reset" method on the billing date.
    # Using this type makes it possible to follow the use of water and energy rather than the total meter value.
    # Perhaps just make another sensor with this property, so both absolute and aggregated is available (if the other data is not stored)
    #
    #   Temp  - forward temperature (actual measurement)
    #   Temp  - return temperature (actual measurement)
    #   Temp  - Expected return temperature (forecast actual measurement)
    #   Temp  - Measured cooling temperature (difference between forward and return temperatures) (calculation of actual)
    #   ENG1  - Start MWh (absolute)
    #   ENG1  - End MWh (absolute)
    #   ENG1  - Consumption MWh (positive increase)
    #   ENG1  - Expected consumption MWh (forecast positive increase)
    #   ENG1  - Expected End MWh (forecast of absolute)
    #   Water - Start M3 (absolute)
    #   Water - End M3 (asolute)
    #   Water - Consumption M3 (positive increase)
    #   Water - Expected consumption M3 (forecast positive increase)
    #   Water - Expected End M3 (forecast absolute)
    # Extra data (don't know what this is):
    #   ENG2  - Start MWh
    #   ENG2  - End MWh
    #   ENG2  - Consumption MWh
    #   TV2  - Start MWh
    #   TV2  - End MWh
    #   TV2  - Consumption MWh
    # The daily datalog should only be one sensor reading.
    #
    #
    # For Water metering a different set of sensors are necessary:
    #
    #   Water - Start M3 (absolute)
    #   Water - End M3 (absolute)
    #   Water - Consumption M3 (positive increase)
    #   Water - Expected End M3 (forecast absolute)
    #   Water - Total consumption M3 since last billing period (positive increase)
    #   Water - Expected Full Year End Total M3 (forecast positive increase)
    #   Water - Expected Year To Date consumption (positive increase) - This one needs to be calculated from the data.
    #
    # In the JSON these are the data points:
    #   ForbrugsLinjer.TForbrugsLinje[last].TForbrugsTaellevaerk[0].Slut|Start|Forbrug
    #   ForbrugsLinjer.TForbrugsLinje[last].ForventetAflaesningM3|ForventetForbrugM3
    #   IaltLinje.TForbrugsTaellevaerk[0].Forbrug
    #   IaltLinje.ForventetForbrugM3
    #   ForbrugsLinjer.TForbrugsLinje[last].ForventetAflaesningM3 - ForbrugsLinjer.TForbrugsLinje[0].ForventetAflaesningM3

    # The sensors are defined in the const.py file
    sensors: list[EforsyningSensor] = []
    unique_id = "eforsyning-" + str(uuid.uuid3(uuid.NAMESPACE_URL, f"{config.data['username']}-{config.data['supplierid']}"))
    if(config.data['is_water_supply']):
        water_series = {"start", "end", "used", "exp-used", "exp-end", "ytd-used", "exp-ytd-used", "exp-fy-used"}

        for s in water_series:
            sensors.append(EforsyningSensor(f"{config.data['entityname']} Water {s}", "water", s, unique_id, coordinator))
    else:
        temp_series = {"forward", "return", "exp-return", "cooling"}
        energy_series = {"start", "end", "used", "exp-used", "exp-end", "total-used", "use-prognosis"}

        # It is recommended to use a truly unique ID when setting up sensors.  This one uses the entry_id because one could have
        # several accounts at the same supplier.  Also possible is to to use e.g. username+supplierid, but that gets kind of long.
        for s in temp_series:
            sensors.append(EforsyningSensor(f"{config.data['entityname']} Water Temperature {s}", "temp", s, unique_id, coordinator))

        for s in energy_series:
            sensors.append(EforsyningSensor(f"{config.data['entityname']} Energy {s}", "energy", s, unique_id, coordinator))

        for s in energy_series:
            sensors.append(EforsyningSensor(f"{config.data['entityname']} Water {s}", "water", s, unique_id, coordinator))

    sensors.append(EforsyningSensor(f"{config.data['entityname']} Amount Remaining", "amount", "remaining", unique_id, coordinator))
    
    async_add_entities(sensors)


class EforsyningSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor.
       An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available
    """
    def __init__(self, name, sensor_type, sensor_point, unique_id, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attrs: dict[str, Any] = {}

        _LOGGER.debug(f"Registering Sensor for {name}")

        self._sensor_key = f"{sensor_type}-{sensor_point}"
        # All sensors have access to all data in the API.
        self._sensor_data = coordinator.data

        self._attr_name = name
        self._attr_unique_id = f"{unique_id}-{self._sensor_key}"

        if sensor_type == "energy":
            self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
            self._attr_icon = "mdi:lightning-bolt-circle"
            self._attr_device_class = DEVICE_CLASS_ENERGY
            self._attr_state_class = STATE_CLASS_MEASUREMENT #STATE_CLASS_TOTAL_INCREASING or STATE_CLASS_TOTAL
            #self._attr_last_reset = datetime(2000, 1, 1, 0, 0, 0) #JSON: "2000-01-01T00:00:00"
        elif sensor_type == "water":
            self._attr_native_unit_of_measurement = VOLUME_CUBIC_METERS
            self._attr_icon = "mdi:water"
            self._attr_state_class = STATE_CLASS_MEASUREMENT #STATE_CLASS_TOTAL
            # Only gas can be measured in m3
            self._attr_device_class = DEVICE_CLASS_GAS
        elif sensor_type == "temp":
            self._attr_native_unit_of_measurement = TEMP_CELSIUS
            self._attr_icon = "mdi:thermometer"
            self._attr_device_class = DEVICE_CLASS_TEMPERATURE
            self._attr_state_class = STATE_CLASS_MEASUREMENT
        else:
            self._attr_native_unit_of_measurement = "kr"
            self._attr_icon = "mdi:cash-100"
            self._attr_device_class = DEVICE_CLASS_MONETARY
            self._attr_state_class = STATE_CLASS_MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self._sensor_data:
            self._attrs["data"] = self._sensor_data["data"]
            self._attrs["billing"] = self._sensor_data["billing"]
        else:
            self._attrs = {}
        return self._attrs

    @property
    def native_value(self) -> StateType:
        if self._sensor_data:
            return cast(float, self._sensor_data[self._sensor_key])
        else:
            return None

