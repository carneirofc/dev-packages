import copy as _copy
import uuid as _uuid
import numpy as _np
from siriuspy.search import PSSearch as _PSSearch
from siriuspy.search import MASearch as _MASearch
from siriuspy.csdevice.enumtypes import EnumTypes as _et
from siriuspy.csdevice.pwrsupply import default_wfmlabels as _default_wfmlabels
from siriuspy.csdevice.pwrsupply import get_ps_propty_database  as _get_ps_propty_database
from siriuspy.csdevice.pwrsupply import get_ma_propty_database  as _get_ma_propty_database
from siriuspy.pwrsupply.controller import ControllerSim as _ControllerSim
from siriuspy.pwrsupply.controller import ControllerEpics as _ControllerEpics


_connection_timeout = 0.0


class PSData:

    def __init__(self, psname):
        self._psname = psname
        self._pstype = _PSSearch.conv_psname_2_pstype(self._psname)
        self._polarity = _PSSearch.conv_pstype_2_polarity(self._pstype)
        self._magfunc = _PSSearch.conv_pstype_2_magfunc(self._pstype)
        self._splims = _PSSearch.conv_pstype_2_splims(self._pstype)
        self._splims_unit = _PSSearch.get_splims_unit()
        self._propty_database = _get_ps_propty_database(self._pstype)

    @property
    def psname(self):
        return self._psname

    @property
    def pstype(self):
        return self._pstype

    @property
    def polarity(self):
        return self._polarity

    @property
    def magfunc(self):
        return self._magfunc

    @property
    def splims(self):
        if self._splims is None:
            return None
        else:
            return self._splims.copy()

    @property
    def splims_unit(self):
        return self._splims_unit

    @property
    def splims_labels(self):
        return sorted(self._slims.keys())

    @property
    def propty_database(self):
        return _copy.deepcopy(self._propty_database)

    def __str__(self):
        st = ''
        st +=        'psname      : ' + str(self.psname)
        st += '\n' + 'pstype      : ' + str(self.pstype)
        st += '\n' + 'polarity    : ' + str(self.polarity)
        st += '\n' + 'magfunc     : ' + str(self.magfunc)
        st += '\n' + 'splims_unit : ' + str(self.splims_unit)

        if self.splims is None:
            st += '\n' + 'splims      : ' + str(None)
        else:
            st += '\n' + 'splims      : ' + 'DRVH:{0:+09.3f} DRVL:{1:+09.3f}'.format(self.splims['DRVH'],self.splims['DRVL'])
            st += '\n' + '              ' + 'HIHI:{0:+09.3f} LOLO:{1:+09.3f}'.format(self.splims['HIHI'],self.splims['LOLO'])
            st += '\n' + '              ' + 'HIGH:{0:+09.3f} LOW :{1:+09.3f}'.format(self.splims['HIGH'],self.splims['LOW'])
            st += '\n' + '              ' + 'HOPR:{0:+09.3f} LOPR:{1:+09.3f}'.format(self.splims['HOPR'],self.splims['LOPR'])

        return st


class MAData:

    def __init__(self, maname):
        self._maname = maname
        self._splims_unit = _MASearch.get_splims_unit()
        psnames = _MASearch.conv_maname_2_psnames(self._maname)
        self._propty_databases = _get_ma_propty_database(self._maname)
        self._psdata = {}
        for psname in psnames:
            self._psdata[psname] = PSData(psname=psname)


    @property
    def maname(self):
        return self._maname

    @property
    def splims_unit(self):
        return self.splims_unit

    @property
    def psnames(self):
        return list(self._psdata.keys())

    def __getitem__(self, psname):
        return self._psdata[psname]

    def get_database(psname):
        return self._propty_databases[psname]


class PowerSupplyLinac(object):

    def __init__(self, psname,
                       controller=None,
                       callback=None,
                       current_std=0.0,
                       enum_keys=False):

        self._psdata = PSData(psname=psname)
        self._callback = callback
        self._enum_keys = enum_keys
        self._ctrlmode_mon = _et.idx.Remote
        self._controller = controller
        self._controller_init(current_std)

    # --- class interface ---

    @property
    def psname(self):
        return self._psdata.psname

    @property
    def pstype(self):
        return self._psdata.pstype

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        if callable(value):
            self._callback = value
        else:
            self._callback = None

    @property
    def splims(self):
        return _copy.deepcopy(self._psdata.splims)

    @property
    def database(self):
        return self._get_database()

    @property
    def ctrlmode_mon(self):
        return self._eget('RmtLocTyp', self._ctrlmode_mon)

    def set_ctrlmode(self, value):
        value = self._eget('RmtLocTyp', value, enum_keys=False)
        if value is not None:
            self._ctrlmode_mon = value

    @property
    def pwrstate_sel(self):
        return self._eget('OffOnTyp', self._pwrstate_sel)

    @pwrstate_sel.setter
    def pwrstate_sel(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        value = self._eget('OffOnTyp', value, enum_keys=False)
        if value is not None and value != self.pwrstate_sts:
            self._pwrstate_sel = value
            self._set_pwrstate_sel(value)

    @property
    def pwrstate_sts(self):
        return self._eget('OffOnTyp', self._controller.pwrstate)

    @property
    def current_sp(self):
        return self._current_sp

    @current_sp.setter
    def current_sp(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        if value not in (self.current_sp, self.current_rb):
            self._current_sp = value
            self._set_current_sp(value)

    @property
    def current_mon(self):
        return self._controller.current_load

    @property
    def intlk_mon(self):
        return self._controller.intlk

    @property
    def intlklabels_cte(self):
        return self._controller.intlklabels

        # --- class implementation ---

    def _get_database(self):
        """Return an updated PV database whose keys correspond to PS properties."""
        db = self._psdata.propty_database
        value = self.ctrlmode_mon; db['CtrlMode-Mon']['value'] = _et.enums('RmtLocTyp').index(value) if self._enum_keys else value
        value = self.pwrstate_sel; db['PwrState-Sel']['value'] = _et.enums('OffOnTyp').index(value) if self._enum_keys else value
        value = self.pwrstate_sts; db['PwrState-Sts']['value'] = _et.enums('OffOnTyp').index(value) if self._enum_keys else value
        db['Current-SP']['value']  = self.current_sp
        db['Current-Mon']['value'] = self.current_mon
        return db

    def _set_pwrstate_sel(self, value):
            self._pwrstate_sel = value
            self._controller.pwrstate = value

    def _set_current_sp(self, value):
            self._pwrstate_sp = value
            self._controller.current_sp = value

    def _controller_init(self, current_std):
        if self._controller is None:
            lims = self._psdata.splims # set controller setpoint limits according to PS database
            self._controller = _ControllerSim(current_min = self._psdata.splims['DRVL'],
                                              current_max = self._psdata.splims['DRVH'],
                                              callback = self._mycallback,
                                              current_std = current_std,
                                              psname=self._psdata.psname)
            self._pwrstate_sel = self._psdata.propty_database['PwrState-Sel']['value']
            self._current_sp   = self._psdata.propty_database['Current-SP']['value']
            self._controller.pwrstate   = self._pwrstate_sel
            self._controller.current_sp = self._current_sp
        else:
            self._pwrstate_sel = self._controller.pwrstate
            self._current_sp   = self._controller.current_sp

        #self.callback = self._mycallback # ????
        self._controller.update_state()

    # --- class private methods ---

    def _eget(self,typ,value,enum_keys=None):
        enum_keys = self._enum_keys if enum_keys is None else enum_keys
        try:
            if enum_keys:
                if isinstance(value, str):
                    return value
                else:
                    return _et.key(typ, value)
            else:
                if isinstance(value, str):
                    return _et.get_idx(typ, value)
                else:
                    return value
        except:
            return None

    def _mycallback(self, pvname, value, **kwargs):
        pass


class PowerSupply(PowerSupplyLinac):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _controller_init(self, current_std):
        if self._controller is None:
            lims = self._psdata.splims # set controller setpoint limits according to PS database
            self._controller = _ControllerSim(current_min = self._psdata.splims['DRVL'],
                                              current_max = self._psdata.splims['DRVH'],
                                              callback = self._mycallback,
                                              current_std = current_std,
                                              psname=self._psdata.psname)

            self._pwrstate_sel = self._psdata.propty_database['PwrState-Sel']['value']
            self._opmode_sel   = self._psdata.propty_database['OpMode-Sel']['value']
            self._current_sp   = self._psdata.propty_database['Current-SP']['value']
            self._wfmlabel_sp  = self._controller.wfmlabel
            self._wfmload_sel  = self._psdata.propty_database['WfmLoad-Sel']['value']
            self._wfmdata_sp   = self._psdata.propty_database['WfmData-SP']['value']
            self._controller.pwrstate   = self._pwrstate_sel
            self._controller.opmode     = self._opmode_sel
            self._controller.current_sp = self._current_sp
            self._controller.wfmload    = self._wfmload_sel
            self._controller.wfmdata_sp = self._wfmdata_sp
        else:
            self._pwrstate_sel = self._controller.pwrstate
            self._opmode_sel   = self._controller.opmode
            self._current_sp   = self._controller.current_sp
            self._wfmlabel_sp  = self._controller.wfmlabel
            self._wfmload_sel  = self._controller.wfmload
            self._wfmdata_sp   = self._controller.wfmdata

        self._controller.callback = self._mycallback
        self._controller.update_state()

    # --- class interface ---

    @property
    def opmode_sel(self):
        return self._eget('PSOpModeTyp', self._opmode_sel)

    @opmode_sel.setter
    def opmode_sel(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        value = self._eget('PSOpModeTyp', value, enum_keys=False)
        if value is not None and value != self.opmode_sts:
            self._opmode_sel = value
            self._set_opmode_sel(value)

    @property
    def opmode_sts(self):
        return self._get_opmode_sts()

    @property
    def reset(self):
        return self._controller.reset_counter

    @reset.setter
    def reset(self,value):
        self._controller.reset()

    @property
    def abort(self):
        return self._controller.abort_counter

    @abort.setter
    def abort(self,value):
        self._controller.abort()

    @property
    def current_rb(self):
        return self._get_current_rb()

    @property
    def currentref_mon(self):
        return self._get_currentref_mon()

    @property
    def wfmindex_mon(self):
        return self._get_wfmindex_mon()

    @property
    def wfmlabels_mon(self):
        return self._get_wfmlabels_mon()

    @property
    def wfmlabel_sp(self):
        return self._wfmlabel_sp

    @property
    def wfmlabel_rb(self):
        return self._get_wfmlabel_rb()

    @wfmlabel_sp.setter
    def wfmlabel_sp(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        if value != self.wfmlabel_rb:
            self._wfmlabel_sp = value
            self._set_wfmlabel_sp(value)

    @property
    def wfmdata_sp(self):
        return _np.array(self._wfmdata_sp)

    @property
    def wfmdata_rb(self):
        return self._get_wfmdata_rb()

    @wfmdata_sp.setter
    def wfmdata_sp(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        if (value != self.wfmdata_rb).any():
            self._wfmdata_sp = _np.array(value)
            self._set_wfmdata_sp(value)

    @property
    def wfmload_sel(self):
        slot = self._wfmload_sel
        if not self._enum_keys:
            return slot
        else:
            wfmlabels = self._get_wfmlabels_mon()
            return wfmlabels[slot]

    @wfmload_sel.setter
    def wfmload_sel(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        wfmlabels = self._get_wfmlabels_mon()
        #slot = _np.where(wfmlabels == value)[0][0] if self._enum_keys else value

        if self._enum_keys:
            if not isinstance(value, str):
                raise ValueError("Type must be str, not {}".format(type(value)))
            if value not in wfmlabels:
                raise KeyError("There is no waveform name {}".format(value))
            slot = _np.where(wfmlabels == value)[0][0]
        else:
            if not isinstance(value, int):
                raise ValueError("Type must be int, not {}".format(type(value)))
            slot = value

        self._wfmload_sel = slot
        self._set_wfmload_sel(slot)

    @property
    def wfmload_sts(self):
        slot = self._get_wfmload_sts()
        if not self._enum_keys:
            return slot
        else:
            wfmlabels = self._get_wfmlabels_mon()
            return wfmlabels[slot]

    @property
    def wfmsave_cmd(self):
        return self._get_wfmsave_cmd()

    @wfmsave_cmd.setter
    def wfmsave_cmd(self, value):
        if self._ctrlmode_mon != _et.idx.Remote: return
        self._controller.wfmsave = value

    # --- class implementation ---

    def _get_database(self):
        """Return an updated  PV database whose keys correspond to PS properties."""
        db = self._psdata.propty_database
        value = self.ctrlmode_mon; db['CtrlMode-Mon']['value'] = _et.enums('RmtLocTyp').index(value) if self._enum_keys else value
        value = self.opmode_sel;   db['OpMode-Sel']['value'] = _et.enums('PSOpModeTyp').index(value) if self._enum_keys else value
        value = self.opmode_sts;   db['OpMode-Sts']['value'] = _et.enums('PSOpModeTyp').index(value) if self._enum_keys else value
        value = self.pwrstate_sel; db['PwrState-Sel']['value'] = _et.enums('OffOnTyp').index(value) if self._enum_keys else value
        value = self.pwrstate_sts; db['PwrState-Sts']['value'] = _et.enums('OffOnTyp').index(value) if self._enum_keys else value
        db['Reset-Cmd']['value'] = self.reset
        db['Abort-Cmd']['value'] = self.abort
        wfmlabels = self._get_wfmlabels_mon()
        db['WfmLoad-Sel']['enums'] = wfmlabels
        db['WfmLoad-Sts']['enums'] = wfmlabels
        value = self.wfmload_sel;  db['WfmLoad-Sel']['value'] = _np.where(wfmlabels == value)[0][0] if self._enum_keys else value
        value = self.wfmload_sts;  db['WfmLoad-Sts']['value'] = _np.where(wfmlabels == value)[0][0] if self._enum_keys else value
        db['WfmLabel-SP']['value']    = self.wfmlabel_sp
        db['WfmLabel-RB']['value']    = self.wfmlabel_rb
        db['WfmLabels-Mon']['value']  = self.wfmlabels_mon
        db['WfmData-SP']['value']     = self.wfmdata_sp
        db['WfmData-RB']['value']     = self.wfmdata_rb
        db['WfmSave-Cmd']['value']    = self.wfmsave_cmd
        db['WfmIndex-Mon']['value']   = self.wfmindex_mon
        db['Current-SP']['value']     = self.current_sp
        db['Current-RB']['value']     = self.current_rb
        db['CurrentRef-Mon']['value'] = self.currentref_mon
        db['Current-Mon']['value']    = self.current_mon
        db['Intlk-Mon']['value']      = self.intlk_mon
        return db

    def _set_opmode_sel(self, value):
        self._controller.opmode = value

    def _get_opmode_sts(self):
        return self._eget('PSOpModeTyp',self._controller.opmode)

    def _get_current_rb(self):
        return self._controller.current_sp

    def _get_currentref_mon(self):
        return self._controller.current_ref

    def _get_wfmindex_mon(self):
        return self._controller.wfmindex

    def _get_wfmlabels_mon(self):
        return self._controller.wfmlabels

    def _get_wfmlabel_rb(self):
        return self._controller.wfmlabel

    def _set_wfmlabel_sp(self, value):
        self._controller.wfmlabel = value

    def _get_wfmdata_rb(self):
        return _np.array(self._controller.wfmdata)

    def _set_wfmdata_sp(self, value):
        self._controller.wfmdata = value

    def _get_wfmload_sts(self):
        return self._controller.wfmload

    def _set_wfmload_sel(self, value):
        self._controller.wfmload = value

    def _get_wfmsave_cmd(self):
        return self._controller.wfmsave

    def _mycallback(self, pvname, value, **kwargs):
        if isinstance(self._controller, _ControllerEpics):
            if 'CtrlMode-Mon' in pvname:
                self._ctrlmode_mon = value
            elif 'OpMode-Sel' in pvname:
                self._opmode_sel   = value
            elif 'PwrState-Sel' in pvname:
                self._pwrstate_sel = value
            elif 'PwrState-Sel' in pvname:
                self._pwrstate_sel = value
            elif 'WfmLoad-Sel' in pvname:
                self._wfmload_sel  = value
            elif 'WfmLabel-SP' in pvname:
                self._wfmlabel_sp  = value
            elif 'WfmData-SP' in pvname:
                self._wfmdata_sp   = value
            elif 'Current-SP' in pvname:
                self._current_sp   = value


class PowerSupplyMA(PowerSupply):

    def __init__(self, maname, **kwargs):
        self._maname = maname
        super().__init__(psname=maname.replace('-MA','-PS'),**kwargs)




class PowerSupplyEpicsSync(PowerSupply):

    def __init__(self, controllers, **kwargs):
        self._controllers = controllers
        super().__init__(controller=controllers[0], **kwargs)

    def _controller_init(self, current_std):
        c0 = self._controllers[0]
        self._pwrstate_sel = c0.pwrstate
        self._opmode_sel = c0.opmode
        self._current_sp = c0.current_sp
        self._wfmlabel_sp  = c0.wfmlabel
        self._wfmload_sel  = c0.wfmload
        self._wfmdata_sp   = c0.wfmdata
        for c in self._controllers:
            c.pwrstate = self._pwrstate_sel
            c.opmode = self._opmode_sel
            c.current_sp = self._current_sp
            c.wfmlabel = self._wfmlabel_sp
            c.wfmload = self._wfmload_sel
            c.wfmdata = self._wfmdata_sp
            c.update_state()

    def _set_opmode_sel(self, value):
        for c in self._controllers:
            c.opmode = value

    def _set_wfmlabel_sp(self, value):
        for c in self._controllers:
            c.wfmlabel = value

    def _set_wfmdata_sp(self, value):
        for c in self._controllers:
            c.wfmdata = value

    def _set_wfmload_sel(self, value):
        for c in self._controllers:
            c.wfmload = value

    def _set_pwrstate_sel(self, value):
        for c in self._controllers:
            c.pwrstate = value

    def _set_current_sp(self, value):
        for c in self._controllers:
            c.current_sp = value


class PowerSupplyMagnet(PowerSupply):

    def __init__(self, psname, **kwargs):
        super().__init__(psname, **kwargs)

    @property
    def database(self):
        """Return property database as a dictionary.
        It prepends power supply family name to each dictionary key.
        """
        _database = {}
        dd = super().database
        _, family = self.ps_name.split('PS-')
        if not isinstance(family,str):
            raise Exception('invalid pv_name!')
        for propty, db in super().database.items():
            key = family + ':' + propty
            _database[key] = _copy.deepcopy(db)
        return _database
