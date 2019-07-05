"""Define properties of all Linac PVs."""

from copy import deepcopy as _dcopy
from mathphys import constants as _c
import siriuspy.csdevice.util as _cutil
from siriuspy.optics import constants as _oc
from siriuspy.search import HLTimeSearch as _HLTimeSearch


# --- Enumeration Types ---

class ETypes(_cutil.ETypes):
    """Local enumerate types."""
    pass


_et = ETypes  # syntactic sugar


class Const(_cutil.Const):
    """Constants important for the timing system."""

    # FINE_DELAY = 5e-12  # [s] (five picoseconds)

    # TrigSrcLL = _cutil.Const.register('TrigSrcLL', _et.TRIG_SRC_LL)
    PSConvDict = {
        'LA-CN:H1DPPS-1': 'LI-01:PS-Spect',
        'LA-CN:H1FQPS-1': 'LI-Fam:PS-QF1',
        'LA-CN:H1FQPS-2': 'LI-Fam:PS-QF2',
        'LA-CN:H1FQPS-3': 'LI-01:PS-QF3',
        'LA-CN:H1DQPS-1': 'LI-01:PS-QD1',
        'LA-CN:H1DQPS-2': 'LI-01:PS-QD2',
        'LA-CN:H1SCPS-1': 'LI-01:PS-CV-1',
        'LA-CN:H1SCPS-2': 'LI-01:PS-CH-1',
        'LA-CN:H1SCPS-3': 'LI-01:PS-CV-2',
        'LA-CN:H1SCPS-4': 'LI-01:PS-CH-2',
        'LA-CN:H1LCPS-1': 'LI-01:PS-CV-3',
        'LA-CN:H1LCPS-2': 'LI-01:PS-CH-3',
        'LA-CN:H1LCPS-3': 'LI-01:PS-CV-4',
        'LA-CN:H1LCPS-4': 'LI-01:PS-CH-4',
        'LA-CN:H1LCPS-5': 'LI-01:PS-CV-5',
        'LA-CN:H1LCPS-6': 'LI-01:PS-CH-5',
        'LA-CN:H1LCPS-7': 'LI-01:PS-CV-6',
        'LA-CN:H1LCPS-8': 'LI-01:PS-CH-6',
        'LA-CN:H1LCPS-9': 'LI-01:PS-CV-7',
        'LA-CN:H1LCPS-10': 'LI-01:PS-CH-7',
        'LA-CN:H1RCPS-1': 'LI-01:PS-LensRev',
        'LA-CN:H1MLPS-1': 'LI-01:PS-Lens-1',
        'LA-CN:H1MLPS-2': 'LI-01:PS-Lens-2',
        'LA-CN:H1MLPS-3': 'LI-01:PS-Lens-3',
        'LA-CN:H1MLPS-4': 'LI-01:PS-Lens-4',
        'LA-CN:H1SLPS-1': 'LI-01:PS-Slnd-1',
        'LA-CN:H1SLPS-2': 'LI-01:PS-Slnd-2',
        'LA-CN:H1SLPS-3': 'LI-01:PS-Slnd-3',
        'LA-CN:H1SLPS-4': 'LI-01:PS-Slnd-4',
        'LA-CN:H1SLPS-5': 'LI-01:PS-Slnd-5',
        'LA-CN:H1SLPS-6': 'LI-01:PS-Slnd-6',
        'LA-CN:H1SLPS-7': 'LI-01:PS-Slnd-7',
        'LA-CN:H1SLPS-8': 'LI-01:PS-Slnd-8',
        'LA-CN:H1SLPS-9': 'LI-01:PS-Slnd-9',
        'LA-CN:H1SLPS-10': 'LI-01:PS-Slnd-10',
        'LA-CN:H1SLPS-11': 'LI-01:PS-Slnd-11',
        'LA-CN:H1SLPS-12': 'LI-01:PS-Slnd-12',
        'LA-CN:H1SLPS-13': 'LI-01:PS-Slnd-13',
        'LA-CN:H1SLPS-14': 'LI-Fam:PS-Slnd-14',
        'LA-CN:H1SLPS-15': 'LI-Fam:PS-Slnd-15',
        'LA-CN:H1SLPS-16': 'LI-Fam:PS-Slnd-16',
        'LA-CN:H1SLPS-17': 'LI-Fam:PS-Slnd-17',
        'LA-CN:H1SLPS-18': 'LI-Fam:PS-Slnd-18',
        'LA-CN:H1SLPS-19': 'LI-Fam:PS-Slnd-19',
        'LA-CN:H1SLPS-20': 'LI-Fam:PS-Slnd-20',
        'LA-CN:H1SLPS-21': 'LI-Fam:PS-Slnd-21',
    }
    LLRFConvDict = {}


def get_llrf_convpropty(device):
    dic = {
        'B_FREQ': '',
        'GET_AMP': '',
        'GET_CH10_AMP': '',
        'GET_CH10_DELAY': '',
        'GET_CH10_I': '',
        'GET_CH10_PHASE': '',
        'GET_CH10_PHASE_CORR': '',
        'GET_CH10_POWER': '',
        'GET_CH10_Q': '',
        'GET_CH1_AMP': '',
        'GET_CH1_DELAY': '',
        'GET_CH1_I': '',
        'GET_CH1_PHASE': '',
        'GET_CH1_PHASE_CORR': '',
        'GET_CH1_POWER': '',
        'GET_CH1_Q': '',
        'GET_CH1_SETTING_I': '',
        'GET_CH1_SETTING_Q': '',
        'GET_CH2_AMP': '',
        'GET_CH2_DELAY': '',
        'GET_CH2_I': '',
        'GET_CH2_PHASE': '',
        'GET_CH2_PHASE_CORR': '',
        'GET_CH2_POWER': '',
        'GET_CH2_Q': '',
        'GET_CH3_AMP': '',
        'GET_CH3_DELAY': '',
        'GET_CH3_I': '',
        'GET_CH3_PHASE': '',
        'GET_CH3_PHASE_CORR': '',
        'GET_CH3_POWER': '',
        'GET_CH3_Q': '',
        'GET_CH4_AMP': '',
        'GET_CH4_DELAY': '',
        'GET_CH4_I': '',
        'GET_CH4_PHASE': '',
        'GET_CH4_PHASE_CORR': '',
        'GET_CH4_POWER': '',
        'GET_CH4_Q': '',
        'GET_CH5_AMP': '',
        'GET_CH5_DELAY': '',
        'GET_CH5_I': '',
        'GET_CH5_PHASE': '',
        'GET_CH5_PHASE_CORR': '',
        'GET_CH5_POWER': '',
        'GET_CH5_Q': '',
        'GET_CH6_AMP': '',
        'GET_CH6_DELAY': '',
        'GET_CH6_I': '',
        'GET_CH6_PHASE': '',
        'GET_CH6_PHASE_CORR': '',
        'GET_CH6_POWER': '',
        'GET_CH6_Q': '',
        'GET_CH7_AMP': '',
        'GET_CH7_DELAY': '',
        'GET_CH7_I': '',
        'GET_CH7_PHASE': '',
        'GET_CH7_PHASE_CORR': '',
        'GET_CH7_POWER': '',
        'GET_CH7_Q': '',
        'GET_CH8_AMP': '',
        'GET_CH8_DELAY': '',
        'GET_CH8_I': '',
        'GET_CH8_PHASE': '',
        'GET_CH8_PHASE_CORR': '',
        'GET_CH8_POWER': '',
        'GET_CH8_Q': '',
        'GET_CH9_AMP': '',
        'GET_CH9_DELAY': '',
        'GET_CH9_I': '',
        'GET_CH9_PHASE': '',
        'GET_CH9_PHASE_CORR': '',
        'GET_CH9_POWER': '',
        'GET_CH9_Q': '',
        'GET_EXTERNAL_TRIGGER_ENABLE': '',
        'GET_FBLOOP_AMP_CORR': '',
        'GET_FBLOOP_PHASE_CORR': '',
        'GET_FB_MODE': '',
        'GET_FF_MODE': '',
        'GET_INTEGRAL_ENABLE': '',
        'GET_INTERLOCK': '',
        'GET_KI': '',
        'GET_KP': '',
        'GET_PHASE': '',
        'GET_PHASE_DIFF': '',
        'GET_REFL_POWER_LIMIT': '',
        'GET_SHIF_MOTOR_ANGLE': '',
        'GET_SHIF_MOTOR_ANGLE_CALC': '',
        'GET_STREAM': '',
        'GET_TRIGGER_DELAY': '',
        'GET_TRIGGER_STATUS': '',
        'SET_AMP': '',
        'SET_CH10_ATT': '',
        'SET_CH10_DELAY': '',
        'SET_CH10_PHASE_CORR': '',
        'SET_CH1_ADT': '',
        'SET_CH1_ATT': '',
        'SET_CH1_DELAY': '',
        'SET_CH1_PHASE_CORR': '',
        'SET_CH2_ADT': '',
        'SET_CH2_ATT': '',
        'SET_CH2_DELAY': '',
        'SET_CH2_PHASE_CORR': '',
        'SET_CH3_ADT': '',
        'SET_CH3_ATT': '',
        'SET_CH3_DELAY': '',
        'SET_CH3_PHASE_CORR': '',
        'SET_CH4_ADT': '',
        'SET_CH4_ATT': '',
        'SET_CH4_DELAY': '',
        'SET_CH4_PHASE_CORR': '',
        'SET_CH5_ADT': '',
        'SET_CH5_ATT': '',
        'SET_CH5_DELAY': '',
        'SET_CH5_PHASE_CORR': '',
        'SET_CH6_ADT': '',
        'SET_CH6_ATT': '',
        'SET_CH6_DELAY': '',
        'SET_CH6_PHASE_CORR': '',
        'SET_CH7_ADT': '',
        'SET_CH7_ATT': '',
        'SET_CH7_DELAY': '',
        'SET_CH7_PHASE_CORR': '',
        'SET_CH8_ADT': '',
        'SET_CH8_ATT': '',
        'SET_CH8_DELAY': '',
        'SET_CH8_PHASE_CORR': '',
        'SET_CH9_ATT': '',
        'SET_CH9_DELAY': '',
        'SET_CH9_PHASE_CORR': '',
        'SET_EXTERNAL_TRIGGER_ENABLE': '',
        'SET_FBLOOP_AMP_CORR': '',
        'SET_FBLOOP_PHASE_CORR': '',
        'SET_FB_MODE': '',
        'SET_FF_MODE': '',
        'SET_INTEGRAL_ENABLE': '',
        'SET_KI': '',
        'SET_KP': '',
        'SET_PHASE': '',
        'SET_PID_KI': '',
        'SET_PID_KP': '',
        'SET_PID_MODE': '',
        'SET_REFL_POWER_LIMIT': '',
        'SET_SHIF_MOTOR_ANGLE': '',
        'SET_SHIF_MOTOR_ANGLE_CALC': '',
        'SET_STREAM': '',
        'SET_TRIGGER_DELAY': '',
        'SET_VM_ADT': '',
        'WF_ADC1': '',
        'WF_ADC10': '',
        'WF_ADC1_I': '',
        'WF_ADC1_Q': '',
        'WF_ADC2': '',
        'WF_ADC2_I': '',
        'WF_ADC2_Q': '',
        'WF_ADC3': '',
        'WF_ADC3_I': '',
        'WF_ADC3_Q': '',
        'WF_ADC4': '',
        'WF_ADC4_I': '',
        'WF_ADC4_Q': '',
        'WF_ADC5': '',
        'WF_ADC5_I': '',
        'WF_ADC5_Q': '',
        'WF_ADC6': '',
        'WF_ADC6_I': '',
        'WF_ADC6_Q': '',
        'WF_ADC7': '',
        'WF_ADC7_I': '',
        'WF_ADC7_Q': '',
        'WF_ADC8': '',
        'WF_ADC8_I': '',
        'WF_ADC8_Q': '',
        'WF_ADC9': '',
        'WF_ADCX': '',
        'WF_ADCX_I': '',
        'WF_ADCX_Q': '',
    }
    if device.dev.endswith('Kly1'):
        dic['SET_SHIF_MOTOR_ANGLE'] = ''
    elif device.dev.endswith('SHB'):
        chans = tuple(['CH{0:d}'.format(i) for i in [3, 4, 5, 6, 9]])
        dic = {k: v for k, v in dic.items() if not k[4:].startswith(chans)}
        dic = {
            'SET_PID_MODE': '',
            'SET_PID_KP': '',
            'SET_PID_KI': '',
        }
    return dic


def channels_propts(chan_num=1):
    dic = {
        'SET_CH{:d}_ATT': '',
        'SET_CH{:d}_DELAY': '',
        'SET_CH{:d}_PHASE_CORR': '',
    }
    if chan_num <= 8:
        dic['SET_CH{:d}_ADT'] = ''

    if chan_num <= 6:
        dic.update({
            'WF_CH{:d}AMP': '',
            'WF_CH{:d}PHASE': '',
        })
    return dic
