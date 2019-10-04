"""PRUController.

This module implements classes that are used to do low level BeagleBone
communications, be it with PRU or BSMP requests to power supply controllers
at the other end of the serial line.
"""

from time import sleep as _sleep, time as _time
from copy import deepcopy as _dcopy
from threading import Thread as _Thread
from threading import Lock as _Lock

from siriuspy.bsmp import constants as _const_bsmp
from siriuspy.bsmp import SerialError as _SerialError

from siriuspy.csdevice.pwrsupply import MAX_WFMSIZE as _MAX_WFMSIZE
from siriuspy.csdevice.pwrsupply import DEFAULT_WFMDATA as _DEFAULT_WFMDATA

from .bsmp import __version__ as _devpckg_firmware_version
from .bsmp import MAP_MIRROR_2_ORIG_FBP as _mirror_map_fbp
from .udc import UDC as _UDC
from .psupply import PSupply as _PSupply


# NOTE: On current behaviour of PRUC and Power Supplies:
#
# 01. Currently curve block changes are implemented only upon the arrival of
#     timing trigger that corresponds to the last curve point.
#     This better preserves magnetic history of the magnet while being
#     able to change the curve on the fly.
#
# 02. PRU 'sync_stop' aborts the sync mode right away. Maybe it should be
#     renamed to 'sync_abort' and a new command named 'sync_stop' should be
#     provided that implements abort only at the end of the ramp, thus
#     preserving the magnetic history of the magnets sourced my the power
#     supplies. Without this abort at the end of the ramp, the high level
#     has to be responsible for first turning the 2Hz timing trigger off
#     before switching the power supply off the ramp mode.
#     This is prone to operation errors!
#
# 03. Change of curves on the fly. In order to allow this blocks 0 and 1 of
#     curves will be used in a cyclic way. This should be transparent for
#     users of the PRUController. At this points only one high level curve
#     for each power supply is implemented. Also we have not implemented yet
#     the possibility of changing the curve length.
#
# 04. Discretization of the current-mon can mascarade measurements of update
#     rates. For testing we should add a small random fluctuation.
#
# 05. In Cycle mode, the high level OpMode-Sts (maybe OpMode-Sel too?) is
#     expected to return to SlowRef automatically without changing CurrentRef.
#     In the current firmware version when the controller executes a
#     SELECT_OP_MODE with SlowRef as argument it automatically sets CurrentRef
#     (V_PS_REFERENCE) to the Current-RB (V_PS_SETPOINT). This is a problem
#     after cycling since we want the IOC to move back to SlowRef automatically
#     So the IOC has to set Current-SP to the same value as SigGen's offset
#     before moving the power supply to Cycle mode. This is being done with the
#     current version of the IOC.
#
# 06. While in RmpWfm, MigWfm or SlowRefSync, the PS_I_LOAD variable read from
#     power supplies after setting the last curve point may not be the
#     final value given by PS_REFERENCE. This is due to the fact that the
#     power supply control loop takes some time to converge and the PRU may
#     block serial comm. before it. This is evident in SlowRefSync mode, where
#     reference values may change considerably between two setpoints.

# TODO: discuss with patricia:
#
# 01. What does the 'delay' param in 'PRUserial485.UART_write' mean exactly?
# 02. Request a 'sync_abort' function in the PRUserial485 library.
# 03. Requested new function that reads curves at PRU memory.
#     patricia will work on this.



class PRUController:
    """Beaglebone controller.

    This class implements all basic PRU configuration and BSMP communications
    of the Beaglebone computer connected through a serial line to power supply
    controllers.
    """

    # TODO: test not dcopying self._variables_values in _bsmp_update_variables.
    #       we need to lock up whole section in that function that does
    #       updating of _variables_values, though. Also to lock up other class
    #       properties and methods that access _variables_values or _psc_status
    # TODO: move scan and process threads to BeagleBone objects. With this
    #       change the code will map to the power supply architecture more
    #       naturally.
    # TODO: use specialized Serial exceptions, not general SerialException.
    #
    # NOTE: All private methods starting with '_bsmp' string make a direct
    #       write to the serial line.

    # --- shortcuts, local variables and constants

    _delay_sleep = 0.020  # [s]

    # --- default delays for sync modes
    # This this is delay PRU observes right after finishing writting to UART
    # the BSMP broadcast command 0x0F 'sync_pulse' before processing the UART
    # buffer again. This delay has to be longer than the duration of the
    # controller's response to 'sync_pulse'.

    _delay_func_sync_pulse = 100  # [us]
    _delay_func_set_slowref_fbp = 100  # [us]

    # --- public interface ---

    def __init__(self,
                 pru,
                 prucqueue,
                 psmodel,
                 device_ids,
                 processing=True,
                 scanning=True,
                 reset=True,
                 freqs=None):
        """Init."""
        # create lock
        self._lock = _Lock()

        # store psmodel
        self._psmodel = psmodel

        # sorted list of device ids
        self._device_ids = sorted(device_ids)

        # initialize UDC
        self._udc = None
        self._parms = None
        self._psupplies = dict()
        self._init_udc(pru, self._psmodel.name, self._device_ids)

        # bypass psmodel default frequencies
        if freqs is not None:
            # TODO: this alters const params. check!
            self._parms.FREQ_SCAN = freqs[0]
            self._parms.FREQ_RAMP = freqs[1]

        # set PRU delays
        self._pru_sync_delays = dict()
        self._pru_sync_delays[self._parms.PRU.SYNC_MODE.MIGINT] = None
        self._pru_sync_delays[self._parms.PRU.SYNC_MODE.MIGEND] = \
            PRUController._delay_func_set_slowref_fbp
        self._pru_sync_delays[self._parms.PRU.SYNC_MODE.RMPINT] = None
        self._pru_sync_delays[self._parms.PRU.SYNC_MODE.RMPEND] = \
            PRUController._delay_func_set_slowref_fbp
        self._pru_sync_delays[self._parms.PRU.SYNC_MODE.BRDCST] = \
            PRUController._delay_func_sync_pulse

        # create PRU (sync mode off).
        self._init_pru(pru)

        # reset power supply controllers
        # NOTE: this should be invoked in the case of IOC setting state of HW
        if reset is True:
            self._bsmp_reset_ps_controllers()  # (contains first BSMP comm)

        # update state of PRUController from ps controller
        self._bsmp_init_update()

        # initialize BSMP devices (might contain BSMP comm)
        self._init_devices()

        # operation queue
        self._queue = prucqueue
        # This object if of class DequeThread which invoke BSMP communications
        # using an append-right, pop-left queue. It also processes the next
        # operation in a way as to circumvent the blocking character of UART
        # writes when PRU sync mode is on.
        # Each operation processing is a method invoked as a separate thread
        # since it run write PRU functions that might block code execution,
        # depending on the PRU sync mode. The serial read called and the
        # preceeding write function are supposed to be in a locked scope in
        # order to avoid other write executations to read the respond of
        # previous write executions.

        # define scan thread
        self._dev_idx_last_scanned = \
            len(self._device_ids)-1  # the next will be the first bsmp dev
        self._last_operation = None  # registers last operation
        self._thread_scan = _Thread(target=self._loop_scan, daemon=True)
        self._scanning = scanning

        # define process thread
        self._thread_process = _Thread(target=self._loop_process, daemon=True)
        self._processing = processing

        # after all initializations, threads are started
        self._running = True
        self._thread_scan.start()
        self._thread_process.start()

    # --- properties to read and set controller state and access functions ---

    @property
    def device_ids(self):
        """Device ids."""
        return self._device_ids[:]

    @property
    def scan_interval(self):
        """Scan interval."""
        return self._scan_interval

    @property
    def scanning(self):
        """Return scanning state."""
        return self._scanning

    @scanning.setter
    def scanning(self, value):
        """Set scanning state."""
        self._scanning = value

    @property
    def bsmpcomm(self):
        """Return bsmpcomm state."""
        return self._queue.enabled

    @bsmpcomm.setter
    def bsmpcomm(self, value):
        """Set bsmpcomm state."""
        self._queue.enabled = value

    @property
    def processing(self):
        """Return processing state."""
        return self._processing

    @processing.setter
    def processing(self, value):
        """Set processing state."""
        self._processing = value

    @property
    def queue_length(self):
        """Store number of operations currently in the queue."""
        return len(self._queue)

    @property
    def last_operation(self):
        """Return last operation information."""
        return self._last_operation

    @property
    def params(self):
        """Return PRUController parameters."""
        return self._parms

    @property
    def connected(self):
        """Store connection state."""
        return all((self.check_connected(id) for id in self.device_ids))

    def check_connected(self, device_id):
        """Return connection state of a device."""
        # TODO: may not be the true current connection state
        psupply = self._psupplies[device_id]
        return psupply.connected

    # --- public methods: bbb controller ---

    def disconnect(self):
        """Disconnect to BSMP devices and stop threads."""
        # move PRU sync to off
        self.pru_sync_abort()

        # wait for empty queue
        self._scanning_false_wait_empty_queue()

        # stop processing
        self.processing = False

        # signal threads to finish
        self._running = False

    # --- public methods: bsmp variable read and func exec ---

    def read_variables(self, device_ids, variable_id=None):
        """
        Return device variables.

        Parameters
        ----------
        device_ids : int, tuple or list
            The BSMP device ids.
        variable_id : int or None, optional.
            The BSMP variable id selected. If not passed all device variables
            will be returned.

        Returns
        -------
        Selected BSMP device variable values.

        """
        # process device_ids
        if isinstance(device_ids, int):
            dev_ids = (device_ids, )
        else:
            dev_ids = device_ids

        # NOTE: trial to move state to psupply objects
        # # builds dict of requested values
        # values = dict()
        # for dev_id in dev_ids:
        #     if variable_id is None:
        #         values[dev_id] = self._psupplies[dev_id].variables
        #     else:
        #         values[dev_id] = \
        #             self._psupplies[dev_id].get_variable(variable_id)

        # # make copy
        # with self._lock:
        #     if isinstance(device_ids, int):
        #         return _dcopy(values[device_ids])
        #     return _dcopy(values)

        # gather selected data
        values = dict()
        for id in dev_ids:
            dev_values = self._variables_values[id]
            if variable_id is None:
                values[id] = dev_values
            else:
                values[id] = dev_values[variable_id]

        # get rid of dict, if a single device_id was passed.
        if isinstance(device_ids, int):
            values = values[device_ids]

        # lock and make copy of value
        # TODO: test if locking is really necessary.
        with self._lock:
            values = _dcopy(values)

        return values

    def wfm_update(self, device_ids):
        """Queue update wfm curve."""
        if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF:
            # in PRU sync off mode, append BSM function exec operation to queue
            if isinstance(device_ids, int):
                device_ids = (device_ids, )
            operation = (self._bsmp_wfm_update, (device_ids, ))
            self._queue.append(operation)
            return True
        else:
            # does nothing if PRU sync is on, regardless of sync mode.
            return False

    def wfm_read(self, device_id):
        """Return wfm curve."""
        with self._lock:
            psupply = self._psupplies[device_id]
            return _dcopy(psupply.wfmref_sp)

    def wfm_write(self, device_ids, data):
        """Write wfm curves."""
        if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF:
            # in PRU sync off mode, append BSM function exec operation to queue
            if isinstance(device_ids, int):
                device_ids = (device_ids, )
            operation = (self._bsmp_wfm_write,
                         (device_ids, data))
            self._queue.append(operation)
            return True
        else:
            return False

    def wfmref_read(self, device_id):
        """Return wfm curve."""
        with self._lock:
            psupply = self._psupplies[device_id]
            return _dcopy(psupply.wfmref)

    def wfmmon_read(self, device_id):
        """ Return Wfm-Mon curve."""
        # NOTE: implement this!!!
        with self._lock:
            psupply = self._psupplies[device_id]
            curve = psupply.wfmref[::-1]
            return curve

    def wfmref_index(self, device_id):
        """Return current index into DSP selected curve."""
        # NOTE: change this to use only psupply object, not _variables_values!
        # if not hasattr(self, '_ggg'):
        #     self._ggg = 0
        # else:
        #     self._ggg += 1
        with self._lock:
            psupply = self._psupplies[device_id]
            dev_variables = self._variables_values[device_id]
            curve_id = \
                dev_variables[self.params.CONST_PSBSMP.V_WFMREF_SELECTED]
            if curve_id == 0:
                beg = dev_variables[self.params.CONST_PSBSMP.V_WFMREF0_START]
                end = dev_variables[self.params.CONST_PSBSMP.V_WFMREF0_START]
            else:
                beg = dev_variables[self.params.CONST_PSBSMP.V_WFMREF1_START]
                end = dev_variables[self.params.CONST_PSBSMP.V_WFMREF1_START]
            index = psupply.psbsmp.curve_index_calc(beg, end)
            # return self._ggg
            return index

    def exec_functions(self, device_ids, function_id, args=None):
        """
        Append BSMP function executions to opertations queue.

        Parameters
        ----------
        device_ids : int, tuple or list
            The BSMP device ids. It can be a list of ids or a singe id.
        function_id : int
            The BSMP function id to be executed for the devices.
        args : tuple, optional
            The list of BSMP function argument values

        Returns
        -------
        status : bool
            True is operation was queued or False, if operation was rejected
            because of the PRU sync state.

        """
        if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF:
            # in PRU sync off mode, append BSM function exec operation to queue
            if isinstance(device_ids, int):
                device_ids = (device_ids, )
            if args is None:
                args = (device_ids, function_id)
            else:
                args = (device_ids, function_id, args)
            operation = (self._bsmp_exec_function, args)
            self._queue.append(operation)
            return True
        else:
            # does nothing if PRU sync is on, regardless of sync mode.
            return False

    # --- public methods: access to PRU properties ---

    @property
    def pru_sync_mode(self):
        """PRU sync mode."""
        return self._pru.sync_mode

    @property
    def pru_sync_status(self):
        """PRU sync status."""
        return self._pru.sync_status

    def pru_sync_start(self, sync_mode):
        """Start PRU sync mode.

        Before starting a sync_mode this method does a number of actions:

        01. Checks if requested mode exists. If not, raises NotImplementedError
        02. Moves sync state to off.
        03. Stops scanning device variables
        04. Waits untill all operations in queue are processed.
        05. Executes a final variable scan in the queue.
        06. Start sync in requested mode
        07. Waits untill all operations in queue are processed.
        08. Turn scanning back on again.

        obs: Since operation in queue are processed before changing to
        he new sync mode, this method can safely be invoked right away after
        any other PRUController method, withou any inserted delay.
        """
        # test if sync_mode is valid
        if sync_mode not in self._parms.PRU.SYNC_MODE.ALL:
            self.disconnect()
            raise NotImplementedError('Invalid sync mode {}'.format(
                hex(sync_mode)))

        # try to abandon previous sync mode gracefully
        if self.pru_sync_status != self._parms.PRU.SYNC_STATE.OFF:
            # --- already with sync mode on.
            self.pru_sync_abort()
        else:
            # --- current sync mode is off
            pass

        # wait for all queued operations to be processed
        self.bsmp_scan()
        self._scanning_false_wait_empty_queue()

        # execute a last BSMP read group so that mirror is updated.
        # This is supposedly needed in cases where the last operation
        # in the queue was a function execution.
        # TODO: test this! but is it really necessary?
        self._bsmp_update_variables(self.device_ids,
                                    self._parms.SYNCOFF)
        self._scanning_false_wait_empty_queue()

        # reset curve index
        self._pru.set_curve_pointer(0)

        # set selected sync mode
        self._pru.sync_start(
            sync_mode=sync_mode,
            delay=self._pru_sync_delays[sync_mode],
            sync_address=self._device_ids[0])

        # update time interval according to new sync mode selected
        self._scan_interval = self._get_scan_interval()

        # accept back new operation requests
        self.scanning = True
        self._queue.ignore_clear()

    def pru_sync_stop(self):
        """Stop PRU sync mode."""
        # TODO: should we do more than what is implemented?
        self._pru.sync_stop()  # TODO: implemented as a sync_abort!!!
        self._scan_interval = self._get_scan_interval()

    def pru_sync_abort(self):
        """Force stop PRU sync mode."""
        # TODO: should we do more than what is implemented?
        self._pru.sync_abort()
        self._scan_interval = self._get_scan_interval()

    @property
    def pru_sync_pulse_count(self):
        """PRU sync pulse count."""
        return self._pru.sync_pulse_count

    @property
    def pru_curve_block(self):
        """PRU curves block index."""
        return self._pru.read_curve_block()

    # TODO: since now we have many concurrent PRUController objects in the
    # same process, due to the fact that a single BBB can communicate with
    # more than one UDC, we should move WfmData (curves) to a separate
    # class that maps more naturally to the BBB-PRUC... Maybe in this
    #  process rename PRUController to something like "UDCComm"

    def pru_curve_read(self, device_id):
        """Read curve of a device from PRU memory."""
        # pass reference to curve, not a copy! this is necessary otherwise
        # it is hard to achieve update rate of 10 Hz of the IOC.
        idx = self.device_ids.index(device_id)
        # curve = _dcopy(self._curves[idx])
        curve = self._curves[idx]
        return curve

    def pru_curve_write(self, device_id, curve):
        """Write curve for a device to the correponding PRU memory."""
        # prepare curves, trimming or padding...
        self._curve_set(device_id, curve)
        # write curve to PRU memory
        self._curve_send()

    # --- public methods: access to atomic methods of scan and process loops

    def bsmp_scan(self):
        """Run scan one."""
        # select devices and variable group, defining the read group
        # opertation to be performed
        device_ids, group_id = self._select_device_group_ids()
        operation = (self._bsmp_update_variables,
                     (device_ids, group_id, ))
        if len(self._queue) == 0 or \
           operation != self._queue.last_operation:
            if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF:
                # with sync off, function executions are allowed and
                # therefore operations must be queued in order
                if self.bsmpcomm:
                    # queue operation only if serial is available.
                    self._queue.append(operation)
            else:
                # for sync on, no function execution is accepted and
                # we can therefore append only unique operations since
                # processing order is not relevant.
                if self.bsmpcomm:
                    # queue operation only if serial is reserved.
                    self._queue.append(operation, unique=True)
        else:
            # does not append if last operation is the same as last one
            # operation appended to queue
            pass

    def bsmp_process(self):
        """Run process once."""
        # process first operation in queue, if any and
        # if serial line is available.
        if self.bsmpcomm:
            self._queue.process()

    # --- private methods: initializations ---

    def _scanning_false_wait_empty_queue(self):
        # wait for all queued operations to be processed
        self._queue.ignore_set()  # ignore eventual new operation requests
        self.scanning = False

        while len(self._queue) > 0:
            _sleep(5*self._delay_sleep)  # sleep a little

    def _init_disconnect(self):
        # disconnect method to be used before any operation is on the queue.
        self.scanning = False
        self.processing = False

    def _init_pru(self, pru):

        # create PRU attribute
        self._pru = pru

        # update time interval attribute
        self._scan_interval = self._get_scan_interval()

        # initialize PRU curves
        # TODO: read curves from PRU memory.
        # CON is working in a PRU library that allows this.
        self._curves = [list(_DEFAULT_WFMDATA),  # 1st power supply
                        list(_DEFAULT_WFMDATA),  # 2nd power supply
                        list(_DEFAULT_WFMDATA),  # 3rd power supply
                        list(_DEFAULT_WFMDATA),  # 4th power supply
                        ]

    def _init_udc(self, pru, psmodel_name, device_ids):

        # create UDC
        self._udc = _UDC(pru, psmodel_name, device_ids)
        self._parms = self._udc.prucparms

        # create PSupply objects
        self._init_psupplies(udc=self._udc)

        # prune variables from mirror group
        self._init_prune_mirror_group()

    def _init_psupplies(self, udc):
        for dev_id in self._udc.device_ids:
            psupply = _PSupply(psbsmp=udc[dev_id])
            self._psupplies[dev_id] = psupply

    def _init_devices(self):

        # TODO: should something be done here?
        for dev_id in self._device_ids:
            pass

    def _init_prune_mirror_group(self):

        if self._psmodel.name != 'FBP':
            return

        # gather mirror variables that will be used
        nr_devs = len(self.device_ids)
        var_ids = []
        for var_id in list(self._parms.groups[self._parms.MIRROR]):
            dev_idx, _ = _mirror_map_fbp[var_id]
            if dev_idx <= nr_devs:
                var_ids.append(var_id)

        # prune from mirror group variables not used
        self._parms.groups[self._parms.MIRROR] = tuple(var_ids)

    def _init_check_version(self):
        if not self.connected:
            return
        for dev_id in self.device_ids:
            # V_FIRMWARE_VERSION should be defined for all BSMP devices
            _udc_firmware_version = self._variables_values[dev_id][
                self._parms.CONST_PSBSMP.V_FIRMWARE_VERSION]
            _udc_firmware_version = \
                self._udc.parse_firmware_version(_udc_firmware_version)
            if 'Simulation' not in _udc_firmware_version and \
               _udc_firmware_version != _devpckg_firmware_version:
                self._init_disconnect()
                errmsg = ('Incompatible bsmp implementation version '
                          'for device id:{}')
                print(errmsg.format(dev_id))
                errmsg = 'lib version: {}'
                print(errmsg.format(_devpckg_firmware_version))
                errmsg = 'udc version: {}'
                print(errmsg.format(_udc_firmware_version))
                print()
                # raise ValueError(errmsg)

    def _curve_set(self, device_id, curve):
        """Set PRU curve of a BSMP device."""
        # get index of curve for the given device id
        idx = self.device_ids.index(device_id)

        # if the case, trim or padd existing curves
        curvsize, curvsize0 = len(curve), len(self._curves[idx])
        if curvsize == 0:
            raise ValueError('Invalid empty curve!')
        elif curvsize > _MAX_WFMSIZE:
            raise ValueError('Curve length exceeds maximum value!')
        elif curvsize > curvsize0:
            for curv in self._curves:
                # padd wfmdata with last current value
                curv += [curv[-1], ] * (curvsize - curvsize0)
        elif curvsize < curvsize0:
            for curv in self._curves:
                # trim wfmdata
                del curv[curvsize:]

        # store curve in PRUController attribute
        self._curves[idx] = list(curve)

    def _curve_send(self):
        """Send PRUController curves to PRU."""
        # NOTE: we the current PRU lib version we can deal with only
        # 4 curves for each controller, corresponding to 4 power supply
        # waveforms. If the number of bsmp devices is bigger than 4 and
        # this method is invoked, exception is raised!
        if len(self._device_ids) > 4:
            errmsg = 'Invalid method invocation when number of devs > 4'
            print(errmsg)
            # raise ValueError(errmsg)

        # select in which block the new curve will be stored
        block_curr = self._pru.read_curve_block()
        block_next = 1 if block_curr == 0 else 0

        self._pru.curve(self._curves[0],
                        self._curves[1],
                        self._curves[2],
                        self._curves[3],
                        block_next)
        # TODO: do we need a sleep here?

        # select block to be used at next start of ramp
        self._pru.set_curve_block(block_next)

    # --- private methods: scan and process ---

    def _loop_scan(self):
        while self._running:

            # run scan method once
            if self.scanning and self._scan_interval != 0:
                self.bsmp_scan()

            # update scan interval
            self._scan_interval = self._get_scan_interval()

            # wait for time_interval
            _sleep(self._scan_interval)

    def _loop_process(self):
        while self._running:
            if self.processing:
                self.bsmp_process()

            # sleep a little
            _sleep(self._delay_sleep)

    def _select_device_group_ids(self):
        """Return variable group id and device ids for the loop scan."""
        if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF:
            return self._device_ids, self._parms.SLOWREF
        elif self._pru.sync_mode == self._parms.PRU.SYNC_MODE.MIGEND:
            dev_ids = self._select_next_device_id()
            return dev_ids, self._parms.MIGWFM
        elif self._pru.sync_mode == self._parms.PRU.SYNC_MODE.RMPEND:
            dev_ids = self._select_next_device_id()
            return dev_ids, self._parms.RMPWFM
        elif self._pru.sync_mode == self._parms.PRU.SYNC_MODE.BRDCST:
            return self._device_ids, self._parms.CYCLE
        else:
            self.disconnect()
            raise NotImplementedError('Sync mode not implemented!')

    def _select_next_device_id(self):
        # select device ids to be read (when not in sync_off mode)
        if self._psmodel.name in ('FBP', ):
            # with the mirror var solution for FBP we can always read only
            # one of them and get updates for all the others
            dev_id = self._device_ids[0]
        else:
            # cycle through bsmp devices
            nr_devs = len(self._device_ids)
            dev_idx = (self._dev_idx_last_scanned + 1) % nr_devs
            dev_id = self._device_ids[dev_idx]
            self._dev_idx_last_scanned = dev_idx
        return (dev_id, )

    def _get_scan_interval(self):
        if self.pru_sync_status == self._parms.PRU.SYNC_STATE.OFF or \
           self.pru_sync_mode == self._parms.PRU.SYNC_MODE.BRDCST:
            if self._parms.FREQ_SCAN == 0:
                return 0
            else:
                return 1.0/self._parms.FREQ_SCAN  # [s]
        else:
            if self._parms.FREQ_RAMP == 0:
                return 0
            else:
                return 1.0/self._parms.FREQ_RAMP  # [s]

    def _serial_error(self, device_ids):
        # signal disconnected for device ids.
        for dev_id in device_ids:
            psupply = self._psupplies[dev_id]
            psupply._connected = False

    def _update_copy_var_vals(self, device_id, copy_var_vals, nr_devs,
                              value, group_id, var_id):
        if self._psmodel.name == 'FBP' and group_id == self._parms.MIRROR:
            # TODO: generalize this !
            # --- update from read of group of mirror variables
            #
            # this code assumes that first entry in each mirror
            # variable block corresponds to the device with
            # lowest device_id, the second entry to the second lowest
            # device_id, and so on.
            #
            mir_dev_idx, mir_var_id = _mirror_map_fbp[var_id]
            if mir_dev_idx <= nr_devs:
                mir_dev_id = self.device_ids[mir_dev_idx-1]
                copy_var_vals[mir_dev_id][mir_var_id] = value
        else:
            # --- update from read of other variables groups
            copy_var_vals[device_id][var_id] = value

    def _check_groups(self):
        group_ids = sorted(self._parms.groups.keys())

        # needs to have all default groups
        if len(group_ids) < 3:
            self._init_disconnect()
            raise ValueError(('Invalid variable group definition: '
                              'default group missing!'))
        # needs to have all consecutive groups
        for i in range(len(group_ids)):
            if i not in group_ids:
                self._init_disconnect()
                raise ValueError(('Invalid variable group definition: '
                                  'non-consecutive group ids!'))

    # --- private methods: BSMP UART communications ---

    def _bsmp_reset_ps_controllers(self):

        # turn PRU sync off
        self.pru_sync_abort()

        # initialize variable groups (first BSMP comm.)
        self._bsmp_init_groups()

        # init curves in ps controller
        # NOTE: somehow this is necessary. if curves are not set in
        # initialization, RMPEND does not work! sometimes the ps controllers
        # are put in a non-responsive state!!!

        self.pru_curve_write(self.device_ids[0], self._curves[0])

    def _bsmp_wfm_sizes(self, device_ids):
        time_init = _time()
        sizes = dict()
        try:
            for dev_id in device_ids:
                psbsmp = self._udc[dev_id]
                sizes[dev_id] = psbsmp.wfmref_size
            return sizes
        except (_SerialError, IndexError):
            tstamp = _time()
            dtime = tstamp - time_init
            operation = ('CS', tstamp, dtime, device_ids, True)
            self._last_operation = operation
            self._serial_error(device_ids)

    def _bsmp_wfm_update(self, device_ids):
        """Read curve from devices."""
        time_init = _time()
        with self._lock:
            try:
                for dev_id in device_ids:
                    psupply = self._psupplies[dev_id]
                    psupply.update_wfmref()
            except (_SerialError, IndexError):
                print('bsmp_wfm_update error!')
                tstamp = _time()
                dtime = tstamp - time_init
                operation = ('CR', tstamp, dtime, device_ids, True)
                self._last_operation = operation
                self._serial_error(device_ids)

    def _bsmp_wfm_write(self, device_ids, curve):
        """Write curve to devices."""
        time_init = _time()
        try:
            # write curves
            for dev_id in device_ids:
                # print(dev_id, curve[0])
                psupply = self._psupplies[dev_id]
                curve = psupply.psbsmp.wfmref_write(curve)
                psupply.wfmref_sp = curve
            # update curves
            self._bsmp_wfm_update(device_ids)
        except (_SerialError, IndexError):
            print('bsmp_wfm_write error!')
            tstamp = _time()
            dtime = tstamp - time_init
            operation = ('CW', tstamp, dtime, device_ids, True)
            self._last_operation = operation
            self._serial_error(device_ids)

    def _bsmp_update_variables(self, device_ids, group_id):
        """Read a variable group of device(s).

        This method is inserted in the operation queue my the scanning method.
        values of power supply controller variables read with the BSMP command
        are used to update a mirror state in BBBController of the power
        supplies.

        The method is invoked with two group_ids:

        01. group_id = self._model.SYNCOFF
            Used for 'SlowRef' and 'Cycle' power supply operation modes.

        02. group_id = self._model.MIRROR
            used for 'SlowRefSync', 'RmpWfm' and 'MigWfm' operation modes.
            In this case mirror variables are read from a single device (power
            supply) in order to update a subset of variables for all devices
            at 2 Hz.
        """

        # NOTE: trial to move state to psupply objects
        # print('HERE1')
        # time_init = _time()
        # with self._lock:
        #     try:
        #         for dev_id in device_ids:
        #             psupply = self._psupplies[dev_id]
        #             psupply.update_variables_in_group(group_id=group_id)
        #             print('HERE2')
        #     except (_SerialError, IndexError):
        #         tstamp = _time()
        #         dtime = tstamp - time_init
        #         operation = ('V', tstamp, dtime, device_ids, group_id, True)
        #         self._last_operation = operation
        #         self._serial_error(device_ids)
        #         return
        # return

        ack, data = dict(), dict()
        # --- send requests to serial line
        time_init = _time()
        try:
            for dev_id in device_ids:
                ack[dev_id], data[dev_id] = \
                    self._udc[dev_id].read_group_of_variables(
                        group_id=group_id)
                psupply = self._psupplies[dev_id]
                psupply.update_wfmref(interval=1.0)

            tstamp = _time()
            dtime = tstamp - time_init
            operation = ('V', tstamp, dtime, device_ids, group_id, False)
            self._last_operation = operation
        except (_SerialError, IndexError):
            print('error!!!')
            tstamp = _time()
            dtime = tstamp - time_init
            operation = ('V', tstamp, dtime, device_ids, group_id, True)
            self._last_operation = operation
            self._serial_error(device_ids)
            return

        # --- make copy of state for updating
        with self._lock:
            copy_var_vals = _dcopy(self._variables_values)
            # copy_var_vals = self._variables_values

        # --- update variables, if ack is ok
        nr_devs = len(self.device_ids)
        var_ids = self._parms.groups[group_id]
        for dev_id in device_ids:
            psupply = self._psupplies[dev_id]
            if ack[dev_id] == _const_bsmp.ACK_OK:
                psupply._connected = True
                values = data[dev_id]
                for i, value in enumerate(values):
                    # ===
                    # NOTE: fixit!
                    # When changing from SlowRef to RmpWfm mode in TB-04-PS-CH,
                    # 1. i >= len(var_ids)
                    # 2. WfmData-RB != WfmData_SP
                    # try/exception necessary!
                    try:
                        var_id = var_ids[i]
                    except IndexError:
                        print('device_ids:', device_ids)
                        print('group_id:', group_id)
                        print('i:', i)
                        print('var_ids:', var_ids)
                        print('len(values):', len(values))
                    # ===
                    self._update_copy_var_vals(dev_id, copy_var_vals, nr_devs,
                                               value, group_id, var_id)

                # add random fluctuation to V_I_LOAD variables (tests)
                # in order to avoid measuring wrong update rates due to
                # power supply discretization of current readout.
                # NOTE: turn off added random fluctuations.
                # commenting out this fluctuation cpu usage is reduced from
                # 20% to 19.5% at BBB1
                # if self._psmodel.name == 'FBP':
                #     copy_var_vals[id][self._parms.CONST_PSBSMP.V_I_LOAD] \
                #         += 0.00001*_random.uniform(-1.0, +1.0)
                # elif self._psmodel.name == 'FBP_DCLink':
                #     copy_var_vals[id][self._parms.CONST_PSBSMP.V_V_OUT] \
                #         += 0.00001*_random.uniform(-1.0, +1.0)
                # elif self._psmodel.name == 'FAC':
                #     copy_var_vals[id][self._parms.CONST_PSBSMP.V_I_LOAD1] \
                #         += 0.00001*_random.uniform(-1.0, +1.0)
                #     copy_var_vals[id][self._parms.CONST_PSBSMP.V_I_LOAD2] \
                #         += 0.00001*_random.uniform(-1.0, +1.0)

            elif ack[dev_id] == _const_bsmp.ACK_INVALID_ID:
                psupply._connected = False
                self._bsmp_init_groups()  # NOTE: necessary?!
            else:
                psupply._connected = False

        # --- use updated copy
        self._variables_values = copy_var_vals  # atomic operation


    def _bsmp_exec_function(self, device_ids, function_id, args=None):
        # --- send func exec request to serial line

        # BSMP device's 'execute_function' needs to lock code execution
        # so as to avoid more than one thread reading each other's responses.
        # class BSMP method 'request' should always do that

        ack, data = dict(), dict()

        # --- send requests to serial line
        time_init = _time()
        try:
            for dev_id in device_ids:
                ack[dev_id], data[dev_id] = \
                    self._udc[dev_id].execute_function(function_id, args)
                # check anomalous response
                if data[dev_id] != 0:
                    print('! anomalous response')
                    print('device_id:   {}'.format(dev_id))
                    print('function_id: {}'.format(function_id))
                    print('response:    {}'.format(data[dev_id]))
                # if UDC receives stacking write requests for different power
                # supplies it may respond with anomalous data. a sleep
                # therefore might eliminate this problem.
                if function_id in (0, 1, 2, 3):
                    # print('dev_id:{}, func_id:{}, resp:{}'.format(dev_id,
                    #       function_id, data[dev_id]))
                    # NOTE: sleep really necessary?
                    _sleep(0.020)

        except (_SerialError, IndexError):
            print('SerialError exception in {}'.format(
                ('F', device_ids, function_id, args)))
            return None
        dtime = _time() - time_init
        self._last_operation = ('F', dtime,
                                device_ids, function_id)

        # --- check if all function executions succeeded.
        success = True
        for dev_id in device_ids:
            connected = (ack[dev_id] == _const_bsmp.ACK_OK)
            success &= connected

        if success:
            return data
        else:
            return None

    def _bsmp_init_update(self):

        # initialize variables_values, a mirror state of BSMP devices
        self._bsmp_init_variable_values()

        # initialize ps curves
        self._bsmp_init_wfm()

        # check if ps controller version is compatible with bsmp.py
        self._init_check_version()

        # initialize parameters_values, a mirror state of BSMP devices
        # TODO: finish implementation of _bsmp_init_parameters_values!
        # self._bsmp_init_parameters_values()

    def _bsmp_init_groups(self):
        # check if groups definition is ok
        self._check_groups()

        # create list of variable ids
        var_ids_list = []
        for group_id in sorted(self._parms.groups.keys()):
            var_ids_list.append(self._parms.groups[group_id])

        # reset groups of variables for all bsmp devices
        for dev_id in self._device_ids:
            psupply = self._psupplies[dev_id]
            # reset var groups - first three groups are reserved default groups
            psupply.psbsmp.reset_groups_of_variables(var_ids_list[3:])
            # update psupply state
            psupply.update_groups(var_ids_list)

    def _bsmp_init_wfm(self):
        self._bsmp_wfm_update(self._device_ids)
        for psupply in self._psupplies.values():
            psupply.update_wfmref()
            psupply.wfmref_sp = psupply.wfmref

    def _bsmp_init_variable_values(self):

        # create _variables_values
        gids = sorted(self._parms.groups.keys())
        max_id = max([max(self._parms.groups[gid]) for gid in gids[3:]])
        dev_variables = [None, ] * (1 + max_id)
        with self._lock:
            self._variables_values = \
                {dev_id: dev_variables[:] for dev_id in self._device_ids}

        # read all variable from BSMP devices
        self._bsmp_update_variables(device_ids=self._device_ids,
                                    group_id=self._parms.ALLRELEVANT)

    # def _bsmp_init_parameters_values(self, bsmp_entities):
    #
    #     # create _parameters_values
    #     self._parameters_values = {id: {} for id in self._device_ids}
    #
    #     # read from ps controllers
    #     self._bsmp_update_parameters(device_ids=self._device_ids,
    #                                  parameter_ids=_Parameters.get_eids())

    # def _bsmp_read_parameters(self, device_ids, parameter_ids=None):
    #     # NOTE: this method is not being used yet.
    #     # reads parameters into pdata dictionary
    #     pdata = {id: {pid: [] for pid in parameter_ids} for id in device_ids}
    #     for id in device_ids:
    #         for pid in parameter_ids:
    #             indices = [0]
    #             for idx in indices:
    #                 data = self._bsmp_exec_function(
    #                     (id,), self._parms.CONST_PSBSMP.F_GET_PARAM,
    #                     args=(pid, idx))
    #                 if data[id] is None:
    #                     return None
    #                 else:
    #                     if len(indices) > 1:
    #                         pdata[id][pid].append(data[id])
    #                     else:
    #                         pdata[id][pid] = data[id]
    #
    #     # update _parameters_values
    #     for id in pdata:
    #         for pid in pdata[id]:
    #             self._parameters_values[id][pid] = pdata[id][pid]
