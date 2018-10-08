"""Define functions used to map an epics field to a BSMP entity id.

These classes implement a command interface, that is, they have
an `execute` method.
"""
import time as _time

# BSMP and PS constants
from siriuspy.pwrsupply import bsmp as _bsmp
from siriuspy.csdevice.pwrsupply import Const as _PSConst
from siriuspy.pwrsupply.status import PSCStatus as _PSCStatus

# TODO: check with ELP group how short these delays can be
_delay_turn_on_off = 0.3  # [s]
_delay_loop_open_close = 0.3  # [s]


class Function:
    """Generic function class."""

    def execute(self, value):
        """Execute function."""
        raise NotImplementedError()


class BSMPFunction(Function):
    """Used PRU controller to execute a function."""

    def __init__(self, device_ids, pru_controller, func_id, setpoints=()):
        """Get controller and bsmp function id."""
        self._device_ids = device_ids
        self.pru_controller = pru_controller
        self.func_id = func_id
        self.setpoints = setpoints

    def execute(self, value=None):
        """Execute command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            if value is None:
                self.pru_controller.exec_functions(
                    self._device_ids, self.func_id)
            else:
                self.pru_controller.exec_functions(
                    self._device_ids, self.func_id, value)


class BSMPFunctionNull(BSMPFunction):
    """Do nothing."""

    def __init__(self):
        """Do nothing."""
        super().__init__(None, None, None)

    def execute(self, value):
        """Do nothing."""
        pass


class PRUCurve(Function):
    """Executes a pru curve write command."""

    def __init__(self, device_ids, pru_controller, setpoints=()):
        """Get pru controller."""
        self._device_ids = device_ids
        self.pru_controller = pru_controller
        self.setpoints = setpoints

    def execute(self, value=None):
        """Execute command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            for dev_id in self._device_ids:
                self.pru_controller.pru_curve_write(dev_id, value)


class PSPwrState(Function):
    """Adapter to deal with FBP turn on/off functions."""

    def __init__(self, device_ids, pru_controller, setpoints=None):
        """Define function."""
        self._device_ids = device_ids
        self.turn_on = BSMPFunction(device_ids, pru_controller, 0)
        self.close_loop = BSMPFunction(device_ids, pru_controller, 3)
        self.turn_off = BSMPFunction(device_ids, pru_controller, 1)
        self.setpoints = setpoints

    def execute(self, value=None):
        """Execute Command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            if value == 1:
                self.turn_on.execute()
                _time.sleep(_delay_turn_on_off)
                self.close_loop.execute()
                _time.sleep(_delay_loop_open_close)
            elif value == 0:
                self.turn_off.execute()
                _time.sleep(_delay_turn_on_off)


class PSPwrStateFBP_DCLink(Function):
    """Adapter to deal with FBP_DCLink turn on/off functions."""

    def __init__(self, device_ids, pru_controller, setpoints=None):
        """Define function."""
        self.setpoints = setpoints
        self.turn_on = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_TURN_ON)
        self.turn_off = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_TURN_OFF)
        self.open_loop = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_OPEN_LOOP)

    def execute(self, value=None):
        """Execute Command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            if value == 1:
                self.turn_on.execute()
                _time.sleep(0.3)
                self.open_loop.execute()
            elif value == 0:
                self.turn_off.execute()


class CtrlLoop(Function):
    """Adapter to close or open control loops."""

    def __init__(self, device_ids, pru_controller, setpoints=None):
        """Define function."""
        self.pru_controller = pru_controller
        self.setpoints = setpoints
        self.open_loop = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_OPEN_LOOP)
        self.close_loop = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_CLOSE_LOOP)

    def execute(self, value=None):
        """Execute Command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            if value == 1:
                self.open_loop.execute(None)
                _time.sleep(_delay_loop_open_close)
            elif value == 0:
                self.close_loop.execute(None)
                _time.sleep(_delay_loop_open_close)


class PSOpMode(Function):
    """Decorate a function."""

    def __init__(self, device_ids, function, setpoints=None):
        """Command."""
        self._device_ids = device_ids
        self.function = function
        # Substitute 26 by const value
        self.disable_siggen = \
            BSMPFunction(device_ids, function.pru_controller, 26)
        self.setpoints = setpoints

    def execute(self, value=None):
        """Parse before executing."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            op_mode = value
            if value in (0, 3, 4):
                self._operation_mode = value
                op_mode = 0
            self.function.execute(op_mode + 3)

            if value == _PSConst.OpMode.SlowRef:
                self.disable_siggen.execute(None)


class Current(Function):
    """Command to set current in PSs linked to magnets."""

    def __init__(self, device_ids, pru_controller, setpoints=None):
        """Create command to set current."""
        self._device_ids = device_ids
        self.pru_controller = pru_controller
        self.set_current = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_SET_SLOWREF)
        self.setpoints = setpoints

    def execute(self, value=None):
        """Execute command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            op_modes = [_PSCStatus(self.pru_controller.read_variables(
                device_id, 0)).ioc_opmode for device_id in self._device_ids]
            slowsync = False
            if _PSConst.OpMode.SlowRefSync in op_modes:
                slowsync = True
                self.pru_controller.pru_sync_stop()

            self.set_current.execute(value)

            if slowsync:
                self.pru_controller.pru_sync_start(0x5B)


class Voltage(Function):
    """Command to set voltage in DCLink type PS."""

    def __init__(self, device_ids, pru_controller, setpoints=None):
        """Create command to set voltage."""
        self.device_ids = device_ids
        func_id = _bsmp.ConstBSMP.F_SET_SLOWREF
        self.set_voltage = BSMPFunction(device_ids, pru_controller, func_id)
        self.setpoints = setpoints

    def execute(self, value=None):
        """Execute command."""
        if not self.setpoints or \
                (self.setpoints and self.setpoints.apply(value)):
            self.set_voltage.execute()


class CfgSiggen(Function):
    """Command to configure siggen."""

    def __init__(self, device_ids, pru_controller, idx, setpoints=None):
        """Init."""
        self._idx = idx
        self._setpoints = setpoints
        self._cfg = BSMPFunction(
            device_ids, pru_controller, _bsmp.ConstBSMP.F_CFG_SIGGEN)

    def execute(self, value=None):
        """Execute command."""
        if self._idx == 5:
            if not self._setpoints or \
                    (self._setpoints and self._setpoints.apply(value[self._idx:])):
                self._cfg.execute(value)
        else:
            if not self._setpoints or \
                    (self._setpoints and self._setpoints.apply(value[self._idx])):
                self._cfg.execute(value)