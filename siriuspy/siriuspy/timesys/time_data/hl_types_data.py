"""Define properties of all timing devices and their connections."""

import re as _re
from copy import deepcopy as _dcopy
from siriuspy import servweb as _web
from siriuspy.namesys import SiriusPVName as _PVName
from .connections import Connections


_timeout = 1.0
AC_FREQUENCY = 60
RF_DIVISION = 4
RF_FREQUENCY = 299792458/518.396*864
BASE_FREQUENCY = RF_FREQUENCY / RF_DIVISION
RF_PERIOD = 1/RF_FREQUENCY
BASE_DELAY = 1 / BASE_FREQUENCY
RF_DELAY = BASE_DELAY / 20
FINE_DELAY = 5e-12                  # five picoseconds


class Events:
    """Contain properties of the Events."""

    HL2LL_MAP = {
        'Linac': 'Evt01', 'InjBO': 'Evt02',
        'InjSI': 'Evt03', 'RmpBO': 'Evt04',
        'MigSI': 'Evt05', 'DigLI': 'Evt06',
        'DigTB': 'Evt07', 'DigBO': 'Evt08',
        'DigTS': 'Evt09', 'DigSI': 'Evt10',
        'Orbit': 'Evt11', 'Coupl': 'Evt12',
        'Tunes': 'Evt13', 'Study': 'Evt14'}
    LL2HL_MAP = {val: key for key, val in HL2LL_MAP.items()}

    LL_TMP = 'Evt{0:02d}'
    LL_RGX = _re.compile('Evt([0-9]{2})([a-z-\.]*)', _re.IGNORECASE)
    HL_RGX = _re.compile('('+'|'.join(list(HL2LL_MAP.keys())) +
                         ')([a-z-\.]*)', _re.IGNORECASE)
    HL_PREF = 'AS-Glob:TI-EVG:'

    LL_CODES = list(range(64))
    LL_EVENTS = []
    for i in LL_CODES:
        LL_EVENTS.append(LL_TMP.format(i))

    MODES = ('Disabled', 'Continuous', 'Injection', 'External')
    DELAY_TYPES = ('Fixed', 'Incr')


class Clocks:
    """Contain properties of the Clocks."""

    STATES = ('Dsbl', 'Enbl')

    LL_TMP = 'Clock{0:d}'
    HL_TMP = 'Clock{0:d}'
    HL_PREF = 'AS-Glob:TI-EVG:'

    HL2LL_MAP = dict()
    for i in range(8):
        HL2LL_MAP[HL_TMP.format(i)] = LL_TMP.format(i)
    LL2HL_MAP = {val: key for key, val in HL2LL_MAP.items()}


class Triggers:
    """Contain properties of the triggers."""

    STATES = ('Dsbl', 'Enbl')
    INTLK = ('Dsbl', 'Enbl')
    POLARITIES = ('Normal', 'Inverse')
    DELAY_TYPES = ('Fixed', 'Incr')
    SRC_LL = ('Dsbl',  'Trigger', 'Clock0', 'Clock1', 'Clock2',
              'Clock3', 'Clock4', 'Clock5', 'Clock6', 'Clock7')

    def __init__(self):
        """Initialize the Instance."""
        text = ''
        if _web.server_online():
            text = _web.high_level_triggers(timeout=_timeout)
        # the execution of text will create the HL_TRIGGS variable.
        exec(text)
        self._hl_triggers = locals()['HL_TRIGGS']
        self.check_triggers_consistency()

    @property
    def hl_triggers(self):
        """Dictionary with high level trigger properties."""
        return _dcopy(self._hl_triggers)

    def check_triggers_consistency(self):
        """Check consitency of Triggers definition.

        Check if High Level definition of Triggers is consistent with
        Low Level connections of the timing devices.
        """
        Connections.add_bbb_info()
        Connections.add_crates_info()
        from_evg = Connections.get_connections_from_evg()
        twds_evg = Connections.get_connections_twds_evg()
        for trig, val in self.hl_triggers.items():
            chans = {_PVName(chan) for chan in val['channels']}
            for chan in chans:
                tmp = twds_evg.get(chan)
                if tmp is None:
                    raise Exception(
                        'Device ' + chan +
                        ' defined in the high level trigger ' +
                        trig + ' not specified in timing connections data.')
                if not tmp:
                    raise Exception('Device ' + chan +
                                    ' defined in the high level trigger ' +
                                    trig + ' maybe were already used.')
                up_dev = tmp.pop()
                diff_devs = from_evg[up_dev] - chans
                if diff_devs and not chan.dev.endswith('BPM'):
                    raise Exception(
                        'Devices: ' + ' '.join(diff_devs) +
                        ' are connected to the same output of ' +
                        up_dev + ' as ' + chan +
                        ' but are not related to the sam trigger (' +
                        trig + ').')
