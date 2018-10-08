"""Ramp utility module."""

# nominal strength values
BO_INJECTION_ENERGY = 0.150  # [GeV]
BO_EJECTION_ENERGY = 3.0  # [GeV]

BO_INJECTION_RF_GAPVOLT = 150.0074530757551  # [kV]
BO_EJECTION_RF_GAPVOLT = 950.0  # [kV]

NOMINAL_STRENGTHS = {
    'SI-Fam:MA-B1B2': BO_EJECTION_ENERGY,  # [Energy: GeV]
    'SI-Fam:MA-QFA': +0.7146305692912001,  # [KL: 1/m]
    'SI-Fam:MA-QDA': -0.2270152048045000,  # [KL: 1/m]
    'SI-Fam:MA-QFB': +1.2344424683922000,  # [KL: 1/m]
    'SI-Fam:MA-QDB2': -0.4782973132726601,  # [KL: 1/m]
    'SI-Fam:MA-QDB1': -0.2808906119138000,  # [KL: 1/m]
    'SI-Fam:MA-QFP': +1.2344424683922000,  # [KL: 1/m]
    'SI-Fam:MA-QDP2': -0.4782973132726601,  # [KL: 1/m]
    'SI-Fam:MA-QDP1': -0.2808906119138000,  # [KL: 1/m]
    'SI-Fam:MA-Q1': +0.5631612043340000,  # [KL: 1/m]
    'SI-Fam:MA-Q2': +0.8684629376249999,  # [KL: 1/m]
    'SI-Fam:MA-Q3': +0.6471254242426001,  # [KL: 1/m]
    'SI-Fam:MA-Q4': +0.7867827142062001,  # [KL: 1/m]
    'SI-Fam:MA-SDA0': -12.1250549999999979,  # [SL: 1/m^2]
    'SI-Fam:MA-SDB0': -09.7413299999999996,  # [SL: 1/m^2]
    'SI-Fam:MA-SDP0': -09.7413299999999996,  # [SL: 1/m^2]
    'SI-Fam:MA-SDA1': -24.4479749999999996,  # [SL: 1/m^2]
    'SI-Fam:MA-SDB1': -21.2453849999999989,  # [SL: 1/m^2]
    'SI-Fam:MA-SDP1': -21.3459000000000003,  # [SL: 1/m^2]
    'SI-Fam:MA-SDA2': -13.3280999999999992,  # [SL: 1/m^2]
    'SI-Fam:MA-SDB2': -18.3342150000000004,  # [SL: 1/m^2]
    'SI-Fam:MA-SDP2': -18.3421500000000002,  # [SL: 1/m^2]
    'SI-Fam:MA-SDA3': -20.9911199999999987,  # [SL: 1/m^2]
    'SI-Fam:MA-SDB3': -26.0718599999999974,  # [SL: 1/m^2]
    'SI-Fam:MA-SDP3': -26.1236099999999993,  # [SL: 1/m^2]
    'SI-Fam:MA-SFA0': +7.8854400000000000,  # [SL: 1/m^2]
    'SI-Fam:MA-SFB0': +11.0610149999999994,  # [SL: 1/m^2]
    'SI-Fam:MA-SFP0': +11.0610149999999994,  # [SL: 1/m^2]
    'SI-Fam:MA-SFA1': +28.7742599999999982,  # [SL: 1/m^2]
    'SI-Fam:MA-SFB1': +34.1821950000000001,  # [SL: 1/m^2]
    'SI-Fam:MA-SFP1': +34.3873949999999979,  # [SL: 1/m^2]
    'SI-Fam:MA-SFA2': +22.6153800000000018,  # [SL: 1/m^2]
    'SI-Fam:MA-SFB2': +29.6730900000000020,  # [SL: 1/m^2]
    'SI-Fam:MA-SFP2': +29.7755099999999970,  # [SL: 1/m^2]
    'BO-Fam:MA-B': BO_INJECTION_ENERGY,  # [Energy: GeV]
    'BO-Fam:MA-QD': +0.0011197961538728,  # [KL: 1/m]
    'BO-Fam:MA-QF': +0.3770999232791374,  # [KL: 1/m]
    'BO-Fam:MA-SD': +0.5258382119529604,  # [SL: 1/m^2]
    'BO-Fam:MA-SF': +1.1898514030258744,  # [SL: 1/m^2]
    # TB.V03.01
    'TB-01:MA-QD1': -0.842087961385100,  # [KL: 1/m]
    'TB-01:MA-QF1': 1.314667151220200,  # [KL: 1/m]
    'TB-02:MA-QD2A': -0.500321146547900,  # [KL: 1/m]
    'TB-02:MA-QF2A': 0.678324452901600,  # [KL: 1/m]
    'TB-02:MA-QF2B': 0.289521256650500,  # [KL: 1/m]
    'TB-02:MA-QD2B': -0.298470673153900,  # [KL: 1/m]
    'TB-03:MA-QF3': 0.796303409495700,  # [KL: 1/m]
    'TB-03:MA-QD3': -0.201377480934500,  # [KL: 1/m]
    'TB-04:MA-QF4': 1.152918500326200,  # [KL: 1/m]
    'TB-04:MA-QD4': -0.708409321198300,  # [KL: 1/m]
}













# Power supply ramp parameters
DEFAULT_PS_RAMP_DURATION = 490.0  # [ms]
DEFAULT_PS_RAMP_RAMPUP_START_TIME = 12.743185796449112  # [ms]
DEFAULT_PS_RAMP_RAMPUP_STOP_TIME = 303.87596899224803  # [ms]
DEFAULT_PS_RAMP_RAMPDOWN_START_TIME = 335.24381095273816  # [ms]
DEFAULT_PS_RAMP_RAMPDOWN_STOP_TIME = 470.5176294073518  # [ms]

DEFAULT_PS_RAMP_START_ENERGY = 0.03  # [GeV]
DEFAULT_PS_RAMP_RAMPUP_START_ENERGY = 0.07875  # [GeV]
DEFAULT_PS_RAMP_RAMPUP_STOP_ENERGY = 3.1017857142857137  # [GeV]
DEFAULT_PS_RAMP_PLATEAU_ENERGY = 3.15  # [GeV]
DEFAULT_PS_RAMP_RAMPDOWN_START_ENERGY = 3.0  # [GeV]
DEFAULT_PS_RAMP_RAMPDOWN_STOP_ENERGY = 0.21  # [GeV]


# Timing parameters
DEFAULT_TI_PARAMS_INJECTION_TIME = 19.604901225306328  # [ms]
DEFAULT_TI_PARAMS_EJECTION_TIME = 294.07351837959493  # [ms]

DEFAULT_TI_PARAMS_PS_RAMP_DELAY = 0.0  # [us]
DEFAULT_TI_PARAMS_RF_RAMP_DELAY = DEFAULT_PS_RAMP_RAMPUP_START_TIME  # [us]


# RF ramp parameters
DEFAULT_RF_RAMP_RAMPINC_DURATION = 0.5  # [min]

MAX_RF_RAMP_DURATION = 410.0  # [ms]
DEFAULT_RF_RAMP_BOTTOM_DURATION = 0.0  # [ms]
DEFAULT_RF_RAMP_RAMPUP_DURATION = 300.0  # [ms]
DEFAULT_RF_RAMP_TOP_DURATION = 15.0  # [ms]
DEFAULT_RF_RAMP_RAMPDOWN_DURATION = 90.0  # [ms]
_duration = DEFAULT_RF_RAMP_BOTTOM_DURATION + \
            DEFAULT_RF_RAMP_RAMPUP_DURATION + \
            DEFAULT_RF_RAMP_TOP_DURATION + \
            DEFAULT_RF_RAMP_RAMPDOWN_DURATION
if _duration > MAX_RF_RAMP_DURATION:
    raise ValueError('Invalid RF ramp default durations.')
del(_duration)

# # Linear extrapolation to start and stop rf gap voltages
_t1 = DEFAULT_TI_PARAMS_INJECTION_TIME
_t2 = DEFAULT_TI_PARAMS_EJECTION_TIME
_v1 = BO_INJECTION_RF_GAPVOLT
_v2 = BO_EJECTION_RF_GAPVOLT
_m = (_v2 - _v1)/(_t2 - _t1)
_t = DEFAULT_TI_PARAMS_RF_RAMP_DELAY + DEFAULT_RF_RAMP_BOTTOM_DURATION
DEFAULT_RF_RAMP_BOTTOM_VOLTAGE = _v1 + _m*(_t - _t1)  # [kV]
_t = _t + DEFAULT_RF_RAMP_RAMPUP_DURATION
DEFAULT_RF_RAMP_TOP_VOLTAGE = _v1 + _m*(_t - _t1)  # [kV]
del(_t1, _t2, _v1, _v2, _m, _t)

DEFAULT_RF_RAMP_BOTTOM_PHASE = 0  # [°]
DEFAULT_RF_RAMP_TOP_PHASE = 0  # [°]


def update_nominal_strengths(dic):
    """Update dictionary with nominal values."""
    for k, v in NOMINAL_STRENGTHS.items():
        if k in dic:
            dic[k] = v