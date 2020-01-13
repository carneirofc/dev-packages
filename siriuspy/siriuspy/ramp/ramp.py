"""Module with BO ramp and SI mig classes."""

import numpy as _np
from copy import deepcopy as _dcopy

from siriuspy.csdevice.pwrsupply import MAX_WFMSIZE as _MAX_WFMSIZE
from siriuspy.search import PSSearch as _PSSearch
from siriuspy.namesys import SiriusPVName
from siriuspy.clientconfigdb import ConfigDBDocument as _ConfigDBDocument
from siriuspy.magnet.util import \
    get_magnet_family_name as _get_magnet_family_name
from siriuspy.ramp.exceptions import RampError as _RampError, \
    RampInvalidDipoleWfmParms as _RampInvalidDipoleWfmParms, \
    RampInvalidNormConfig as _RampInvalidNormConfig, \
    RampInvalidRFParms as _RampInvalidRFParms
from siriuspy.ramp.util import MAX_RF_RAMP_DURATION as _MAX_RF_RAMP_DURATION, \
    NOMINAL_STRENGTHS as _NOMINAL_STRENGTHS
from siriuspy.ramp.waveform import WaveformDipole as _WaveformDipole, \
    Waveform as _Waveform


class BoosterNormalized(_ConfigDBDocument):
    """Booster normalized configuration."""

    def __init__(self, name=None):
        """Constructor."""
        super().__init__('bo_normalized', name=name)
        self._value = self.get_value_template()
        self._orig_value = None

        self._psnames2index = dict()
        for index, data in enumerate(self._value['pvs']):
            psname = SiriusPVName(data[0]).device_name
            self._psnames2index[psname] = index

    @property
    def psnames(self):
        return list(self._psnames2index.keys())

    def load(self):
        super().load()
        self._orig_value = self.value

    def save(self, **kws):
        super().save(**kws)
        self._orig_value = self.value

    def verify_synchronized(self, psname=None):
        if not self._orig_value:
            return
        modified = False
        for i in range(len(self._value['pvs'])):
            if self._value['pvs'][i][1] != self._orig_value['pvs'][i][1]:
                modified = True
                break
        self._synchronized = not modified

    def _get_item(self, psname):
        index = self._psnames2index[psname]
        value = self._value['pvs'][index][1]
        return float(value)

    def _set_item(self, psname, value):
        """Set configuration item."""
        index = self._psnames2index[psname]
        if self._value['pvs'][index][1] != value:
            self._value['pvs'][index][1] = value
            self.verify_synchronized()

    def _set_value(self, value):
        """Set configuration."""
        if isinstance(value, dict):
            for key, val in value.items():
                if key == 'label':
                    self.name = val
                else:
                    self[key] = val
        else:
            super()._set_value(value)
        self.verify_synchronized()

    def __str__(self):
        """Return string representation of configuration."""
        if not self._value:
            st = 'name: {}'.format(self.name)
            return st
        st = ''
        k = [data[0] for data in self._value['pvs']]
        v1 = [data[1] for data in self._value['pvs']]
        v2 = [data[2] for data in self._value['pvs']]
        maxlen = max(tuple(len(ky) for ky in k) + (len('name'),))
        fmtstr1 = '{:<'+str(maxlen)+'}, {:+.6f}, {:+.6f}\n'
        fmtstr2 = '{:<'+str(maxlen)+'}: {}\n'
        st = fmtstr2.format('name', self.name)
        for i in range(len(k)):
            st += fmtstr1.format(k[i], v1[i], v2[i])
        return st

    def __eq__(self, value):
        for ma in self.manames:
            if ma == 'BO-Fam:MA-B':
                continue
            if not _np.isclose(self[ma], value[ma], atol=1e-5):
                return False
        return True


class BoosterRamp(_ConfigDBDocument):
    """Booster ramp class."""

    PSNAMES = _PSSearch.get_psnames({'sec': 'BO', 'dis': 'PS'})
    PSNAME_DIPOLES = ('BO-Fam:PS-B-1', 'BO-Fam:PS-B-2')
    PSNAME_DIPOLE_REF = PSNAME_DIPOLES[0]

    def __init__(self, name=None, auto_update=False):
        """Constructor."""
        super().__init__('bo_ramp', name=name)
        self._auto_update = auto_update
        self._ps_waveforms = dict()
        self._nominal_strengths = dict()
        self._orig_value = None
        self.value = self.get_value_template()

    # --- ConfigSrv API ---

    def load(self):
        """Load configuration from config server."""
        # load booster ramp configuration
        super().load()
        self._orig_value = self.value
        self._invalidate_ps_waveforms(True)

    def save(self, new_name=None):
        super().save(new_name=new_name)
        self._orig_value = self.value

    # ---- ps_normalized_configs ----

    @property
    def ps_normalized_configs(self):
        """List of ps normalized config."""
        return _dcopy(self._value['ps_normalized_configs*'])

    def ps_normalized_configs_set(self, value):
        """Receive a dict of times as keys and ps2strengths dict as values."""
        self._value['ps_normalized_configs*'] = _dcopy(value)
        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    @property
    def ps_normalized_configs_times(self):
        """Return time instants corresponding to ps normalized configs."""
        return [float(k) for k in self._value['ps_normalized_configs*'].keys()]

    @property
    def ps_normalized_configs_labels(self):
        """Return names corresponding to ps normalized configs."""
        return [n['label'] for n in
                self._value['ps_normalized_configs*'].values()]

    def ps_normalized_configs_delete(self, time):
        """Delete a ps normalized config by its time."""
        self._value['ps_normalized_configs*'].pop('{:.3f}'.format(time))
        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    def ps_normalized_configs_insert(self, time, label='',
                                     psname2strength=dict()):
        """Insert a ps normalized configuration."""
        # verify if there is no config in this time
        otimes = self.ps_normalized_configs_times
        if time in otimes:
            raise _RampInvalidNormConfig(
                'There is already a configuration at this time.')

        # create nconfig data
        nconfig = dict(label=label)
        # interpolate strengths, if necessary
        if not psname2strength:
            psname2strength = dict()
            if otimes:
                for ps in self.PSNAMES:
                    if ps in self.PSNAME_DIPOLES:
                        continue
                    ovalues = list()
                    for t in otimes:
                        str_time = '{:.3f}'.format(t)
                        nc = self._value['ps_normalized_configs*'][str_time]
                        ovalues.append(nc[ps])
                    psname2strength[ps] = _np.interp(time, otimes, ovalues)
            else:
                psname2strength = self.ps_normalized_config_nominal_values
        nconfig.update(psname2strength)
        nconfig = self._update_ps_normalized_config_energy(nconfig, time)
        self._value['ps_normalized_configs*']['{:.3f}'.format(time)] = nconfig

        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    def ps_normalized_configs_change_time(self, time, new_time,
                                          change_energy=False):
        """Change the time of an existing config."""
        otimes = self.ps_normalized_configs_times
        if new_time in otimes:
            raise _RampInvalidNormConfig(
                'There is already a configuration at this time.')
        str_time = '{:.3f}'.format(time)
        str_new_time = '{:.3f}'.format(new_time)

        # set config energy appropriately if needed
        if change_energy:
            self._update_ps_normalized_config_energy(
                self._value['ps_normalized_configs*'][str_time], new_time)

        nconfig = self._value['ps_normalized_configs*'].pop(str_time)
        self._value['ps_normalized_configs*'][str_new_time] = nconfig
        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    def ps_normalized_configs_change_label(self, time, new_label):
        """Change the label of an existing config given its time."""
        str_time = '{:.3f}'.format(time)
        self._value['ps_normalized_configs*'][str_time]['label'] = new_label
        self.verify_synchronized()

    @property
    def ps_normalized_config_nominal_values(self):
        if not self._nominal_strengths:
            psname2strength = dict()
            for ps in self.PSNAMES:
                if ps in _NOMINAL_STRENGTHS:
                    psname2strength[ps] = _NOMINAL_STRENGTHS[ps]
                else:
                    psname2strength[ps] = 0.0
            self._nominal_strengths = psname2strength
        return self._nominal_strengths

    # ---- ps ramp parameters ----

    @property
    def ps_ramp_duration(self):
        """Power supplies ramp duration."""
        return self._value['ps_ramp']['duration']

    @ps_ramp_duration.setter
    def ps_ramp_duration(self, value):
        """Set power supplies duration."""
        value = float(value)
        if value != self._value['ps_ramp']['duration']:
            if not self.ps_ramp_rampdown_stop_time < value:
                raise _RampInvalidDipoleWfmParms(
                    'Invalid duration for waveforms.')
            self._value['ps_ramp']['duration'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_wfm_nrpoints_fams(self):
        """Power supplies waveform number of points."""
        rdip = self._value['ps_ramp']
        return rdip['wfm_nrpoints_fams']

    @ps_ramp_wfm_nrpoints_fams.setter
    def ps_ramp_wfm_nrpoints_fams(self, value):
        """Set power supplies waveform number of points for families."""
        value = int(value)
        rdip = self._value['ps_ramp']
        if value != rdip['wfm_nrpoints_fams']:
            if not 1 <= value <= _MAX_WFMSIZE:
                raise _RampInvalidDipoleWfmParms(
                    'Invalid number of points for waveforms.')
            rdip['wfm_nrpoints_fams'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_wfm_nrpoints_corrs(self):
        """Power supplies waveform number of points for correctors."""
        rdip = self._value['ps_ramp']
        return rdip['wfm_nrpoints_corrs']

    @ps_ramp_wfm_nrpoints_corrs.setter
    def ps_ramp_wfm_nrpoints_corrs(self, value):
        """Set power supplies waveform number of points for correctors."""
        value = int(value)
        rdip = self._value['ps_ramp']
        if value != rdip['wfm_nrpoints_corrs']:
            if not 1 <= value <= _MAX_WFMSIZE:
                raise _RampInvalidDipoleWfmParms(
                    'Invalid number of points for waveforms.')
            rdip['wfm_nrpoints_corrs'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_times(self):
        """Return ps ramp times."""
        v = (self.ps_ramp_rampup1_start_time,
             self.ps_ramp_rampup2_start_time,
             self.ps_ramp_rampdown_start_time,
             self.ps_ramp_rampdown_stop_time)
        return v

    @property
    def ps_ramp_energies(self):
        """Return ps ramp times."""
        v = (self.ps_ramp_rampup1_start_energy,
             self.ps_ramp_rampup2_start_energy,
             self.ps_ramp_rampdown_start_energy,
             self.ps_ramp_rampdown_stop_energy)
        return v

    @property
    def ps_ramp_start_energy(self):
        """Return."""
        return self._value['ps_ramp']['start_energy']

    @ps_ramp_start_energy.setter
    def ps_ramp_start_energy(self, value):
        """Return."""
        value = float(value)
        rdip = self._value['ps_ramp']
        if value != rdip['start_energy']:
            w = self._create_new_ps_waveform_dipole()
            w.start_energy = value
            rdip['start_energy'] = w.start_energy
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup1_start_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampup1_start_energy']

    @ps_ramp_rampup1_start_energy.setter
    def ps_ramp_rampup1_start_energy(self, value):
        """Return."""
        value = float(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampup1_start_energy']:
            w = self._create_new_ps_waveform_dipole()
            w.rampup1_start_energy = value
            rdip['rampup1_start_energy'] = w.rampup1_start_energy
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup1_start_time(self):
        """Return."""
        return self._value['ps_ramp']['rampup1_start_time']

    @ps_ramp_rampup1_start_time.setter
    def ps_ramp_rampup1_start_time(self, value):
        """Return."""
        self._check_valid_time(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampup1_start_time']:
            rdip['rampup1_start_time'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup1_slope(self):
        """Return rampup1 slope."""
        self._update_ps_waveform(self.PSNAME_DIPOLE_REF)
        return self._ps_waveforms[self.PSNAME_DIPOLE_REF].rampup1_slope

    @property
    def ps_ramp_rampup2_start_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampup2_start_energy']

    @ps_ramp_rampup2_start_energy.setter
    def ps_ramp_rampup2_start_energy(self, value):
        """Return."""
        value = float(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampup2_start_energy']:
            w = self._create_new_ps_waveform_dipole()
            w.rampup2_start_energy = value
            rdip['rampup2_start_energy'] = w.rampup2_start_energy
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup2_start_time(self):
        """Return."""
        return self._value['ps_ramp']['rampup2_start_time']

    @ps_ramp_rampup2_start_time.setter
    def ps_ramp_rampup2_start_time(self, value):
        """Return."""
        self._check_valid_time(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampup2_start_time']:
            rdip['rampup2_start_time'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup2_slope(self):
        """Return rampup2 slope."""
        self._update_ps_waveform(self.PSNAME_DIPOLE_REF)
        return self._ps_waveforms[self.PSNAME_DIPOLE_REF].rampup2_slope

    @property
    def ps_ramp_rampup_smooth_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampup_smooth_energy']

    @ps_ramp_rampup_smooth_energy.setter
    def ps_ramp_rampup_smooth_energy(self, value):
        """Return."""
        rdip = self._value['ps_ramp']
        if value != rdip['rampup_smooth_energy']:
            rdip['rampup_smooth_energy'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampup_smooth_intvl(self):
        """Return."""
        return self._value['ps_ramp']['rampup_smooth_intvl']

    @ps_ramp_rampup_smooth_intvl.setter
    def ps_ramp_rampup_smooth_intvl(self, value):
        """Return."""
        rdip = self._value['ps_ramp']
        if value != rdip['rampup_smooth_intvl']:
            rdip['rampup_smooth_intvl'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_start_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_start_energy']

    @ps_ramp_rampdown_start_energy.setter
    def ps_ramp_rampdown_start_energy(self, value):
        """Return."""
        value = float(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_start_energy']:
            w = self._create_new_ps_waveform_dipole()
            w.rampdown_start_energy = value
            rdip['rampdown_start_energy'] = w.rampdown_start_energy
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_start_time(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_start_time']

    @ps_ramp_rampdown_start_time.setter
    def ps_ramp_rampdown_start_time(self, value):
        """Return."""
        self._check_valid_time(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_start_time']:
            rdip['rampdown_start_time'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_stop_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_stop_energy']

    @ps_ramp_rampdown_stop_energy.setter
    def ps_ramp_rampdown_stop_energy(self, value):
        """Return."""
        value = float(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_stop_energy']:
            w = self._create_new_ps_waveform_dipole()
            w.rampdown_stop_energy = value
            rdip['rampdown_stop_energy'] = w.rampdown_stop_energy
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_stop_time(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_stop_time']

    @ps_ramp_rampdown_stop_time.setter
    def ps_ramp_rampdown_stop_time(self, value):
        """Return."""
        self._check_valid_time(value)
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_stop_time']:
            rdip['rampdown_stop_time'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_slope(self):
        """Return rampup2 slope."""
        self._update_ps_waveform(self.PSNAME_DIPOLE_REF)
        return self._ps_waveforms[self.PSNAME_DIPOLE_REF].rampdown_slope

    @property
    def ps_ramp_rampdown_smooth_energy(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_smooth_energy']

    @ps_ramp_rampdown_smooth_energy.setter
    def ps_ramp_rampdown_smooth_energy(self, value):
        """Return."""
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_smooth_energy']:
            rdip['rampdown_smooth_energy'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    @property
    def ps_ramp_rampdown_smooth_intvl(self):
        """Return."""
        return self._value['ps_ramp']['rampdown_smooth_intvl']

    @ps_ramp_rampdown_smooth_intvl.setter
    def ps_ramp_rampdown_smooth_intvl(self, value):
        """Return."""
        rdip = self._value['ps_ramp']
        if value != rdip['rampdown_smooth_intvl']:
            rdip['rampdown_smooth_intvl'] = value
            self.verify_synchronized()
            self._invalidate_ps_waveforms(True)

    # ---- rf ramp parameters ----

    @property
    def rf_ramp_duration(self):
        """RF ramp duration."""
        d = self.rf_ramp_bottom_duration + \
            self.rf_ramp_rampup_duration + \
            self.rf_ramp_top_duration + \
            self.rf_ramp_rampdown_duration
        return d

    @property
    def rf_ramp_times(self):
        """Time instants to define RF ramp."""
        t = (self.ti_params_rf_ramp_delay,      # = RF ramp start, bottom start
             self.rf_ramp_rampup_start_time,    # = RF bottom stop
             self.rf_ramp_rampup_stop_time,     # = RF top start
             self.rf_ramp_rampdown_start_time,  # = RF top stop
             self.rf_ramp_duration)             # = RF rampdown stop
        return t

    @property
    def rf_ramp_voltages(self):
        """List of voltages to define RF ramp."""
        v = (self.rf_ramp_bottom_voltage,
             self.rf_ramp_bottom_voltage,
             self.rf_ramp_top_voltage,
             self.rf_ramp_top_voltage,
             self.rf_ramp_bottom_voltage)
        return v

    @property
    def rf_ramp_phases(self):
        """List of phases to define RF ramp."""
        p = (self.rf_ramp_bottom_phase,
             self.rf_ramp_bottom_phase,
             self.rf_ramp_top_phase,
             self.rf_ramp_top_phase,
             self.rf_ramp_bottom_phase)
        return p

    def rf_ramp_interp_voltages(self, time):
        """Return voltages related to times."""
        v = _np.interp(time, self.rf_ramp_times, self.rf_ramp_voltages)
        return v

    @property
    def rf_ramp_rampup_start_time(self):
        """RF ramp rampup start time."""
        t = self.ti_params_rf_ramp_delay + \
            float(self._value['rf_ramp']['bottom_duration'])
        return t

    @rf_ramp_rampup_start_time.setter
    def rf_ramp_rampup_start_time(self, value):
        value = float(value)
        if value == self.rf_ramp_rampup_start_time:
            return
        if not self.ti_params_rf_ramp_delay <= value < \
                self.rf_ramp_rampup_stop_time:
            raise _RampInvalidRFParms('Invalid rampup start time.')

        delay = self.ti_params_rf_ramp_delay
        rampup_stop_time = self.rf_ramp_rampup_stop_time
        self._value['rf_ramp']['bottom_duration'] = \
            value - delay
        self._value['rf_ramp']['rampup_duration'] = \
            rampup_stop_time - value
        self.verify_synchronized()

    @property
    def rf_ramp_rampup_stop_time(self):
        """RF ramp rampup stop time."""
        t = self.ti_params_rf_ramp_delay + \
            float(self._value['rf_ramp']['bottom_duration']) + \
            float(self._value['rf_ramp']['rampup_duration'])
        return t

    @rf_ramp_rampup_stop_time.setter
    def rf_ramp_rampup_stop_time(self, value):
        value = float(value)
        if value == self.rf_ramp_rampup_stop_time:
            return
        if not self.rf_ramp_rampup_start_time < value <= \
                self.rf_ramp_rampdown_start_time:
            raise _RampInvalidRFParms('Invalid rampup stop time.')

        rampup_start_time = self.rf_ramp_rampup_start_time
        rampdown_start_time = self.rf_ramp_rampdown_start_time
        self._value['rf_ramp']['rampup_duration'] = \
            value - rampup_start_time
        self._value['rf_ramp']['top_duration'] = \
            rampdown_start_time - value
        self.verify_synchronized()

    @property
    def rf_ramp_rampdown_start_time(self):
        """RF ramp rampdown start time."""
        t = self.ti_params_rf_ramp_delay + \
            float(self._value['rf_ramp']['bottom_duration']) + \
            float(self._value['rf_ramp']['rampup_duration']) + \
            float(self._value['rf_ramp']['top_duration'])
        return t

    @rf_ramp_rampdown_start_time.setter
    def rf_ramp_rampdown_start_time(self, value):
        value = float(value)
        if value == self.rf_ramp_rampdown_start_time:
            return
        if not self.rf_ramp_rampup_stop_time <= value < \
                self.rf_ramp_rampdown_stop_time:
            raise _RampInvalidRFParms('Invalid rampdown start time.')

        rampup_stop_time = self.rf_ramp_rampup_stop_time
        rampdown_stop_time = self.rf_ramp_rampdown_stop_time
        self._value['rf_ramp']['top_duration'] = \
            value - rampup_stop_time
        self._value['rf_ramp']['rampdown_duration'] = \
            rampdown_stop_time - value
        self.verify_synchronized()

    @property
    def rf_ramp_rampdown_stop_time(self):
        """RF ramp rampdown start time."""
        t = self.ti_params_rf_ramp_delay + \
            float(self._value['rf_ramp']['bottom_duration']) + \
            float(self._value['rf_ramp']['rampup_duration']) + \
            float(self._value['rf_ramp']['top_duration']) + \
            float(self._value['rf_ramp']['rampdown_duration'])
        return t

    @rf_ramp_rampdown_stop_time.setter
    def rf_ramp_rampdown_stop_time(self, value):
        value = float(value)
        if value == self.rf_ramp_rampdown_stop_time:
            return
        if not self.rf_ramp_rampdown_start_time < value <= \
                self.ti_params_rf_ramp_delay + _MAX_RF_RAMP_DURATION:
            raise _RampInvalidRFParms('Invalid rampdown stop time.')

        rampdown_start_time = self.rf_ramp_rampdown_start_time
        self._value['rf_ramp']['rampdown_duration'] = \
            value - rampdown_start_time
        self.verify_synchronized()

    @property
    def rf_ramp_bottom_duration(self):
        """Bottom duration, in ms."""
        return self._value['rf_ramp']['bottom_duration']

    @property
    def rf_ramp_rampup_duration(self):
        """Rampup duration, in ms."""
        return self._value['rf_ramp']['rampup_duration']

    @property
    def rf_ramp_top_duration(self):
        """Top duration, in ms."""
        return self._value['rf_ramp']['top_duration']

    @property
    def rf_ramp_rampdown_duration(self):
        """Rampdown duration, in ms."""
        return self._value['rf_ramp']['rampdown_duration']

    @property
    def rf_ramp_bottom_voltage(self):
        """RF ramp bottom voltage, in kV."""
        return self._value['rf_ramp']['bottom_voltage']

    @rf_ramp_bottom_voltage.setter
    def rf_ramp_bottom_voltage(self, value):
        value = float(value)
        if value == self._value['rf_ramp']['bottom_voltage']:
            return
        if not 0 <= value <= self.rf_ramp_top_voltage:
            raise _RampInvalidRFParms('Invalid value to bottom voltage.')

        self._value['rf_ramp']['bottom_voltage'] = value
        self.verify_synchronized()

    @property
    def rf_ramp_top_voltage(self):
        """RF ramp top voltage, in kV."""
        return self._value['rf_ramp']['top_voltage']

    @rf_ramp_top_voltage.setter
    def rf_ramp_top_voltage(self, value):
        value = float(value)
        if value == self._value['rf_ramp']['top_voltage']:
            return
        if not value >= self._value['rf_ramp']['bottom_voltage']:
            raise _RampInvalidRFParms('Invalid value to top voltage.')

        self._value['rf_ramp']['top_voltage'] = value
        self.verify_synchronized()

    @property
    def rf_ramp_bottom_phase(self):
        """RF ramp bottom phase, in degrees."""
        return self._value['rf_ramp']['bottom_phase']

    @rf_ramp_bottom_phase.setter
    def rf_ramp_bottom_phase(self, value):
        value = float(value)
        if value == self._value['rf_ramp']['bottom_phase']:
            return
        if not -180 < value < 360:
            raise _RampInvalidRFParms('Invalid value to bottom phase.')

        self._value['rf_ramp']['bottom_phase'] = value
        self.verify_synchronized()

    @property
    def rf_ramp_top_phase(self):
        """RF ramp top phase, in degrees."""
        return self._value['rf_ramp']['top_phase']

    @rf_ramp_top_phase.setter
    def rf_ramp_top_phase(self, value):
        value = float(value)
        if value == self._value['rf_ramp']['top_phase']:
            return
        if not -180 < value < 360:
            raise _RampInvalidRFParms('Invalid value to top phase.')

        self._value['rf_ramp']['top_phase'] = value
        self.verify_synchronized()

    # --- timing parameters ---

    @property
    def ti_params_injection_time(self):
        """Injection time instant."""
        return float(self._value['ti_params']['injection_time'])

    @ti_params_injection_time.setter
    def ti_params_injection_time(self, value):
        """Set injection time instant."""
        # TODO: verify value
        if value == self._value['ti_params']['injection_time']:
            return
        self._value['ti_params']['injection_time'] = value
        self.verify_synchronized()

    @property
    def ti_params_ejection_time(self):
        """Ejection time instant."""
        return float(self._value['ti_params']['ejection_time'])

    @ti_params_ejection_time.setter
    def ti_params_ejection_time(self, value):
        """Set ejection time instant."""
        # TODO: verify value
        if value == self._value['ti_params']['ejection_time']:
            return
        self._value['ti_params']['ejection_time'] = value
        self.verify_synchronized()

    @property
    def ti_params_ps_ramp_delay(self):
        """PS ramp delay."""
        return float(self._value['ti_params']['ps_ramp_delay'])

    @ti_params_ps_ramp_delay.setter
    def ti_params_ps_ramp_delay(self, value):
        """Set ps ramp delay [us]."""
        value = float(value)
        if value == self._value['ti_params']['ps_ramp_delay']:
            return
        self._value['ti_params']['ps_ramp_delay'] = value
        self.verify_synchronized()

    @property
    def ti_params_rf_ramp_delay(self):
        """RF delay."""
        return float(self._value['ti_params']['rf_ramp_delay'])

    @ti_params_rf_ramp_delay.setter
    def ti_params_rf_ramp_delay(self, value):
        """Set RF ramp delay [us]."""
        # TODO: verify value
        if value == self._value['ti_params']['rf_ramp_delay']:
            return
        self._value['ti_params']['rf_ramp_delay'] = value
        self.verify_synchronized()

    # --- API for waveforms ---

    @property
    def ps_waveform_psnames_exclimits(self):
        """Return a list of psnames whose waveform exceeds current limits."""
        if not self._value['ps_normalized_configs*']:
            psnames = list(self.PSNAME_DIPOLES)
        else:
            psnames = self.PSNAMES
        psnames_exclimits = list()
        for psname in psnames:
            self._update_ps_waveform(psname)
            w_currents = self._ps_waveforms[psname].currents
            isNan = _np.any(_np.isnan(w_currents))
            isInf = _np.any(_np.isinf(w_currents))
            if isNan or isInf:
                continue
            limits = _PSSearch.conv_psname_2_splims(psname)
            highlim = limits['HOPR'] if psname not in self.PSNAME_DIPOLES \
                else 1072
            lowlim = limits['LOPR']
            if _np.any(w_currents > highlim) or _np.any(w_currents < lowlim):
                psnames_exclimits.append(psname)
        return psnames_exclimits

    def ps_waveform_get(self, psname):
        """Return ps waveform for a given power supply."""
        if psname not in self.PSNAME_DIPOLES and \
                not self._value['ps_normalized_configs*']:
            raise _RampError('There is no normalized cofiguration defined!')
        self._update_ps_waveform(psname)
        waveform = self._ps_waveforms[psname]
        return waveform

    def ps_waveform_set(self, psname, waveform):
        """Set ps waveform for a given power supply."""
        self._ps_waveforms[psname] = _dcopy(waveform)

    def ps_waveform_get_times(self, psname):
        """Return ramp energy at a given time."""
        self._update_ps_waveform(psname)
        times = self._ps_waveforms[psname].times
        return times

    def ps_waveform_get_currents(self, psname):
        """Return ps waveform current for a given power supply."""
        if not self._value['ps_normalized_configs*'] and \
                psname not in self.PSNAME_DIPOLES:
            raise _RampError('There is no normalized cofiguration defined!')
        self._update_ps_waveform(psname)
        waveform = self._ps_waveforms[psname]
        return waveform.currents.copy()

    def ps_waveform_get_strengths(self, psname):
        """Return ps waveform strength for a given power supply."""
        if not self._value['ps_normalized_configs*'] and \
                psname not in self.PSNAME_DIPOLES:
            raise _RampError('There is no normalized cofiguration defined!')
        self._update_ps_waveform(psname)
        waveform = self._ps_waveforms[psname]
        return waveform.strengths.copy()

    def ps_waveform_interp_time(self, energy):
        """Return ps ramp time at a given energy.
        Use only energies until rampdown-start time.
        """
        rampdown_start_time = self.ps_ramp_rampdown_start_time
        times = [t for t in self.ps_waveform_get_times(self.PSNAME_DIPOLE_REF)
                 if t < rampdown_start_time]
        energies = self._ps_waveforms[self.PSNAME_DIPOLE_REF].strengths[
                 0:len(times)]
        time = _np.interp(energy, energies, times)
        return time

    def ps_waveform_interp_strengths(self, psname, time):
        """Return ps ramp strength at a given time."""
        if not self._value['ps_normalized_configs*'] and \
                psname not in self.PSNAME_DIPOLES:
            raise _RampError('There is no normalized cofiguration defined!')
        self._update_ps_waveform(psname)
        times = self.ps_waveform_get_times(psname)
        strengths = self._ps_waveforms[psname].strengths
        strength = _np.interp(time, times, strengths)
        return strength

    def ps_waveform_interp_currents(self, psname, time):
        """Return ps ramp current at a given time."""
        if not self._value['ps_normalized_configs*'] and \
                psname not in self.PSNAME_DIPOLES:
            raise _RampError('There is no normalized cofiguration defined!')
        self._update_ps_waveform(psname)
        times = self.ps_waveform_get_times(psname)
        currents = self._ps_waveforms[psname].currents
        current = _np.interp(time, times, currents)
        return current

    def ps_waveform_interp_energy(self, time):
        """Return ps ramp energy at a given time."""
        return self.ps_waveform_interp_strengths(self.PSNAME_DIPOLE_REF, time)

    def verify_synchronized(self):
        if not self._orig_value:
            # print('no original value to compare')
            return
        modified = False
        for group, params in self._orig_value.items():
            if not params:
                if self._value[group]:
                    modified = True
                    # print('now, it has configs', self._value[group].keys())
                    break
                else:
                    # print('do not have configs')
                    continue
            if self._orig_value[group].keys() != self._value[group].keys():
                modified = True
                # print('has different keys',
                #       self._orig_value[group].keys(),
                #       self._value[group].keys())
                break
            for param, value in params.items():
                if self._value[group][param] != value:
                    modified = True
                    # print('has params with different values',
                    #       self._value[group][param], value)
                    break
        self._synchronized = not modified

    def verify_ps_normalized_synchronized(self, time, value=None):
        str_time = '{:.3f}'.format(time)
        if not self._orig_value:
            return False
        if str_time not in self._orig_value['ps_normalized_configs*'].keys():
            return False
        o = self._orig_value['ps_normalized_configs*'][str_time]
        c = value if value is not None else \
            self._value['ps_normalized_configs*'][str_time]
        return o == c

    # --- private methods ---

    def __len__(self):
        """Return number of ps normalized configurations."""
        return len(self._value['ps_normalized_configs*'])

    def __str__(self):
        """Return string representation of configuration."""
        if not self._value:
            st = 'name: {}'.format(self.name)
            return st
        labels = (
            'ti_params_rf_ramp_delay [us]',
            'ti_params_ps_ramp_delay [us]',
            'ti_params_injection_time [ms]',
            'ti_params_ejection_time [ms]',
            'ps_ramp_duration [ms]',
            'ps_ramp_time_energy [ms] [GeV]',
            'ps_ramp_slopes [GeV/s]',
            'ps_normalized_configs [ms] [name]',
        )
        st = ''
        maxlen = max(tuple(len(l) for l in labels) + (len('name'),))
        strfmt1 = '{:<' + str(maxlen) + 's}: {}\n'
        strfmt2 = strfmt1.replace('{}', '{:07.3f} {:+08.3f} {:<s}')
        strfmt3 = strfmt1.replace('{}', '{:07.3f} {}')
        strfmt4 = strfmt1.replace('{}', '{:07.3f}')
        st += strfmt1.format('name', self.name)
        st += strfmt1.format(labels[0], self.ti_params_rf_ramp_delay)
        st += strfmt1.format(labels[1], self.ti_params_ps_ramp_delay)
        st += strfmt4.format(labels[2], self.ti_params_injection_time)
        st += strfmt4.format(labels[3], self.ti_params_ejection_time)
        st += strfmt1.format(labels[4], self.ps_ramp_duration)
        st += strfmt1.format(labels[5], '')
        st += strfmt2.format('', 0.0,
                             self.ps_ramp_start_energy, '(start)')
        st += strfmt2.format('', self.ps_ramp_rampup1_start_time,
                             self.ps_ramp_rampup1_start_energy,
                             '(rampup1_start)')
        st += strfmt2.format('', self.ps_ramp_rampup2_start_time,
                             self.ps_ramp_rampup2_start_energy,
                             '(rampup2_start)')
        st += strfmt2.format('', self.ps_ramp_rampdown_start_time,
                             self.ps_ramp_rampdown_start_energy,
                             '(rampdown_start)')
        st += strfmt2.format('', self.ps_ramp_rampdown_stop_time,
                             self.ps_ramp_rampdown_stop_energy,
                             '(rampdown_stop)')
        st += strfmt2.format('', self.ps_ramp_duration,
                             self.ps_ramp_start_energy, '(stop)')
        st += strfmt1.format(labels[6], '')
        st += strfmt3.format('', self.ps_ramp_rampup1_slope,
                             '(rampup1)')
        st += strfmt3.format('', self.ps_ramp_rampup2_slope,
                             '(rampup2)')
        st += strfmt3.format('', self.ps_ramp_rampdown_slope,
                             '(rampdown)')
        st += strfmt1.format(labels[7], '')
        time = self.ps_normalized_configs_times
        name = self.ps_normalized_configs_labels
        for i in range(len(time)):
            st += strfmt3.format('', time[i], name[i])
        return st

    def _get_item(self, time):
        str_time = '{:.3f}'.format(time)
        return _dcopy(self._value['ps_normalized_configs*'][str_time])

    def _set_item(self, time, value):
        """Set configuration item."""
        str_time = '{:.3f}'.format(time)
        if value == self._value['ps_normalized_configs*'][str_time]:
            return
        self._value['ps_normalized_configs*'][str_time] = _dcopy(value)
        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    def _set_value(self, value):
        super()._set_value(value)
        self.verify_synchronized()
        self._invalidate_ps_waveforms()

    def _update_ps_normalized_config_energy(self, nconfig_obj, time):
        indices = self._conv_times_2_indices(self.PSNAME_DIPOLE_REF, [time])
        strengths = self.ps_waveform_get_strengths(self.PSNAME_DIPOLE_REF)
        strength = _np.interp(
            indices[0],
            list(range(self._get_appropriate_wfmnrpoints(
                self.PSNAME_DIPOLE_REF))),
            strengths)
        for psname in self.PSNAME_DIPOLES:
            nconfig_obj[psname] = strength
        return nconfig_obj

    def _update_ps_waveform(self, psname):

        # update dipole if necessary
        if self.PSNAME_DIPOLE_REF not in self._ps_waveforms:
            self._update_ps_waveform_dipole()

        # update family if necessary
        family = _get_magnet_family_name(psname)
        if family is not None and family not in self._ps_waveforms:
            self._update_ps_waveform(family)

        # update magnet waveform if it is not a dipole
        if psname not in self._ps_waveforms:
            self._update_ps_waveform_not_dipole(
                psname, self.PSNAME_DIPOLE_REF, family)

    def _update_ps_waveform_not_dipole(self, psname, dipole, family=None):
        nc_times = sorted(self.ps_normalized_configs_times)
        nc_values = list()
        for t in nc_times:
            nconfig = self._value['ps_normalized_configs*']['{:.3f}'.format(t)]
            nc_values.append(nconfig[psname])

        # interpolate strengths
        wfm_nrpoints = self._get_appropriate_wfmnrpoints(psname)
        nc_indices = self._conv_times_2_indices(psname, nc_times)
        wfm_indices = [i for i in range(wfm_nrpoints)]
        wfm_strengths = _np.interp(wfm_indices, nc_indices, nc_values)

        # create waveform object with given strengths
        dipole = self._ps_waveforms[dipole]
        if family is not None:
            family = self._ps_waveforms[family]
        self._ps_waveforms[psname] = _Waveform(
            psname=psname, dipole=dipole, family=family,
            strengths=wfm_strengths, wfm_nrpoints=wfm_nrpoints)

    def _update_ps_waveform_dipole(self):
        for psname in self.PSNAME_DIPOLES:
            w = self._create_new_ps_waveform_dipole(psname)
            self._ps_waveforms[psname] = w

    def _create_new_ps_waveform_dipole(self, dipole=''):
        if not dipole:
            dipole = self.PSNAME_DIPOLE_REF
        rdip = self._value['ps_ramp']
        dipole = _WaveformDipole(
            psname=dipole,
            wfm_nrpoints=self._get_appropriate_wfmnrpoints(dipole),
            duration=rdip['duration'],
            start_energy=rdip['start_energy'],
            rampup1_start_time=rdip['rampup1_start_time'],
            rampup1_start_energy=rdip['rampup1_start_energy'],
            rampup2_start_time=rdip['rampup2_start_time'],
            rampup2_start_energy=rdip['rampup2_start_energy'],
            rampup_smooth_intvl=rdip['rampup_smooth_intvl'],
            rampup_smooth_energy=rdip['rampup_smooth_energy'],
            rampdown_start_time=rdip['rampdown_start_time'],
            rampdown_start_energy=rdip['rampdown_start_energy'],
            rampdown_stop_time=rdip['rampdown_stop_time'],
            rampdown_stop_energy=rdip['rampdown_stop_energy'],
            rampdown_smooth_intvl=rdip['rampdown_smooth_intvl'],
            rampdown_smooth_energy=rdip['rampdown_smooth_energy'])
        return dipole

    def _conv_times_2_indices(self, psname, times):
        duration = self.ps_ramp_duration
        wfm_nrpoints = self._get_appropriate_wfmnrpoints(psname)
        interval = duration / (wfm_nrpoints - 1.0)
        indices = [t/interval for t in times]
        return indices

    def _invalidate_ps_waveforms(self, include_dipole=False):
        psnames = tuple(self._ps_waveforms.keys())
        for psname in psnames:
            if psname not in self.PSNAME_DIPOLES or include_dipole:
                del(self._ps_waveforms[psname])

    def _check_valid_time(self, time):
        """Check if time is in valid interval."""
        d = self.ps_ramp_duration
        if 0 < time < d:
            return True
        else:
            raise _RampError(
                'Time value must be between 0 and {}!'.format(d))

    def _get_appropriate_wfmnrpoints(self, psname):
        """Return appropriate number of points for psname."""
        if _PSSearch.conv_psname_2_psmodel(psname) == 'FBP':
            return self.ps_ramp_wfm_nrpoints_corrs
        else:
            return self.ps_ramp_wfm_nrpoints_fams


class SiriusMig(BoosterRamp):
    """Sirius migration class."""

    PSNAME_DIPOLES = ('SI-Fam:PS-B1B2-1', 'SI-Fam:PS-B1B2-2')
