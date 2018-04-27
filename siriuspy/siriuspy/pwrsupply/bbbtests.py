"""Tests with BeagleBone."""

import time
import epics
import sys

from siriuspy.bsmp import *
from siriuspy.pwrsupply.pru import PRU
from siriuspy.pwrsupply.bsmp import Const as BSMPConst
from siriuspy.pwrsupply.bsmp import FBPEntities
from siriuspy.pwrsupply.prucontroller import PRUController

P = 'T'

BBB1_device_ids = (1, 2)
BBB2_device_ids = (5, 6)

siggen_config = [
    # --- siggen sine parameters ---
    0,       # type
    10,      # num_cycles
    0.5,     # freq
    2.0,     # amplitude
    0.0,     # offset
    0.0,     # aux_param[0]
    0.0,     # aux_param[1]
    0.0,     # aux_param[2]
    0.0,     # aux_param[3]
]

curve1 = [i*2.0/(4000.0-1.0) for i in range(4000)]


bsmp_cmds = {
    'remove_group': 0x32,
    'execute_function': 0x50,
}

def create_bsmp():

    pru = PRU()
    # msg = Message.message(bsmp_cmds['remove_group'])
    msg = Message.message(bsmp_cmds['execute_function'])
    pck = Package.package(1, msg)
    pru.UART_write(pck.stream, 1000)
    response = pru.UART_read()
    print(response)


def configure_timing_modules(cycle=True):
    """Configure timing devices for Event1."""
    print('Configuring Timing Modules to ' + ('cycle' if cycle else 'ramp'))
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVG:Evt01Mode-Sel', 'External')
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVG:DevEnbl-Sel', 1)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVG:RFDiv-SP', 4)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVR-1:DevEnbl-Sel', 1)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVR-1:OTP08Width-SP', 7000)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVR-1:OTP08State-Sel', 1)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVR-1:OTP08Evt-SP', 1)
    time.sleep(0.1)
    epics.caput(P+'AS-Glob:TI-EVR-1:OTP08Pulses-SP', 1 if cycle else 4000)
    time.sleep(0.1)


def calc_siggen_duration():
    """Calc duration for Sine or DampedSine siggens."""
    num_cycles = siggen_config[1]
    freq = siggen_config[2]
    return num_cycles/freq


def reset_interlocks(pruc):
    """Reset interlocks."""
    # try to reset and then check interlocks
    ids = pruc.device_ids
    pruc.exec_functions(ids, BSMPConst.F_RESET_INTERLOCKS)
    intlck = 0
    for id in ids:
        intlck |= pruc.read_variables(id, BSMPConst.V_PS_HARD_INTERLOCKS)
        intlck |= pruc.read_variables(id, BSMPConst.V_PS_SOFT_INTERLOCKS)
    if intlck:
        raise ValueError('could not reset interlocks!')


def create_pruc():
    """Method."""
    # create BBB controller
    pruc = PRUController(bsmp_entities=FBPEntities(),
                         device_ids=BBB1_device_ids,
                         simulate=False,
                         processing=True,
                         scanning=True)
    return pruc


def init_slowref(pruc):
    """Method."""
    ids = pruc.device_ids

    # set bbb to sync off
    pruc.pru_sync_stop()

    # try to reset and then check interlocks
    reset_interlocks(pruc)

    # turn power supplies on
    pruc.exec_functions(ids, BSMPConst.F_TURN_ON)
    # time.sleep(0.3)  # implemented within PRUController now

    # close loop
    pruc.exec_functions(ids, BSMPConst.F_CLOSE_LOOP)
    # time.sleep(0.3) # implemented within PRUController now

    # disable siggen
    pruc.exec_functions(ids, BSMPConst.F_DISABLE_SIGGEN)

    # set slowref
    pruc.exec_functions(ids,
                        BSMPConst.F_SELECT_OP_MODE,
                        BSMPConst.E_STATE_SLOWREF)

    # current setpoint
    current_sp = 2.5
    pruc.exec_functions(ids, BSMPConst.F_SET_SLOWREF, current_sp)


def config_cycle_mode(pruc):
    """Config siggen and set power supplies to cycle mode."""
    ids = pruc.device_ids

    # set bbb to sync off
    pruc.pru_sync_stop()

    # disable siggen
    pruc.exec_functions(ids, BSMPConst.F_DISABLE_SIGGEN)

    # configure siggen parameters (needs disabled siggen!)
    pruc.exec_functions(ids,
                        BSMPConst.F_CFG_SIGGEN,
                        siggen_config)

    # set ps to cycle mode
    pruc.exec_functions(ids,
                        BSMPConst.F_SELECT_OP_MODE,
                        BSMPConst.E_STATE_CYCLE)


def run_rmpwfm(pruc):
    """Run rmpwfm."""
    # create pruc in deafault config
    init_slowref(pruc)

    # write curve1 to PRu
    pruc.pru_curve_write(1, curve1)

    # enters cycle mode
    pruc.pru_sync_start(sync_mode=pruc.SYNC.RMPEND)

    print('power supply in rmpwfm mode, waiting for sync signal...')


def run_cycle(pruc):
    """Run cycle mode.

    This function prepares PRU and devices so that timing trigger can
    be received and the duration of BSMP command 'sync_pulse', generated by
    PRU upon receiving the timing trigger, can be measured in the oscilloscope.
    """
    id = 1

    # get signal duration
    duration = calc_siggen_duration()

    # create pruc in deafault config
    init_slowref(pruc)

    # read siggen offset and use it as setpoint
    setpoint = pruc.read_variables(id, pruc.BSMP.V_SIGGEN_OFFSET)
    pruc.exec_functions(id, pruc.BSMP.F_SET_SLOWREF, setpoint)

    # configure cycle mode
    config_cycle_mode(pruc)

    # enters cycle mode
    pruc.pru_sync_start(sync_mode=pruc.SYNC.CYCLE)

    # loops until timing trigger is received
    print('waiting for trigger from EVR...', end='')
    sys.stdout.flush()
    while pruc.pru_sync_status == pruc.SYNC.ON:
        t0 = time.time()
        time.sleep(0.1)
    print('arrived.')

    # makes sure power supply is in enable_siggen
    print('waiting for siggen to be enabled...', end='')
    sys.stdout.flush()
    while pruc.read_variables(id, BSMPConst.V_SIGGEN_ENABLE) == 0:
        time.sleep(0.1)
    print('enabled.')

    # loops while cycling
    while time.time() - t0 < duration + 2.0:
        # read iload and siggen
        iload, siggen_enable = {}, {}
        for id2 in pruc.device_ids:
            siggen_enable[id2] = \
                pruc.read_variables(id2, BSMPConst.V_SIGGEN_ENABLE)
            iload[id2] = pruc.read_variables(id2, BSMPConst.V_I_LOAD)

        # print
        print('dtime:{:06.2f}'.format(time.time()-t0), end='')
        print('  -  ', end='')
        print('iload:', end='')
        for id2 in pruc.device_ids:
            print('{:+08.4f} '.format(iload[id2]), end='')
        print('  -  ', end='')
        print('sigge:', end='')
        for id2 in pruc.device_ids:
            print('{} '.format(siggen_enable[id2]), end='')
        print()

        time.sleep(0.1)

    # return to SlowRef mode
    pruc.exec_functions(id,
                        BSMPConst.F_SELECT_OP_MODE,
                        BSMPConst.E_STATE_SLOWREF)


# @staticmethod
# def basic_tests():
#     """Basic."""
#     pru, bsmp = create_bsmp()
#
#
# @staticmethod
# def create_bbb_controller(simulate=False, running=True,
#                           device_ids=BBB1_device_ids):
#     """Return a BBB controller."""
#     pruc = PRUController(bsmp_entities=FBPEntities(),
#                          device_ids=BBB1_device_ids,
#                          simulate=simulate,
#                          processing=running,
#                          scanning=running)
#     return pruc
#
#
# @staticmethod
# def set_rmpwfm_mode_in_power_supplies(pruc):
#     """Config rmpwfm and set power supplies to rmpwfm mode."""
#     ids = pruc.device_ids
#
#     # configure siggen parameters
#     pruc.exec_function(ids, BSMPConst.F_CFG_SIGGEN, siggen_config)
#
#     # disable siggen
#     pruc.exec_function(ids, BSMPConst.F_DISABLE_SIGGEN)
#
#     # set ps to cycle mode
#     pruc.exec_function(ids, BSMPConst.F_SELECT_OP_MODE,
#                        args=(PSConst.States.Cycle,))
#
#
# @staticmethod
# def run_cycle(pruc):
#     """Set cycle_mode in bbb controller."""
#     # get signal duration
#     duration = calc_siggen_duration()
#
#     # set sync on in cycle mode
#     pruc.pru_sync_start(pruc.SYNC.CYCLE)
#     print('waiting to enter cycle mode...')
#     while pruc.pru_sync_status != pruc.SYNC.ON:
#         pass
#
#     # print message
#     print('wainting for timing trigger...')
#
#     # loop until siggen is active
#     not_finished, trigg_not_rcvd = [pruc.pru_sync_status] * 2
#     while not_finished:
#         if pruc.pru_sync_status == 0 and trigg_not_rcvd:
#             trigg_not_rcvd = 0
#             t0 = time.time()
#             print('timing signal arrived!')
#
#         # read iload and siggen
#         iload, siggen_enable = {}, {}
#         for id in pruc.device_ids:
#             siggen_enable[id] = \
#                 pruc.read_variables(id, BSMPConst.V_SIGGEN_ENABLE)
#             iload[id] = pruc.read_variables(id, BSMPConst.V_I_LOAD)
#
#         # print info
#         if not trigg_not_rcvd:
#             # print
#             print('dtime:{:06.2f}'.format(time.time()-t0), end='')
#             print('    -    ', end='')
#             print('iload:', end='')
#             for id in pruc.device_ids:
#                 print('{:+08.4f} '.format(iload[id]), end='')
#             print('    -    ', end='')
#             print('sigge:', end='')
#             for id in pruc.device_ids:
#                 print('{} '.format(siggen_enable[id]), end='')
#             print()
#
#         # test if finished
#         if not trigg_not_rcvd and time.time() - t0 > duration + 2:
#             not_finished = 0
#
#         # sleep a little
#         time.sleep(0.1)
#
#
# @staticmethod
# def run_rmpwfm():
#     """Example of testing rmp mode."""
#     # Example of testing cycle mode for powr supplies in BBB1
#
#     # create BBB1 controller
#     pruc = create_pruc()
#
#     # configure power supplies rmpwfm and set them to run it
#     pruc.exec_function(pruc.device_ids, BSMPConst.F_SELECT_OP_MODE,
#                        args=(PSConst.States.RmpWfm,))
#
#     # set PRU sync mode
#     pruc.pru_sync_start(pruc.SYNC.RMPEND)
#
#
# @staticmethod
# def test_cycle():
#     """Example of testing cycle mode."""
#     # Example of testing cycle mode for powr supplies in BBB1
#
#     # create BBB1 controller
#     pruc = create_bbb_controller()
#
#     # initialized power supplies
#     init_power_supplies(pruc)
#
#     # configure power supplies siggen and set them to run it
#     set_cycle_mode_in_power_supplies(pruc)
#
#     # run cycle
#     run_cycle(pruc)
