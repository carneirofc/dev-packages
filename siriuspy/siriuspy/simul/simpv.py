"""Simulated PV."""


from ..namesys import SiriusPVName as _SiriusPVName
from ..epics.pv_fake import add_to_database as _add_to_database
from ..epics.pv_fake import PVFake as _PVFake
from .simulation import Simulation as _Simulation


class SimPV(_PVFake):
    """."""

    def __new__(cls, pvname, *args, **kwargs):
        """Return existing SimPV object or return a new one."""
        _, _ = args, kwargs  # throwaway arguments
        instance = _Simulation.pv_find(pvname)
        if not instance:
            instance = super(SimPV, cls).__new__(cls)
        return instance

    def __init__(
            self, pvname, **kwargs):
        """."""
        # if object already exists, no initialization needed.
        if _Simulation.pv_find(pvname):
            return

        # --- initializations ---

        # convert string to SiriusPVName
        pvname = _SiriusPVName(pvname)

        # get pv database
        dbase = dict()
        dbase[pvname] = _Simulation.pv_dbase_find(pvname, unique=True)

        # init pv database
        _add_to_database(dbase, '')

        # call base class constructor
        super().__init__(pvname, **kwargs)

        # register SimPV in simulation
        _Simulation.pv_register(self)

    @property
    def value(self):
        """."""
        _ = _Simulation.pv_get(self.pvname)
        return super().get()

    @value.setter
    def value(self, value):
        """."""
        status = _Simulation.pv_put(self.pvname, value)
        if status:
            super().put(value)

    def get(self, **kwargs):
        """."""
        _ = _Simulation.pv_get(self.pvname, **kwargs)
        return super().get(**kwargs)

    def put(self, value, **kwargs):
        """."""
        status = _Simulation.pv_put(self.pvname, value, **kwargs)
        if status:
            super().put(value, **kwargs)

    def get_sim(self):
        """Get SimPV value without invoking simulator callback."""
        return super().get()

    def put_sim(self, value):
        """Set SimPV value without invoking simulator callback."""
        super().put(value)