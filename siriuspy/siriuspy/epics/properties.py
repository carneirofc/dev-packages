"""Epics PV derived classes."""

import time as _time
import epics as _epics


class EpicsProperty:
    """Pair of Epics PVs."""

    def __init__(self, name, suffix_sp, suffix_rb,  prefix='',
                 default_value=None):
        """Init."""
        self._name = name
        self._suffix_sp = suffix_sp
        self._suffix_rb = suffix_rb
        self._prefix = prefix
        self._default = default_value
        pvname = self._prefix + self._name
        self._pv_sp = _epics.PV(pvname + self._suffix_sp)
        self._pv_rb = _epics.PV(pvname + self._suffix_rb)

    @property
    def name(self):
        """PV name."""
        return self._name

    @property
    def prefix(self):
        """PV prefix."""
        return self._prefix

    @property
    def suffix_sp(self):
        """PV SP suffix."""
        return self._suffix_sp

    @property
    def suffix_rb(self):
        """PV RB suffix."""
        return self._suffix_rb

    @property
    def pvname_sp(self):
        """Return SP pvname (without prefix)."""
        return self._name + self._suffix_sp

    @property
    def pvname_rb(self):
        """Return RB pvname (without prefix)."""
        return self._name + self._suffix_rb

    @property
    def connected(self):
        """State of connection."""
        return self._pv_sp.connected and self._pv_rb.connected

    @property
    def readback(self):
        """Property readback."""
        return self._pv_rb.value

    @property
    def setpoint(self):
        """Property setpoint."""
        return self._pv_sp.value

    @property
    def default(self):
        """Return default value."""
        return self._default

    @setpoint.setter
    def setpoint(self, value):
        """Set setpoint value."""
        self._pv_sp.value = value

    def set_setpoint_check(self, value, timeout):
        """Set setpoint value and check readback."""
        # setpoint
        self._pv_sp.value = value
        # check
        t0 = _time.time()
        while True:
            if self._pv_rb.value == value:
                return True
            if _time.time() - t0 > timeout:
                return False
            _time.sleep(min(0.1, timeout))

    def reset(self):
        """Reset to default value."""
        if self._default is not None:
            self.setpoint = self._default


class EpicsPropertiesList:
    """List of Epics properties."""

    def __init__(self, properties):
        """Init."""
        self._properties = dict()
        for property in properties:
            self._properties[property.name] = property

    @property
    def connected(self):
        """State of connection."""
        for property in self._properties.values():
            if not property.connected:
                return False
        return True

    @property
    def properties(self):
        """Properties."""
        return sorted(self._properties.keys())

    def get_readback(self, name):
        """Return readback value of a property."""
        property = self._properties[name]
        return property.readback

    def get_setpoint(self, name):
        """Return setpoint value of a property."""
        property = self._properties[name]
        return property.setpoint

    def set_setpoints_check(self, setpoints, timeout):
        """Set setpoints of properties."""
        # setpoints
        for name, value in setpoints.items():
            property = self.__properties[name]
            property.setpoint = value
        # check
        t0 = _time.time()
        while True:
            finished = True
            for pvname, value in setpoints.items():
                property = self._properties[pvname]
                if not property.readback == value:
                    finished = False
                    break
            if finished or _time.time()-t0 > timeout:
                break
            _time.sleep(min(0.1, timeout))
        return finished

    def reset(self):
        """Reset properties to default values."""
        for property in self._properties.values():
            property.reset()

    def reset_check(self, timeout):
        """Reset properties to default values and check."""
        # build setpoints
        setpoints = dict()
        for name, property in self._properties.items():
            setpoints[name] = property.default
        # reset and check
        return self.set_setpoints_check(setpoints, timeout)

    def __getitem__(self, key):
        """Property item."""
        if isinstance(key, int):
            properties = self.properties
            key = properties[key]
        return self._properties[key]
