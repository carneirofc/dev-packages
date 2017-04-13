import copy as _copy
import re as _re
import sys as _sys
import math as _math
import numpy as _np
import importlib as _importlib
if _importlib.find_loader('matplotlib') is not None:
    import matplotlib.pyplot as _plt
    import matplotlib.gridspec as _gridspec
    import matplotlib.cm as _cmap

import siriuspy.servweb as _web
import siriuspy.namesys as _namesys

_timeout = 1.0
_LOCAL = False

class _TimeDevData:
    """Class with mapping of Connection among timing devices and triggers receivers.

    Data are read from the Sirius web server.
    """
    _reg = _re.compile('([a-z]+)([0-9]*)',_re.IGNORECASE)

    _spacing_for_plot = 10

    def __init__(self, timeout=_timeout):
        self._conn_from_evg       = dict()
        self._conn_twrds_evg      = dict()
        self._devices_relations   = dict()
        self._top_chain_devs      = set()
        self._final_receiver_devs = set()
        self._all_devices         = set()
        self._hierarchy_map       = list()
        self._positions           = dict()
        self._colors              = dict()
        self._arrow_colors        = dict()
        if _web.server_online():
            if _LOCAL:
                with open('/home/fac_files/lnls-sirius/control-system-constants/'+
                          'timesys/timing-devices-connection.txt','r') as f:
                    text = f.read()
            else:
                text = _web.timing_devices_mapping(timeout=_timeout)
            self._parse_text_and_build_connection_mappings(text)
            self._update_related_maps()

    def _update_related_maps(self):
        self._top_chain_devs      = self._conn_from_evg.keys()  - self._conn_twrds_evg.keys()
        self._final_receiver_devs = self._conn_twrds_evg.keys() - self._conn_from_evg.keys()
        self._all_devices         = self._conn_from_evg.keys()  | self._conn_twrds_evg.keys()
        self._build_devices_relations()
        self._build_hierarchy_map()
        self._build_positions()
        self._build_colors()
        self._build_arrow_colors()

    def _get_dev_and_channel(self,txt):
        type_chan = num_chan = None
        txt = _namesys.SiriusPVName(txt)
        dev = txt.dev_name
        chan  = txt.propty.lower()
        reg_match = self._reg.findall(chan)
        if reg_match:
            type_chan, num_chan = reg_match[0]
            return dev, chan, type_chan, num_chan

    def _parse_text_and_build_connection_mappings(self,text):
        from_evg = dict()
        twrds_evg = dict()
        lines = text.splitlines()
        for n,line in enumerate(lines,1):
            line = line.strip()
            if not line or line[0] == '#': continue # empty line
            out,inn,*_ = line.split()
            send, ochn, octyp, ocn = self._get_dev_and_channel(out)
            recv, ichn, ictyp, icn = self._get_dev_and_channel(inn)
            if not ochn or not ichn:
                print('No {0:s} channel defined in line {1:d}:\n\t {2:s}'.format(
                       'output' if not ochn else 'input', n,        line))
                return
            elif not octyp or not ictyp:
                print('Sintaxe error in definition of {0:s} channel in line {1:d}:\n\t {2:s}'.format(
                                        'output' if not octyp else 'input',   n,       line))
                return
            elif octyp != ictyp:
                print('Channel types do not match in line {0:d}:\n\t {1:s}'.format(n,line))
                return
            else:
                if send in from_evg.keys():
                    this_sen = from_evg[send]
                    if ochn in this_sen.keys():  this_sen[ochn] += (recv,ichn)
                    else:                        this_sen.update({ ochn : ((recv, ichn), ) }  )
                else:
                    from_evg[send] = { ochn : ((recv, ichn), ) }

                if recv in twrds_evg.keys():
                    this_recv = twrds_evg[recv]
                    if ichn in this_recv.keys():
                        print('Duplicate device input connection in line {0:d}:\n\t {1:s}'.format(n,line))
                        return
                    else:
                        this_recv.update(  { ichn : (send, ochn) }  )
                else:
                    twrds_evg[recv] =   { ichn : (send, ochn) }
        self._conn_from_evg   = from_evg
        self._conn_twrds_evg = twrds_evg

    def _build_devices_relations(self):
        simple_map = dict()
        for k,vs in self._conn_from_evg.items():
            devs = set()
            for v in vs.values(): devs.update([i[0] for i in v])
            simple_map[k] = devs
        self._devices_relations =  simple_map

    def _build_hierarchy_map(self):
        hierarchy = [self._top_chain_devs.copy(),]
        while True:
            vals = set()
            for k in hierarchy[-1]:
                vals |= self._devices_relations.get(k,set())
            if vals: hierarchy.append(vals)
            else:    break
        self._hierarchy_map = hierarchy

    def plot_network(self):
        if 'matplotlib' not in _sys.modules:
            print('Cannot draw network:matplotlib is not installed')
            return

        def on_motion(event):
            if event.inaxes is None: return
            ind = _np.argmin(  ( xs - event.xdata )**2  +  ( ys - event.ydata )**2  )
            pos = (xs[ind],ys[ind])
            txt.xy = pos
            txt.set_position(pos)
            txt.set_text(self._inv_positions[pos])
            f.canvas.draw()


        f  = _plt.figure(figsize=(20,20))
        f.canvas.mpl_connect('motion_notify_event',on_motion)
        gs = _gridspec.GridSpec(1, 1)
        gs.update(left=0.1,top=0.97,bottom=0.12,right=0.95,hspace=0.00,wspace=0.2)
        ax = _plt.subplot(gs[0,0])
        xs = _np.zeros(len(self._all_devices))
        ys = _np.zeros(len(self._all_devices))
        for i,dev in enumerate(sorted(self._all_devices)):
            xs[i], ys[i] = self._positions[dev]
            ax.plot(*self._positions[dev],color=self._colors[dev],marker='.',markersize = 8)

        txt = ax.annotate(s='',xy=(0.0,0.0),xycoords='data')

        kwargs = dict()
        for dev in sorted(self._devices_relations.keys()):
            conns = sorted(self._devices_relations[dev])
            for conn in conns:
                x  = self._positions[dev][0]
                y  = self._positions[dev][1]
                dx = self._positions[conn][0] - x
                dy = self._positions[conn][1] - y
                cor = self._arrow_colors[(dev,conn)]
                ax.arrow(x,y,dx,dy, fc=cor, ec=cor, length_includes_head=True)#,**kwargs)

    def _build_positions(self):
        pi2 = _math.pi*2
        dist = lambda x: self._spacing_for_plot/_math.sqrt(  2*( 1-_math.cos(x) )  )
        pol2cart = lambda x,y:(  x*_math.cos( (y[0]+y[1])/2 ),  x*_math.sin( (y[0]+y[1])/2 )   )

        nevgs = len(self._hierarchy_map[0])
        radia = [0]* len(self._hierarchy_map)
        radia[0] = 0 if nevgs == 1 else dist(pi2/nevgs)
        angles = dict()
        positions = dict()
        for i,dev in enumerate(self._hierarchy_map[0]):
            angles[dev] = ( i*pi2/nevgs, (i+1)*pi2/nevgs )
            positions[dev] = pol2cart(radia[0],angles[dev])

        #find angles and radia
        for n, devs in enumerate(self._hierarchy_map):
            min_ang = pi2
            for dev in devs:
                angi, angf = angles[dev]
                dang = angf-angi
                devs2 = self._devices_relations.get(dev,set())
                nr = len(devs2)
                min_ang = min(min_ang,dang,dang/nr if nr else min_ang)
                for i,dev2 in enumerate(devs2):
                    angles[dev2] = ( i*dang/nr + angi, (i+1)*dang/nr + angi)
            r = dist(min_ang)
            if n>0 and r <= radia[n-1]:
                radia[n] = 2*radia[n-1]
            else:
                radia[n] = r

        # get positions
        for n,devs in enumerate(self._hierarchy_map):
            for dev in devs:
                devs2 = self._devices_relations.get(dev,set())
                for i,dev2 in enumerate(devs2):
                    positions[dev2] = pol2cart(radia[n],angles[dev2])

        self._positions =  positions
        self._inv_positions = {xy:dev for dev,xy in positions.items()}

    def _build_colors(self):
        dev_types = set()
        for dev in self._all_devices:
            dev_types.add(_namesys.SiriusPVName(dev).dev_type)

        nr = len(dev_types)+2
        color_types = dict()
        for i, dev_type in  enumerate(sorted(dev_types),1):
            color_types[dev_type] = _cmap.spectral(i/nr)

        colors = dict()
        for dev in self._all_devices:
            colors[dev] = color_types[_namesys.SiriusPVName(dev).dev_type]

        self._colors = colors

    def _build_arrow_colors(self):
        chan_types = set()
        for conns in self._conn_from_evg.values():
            for chan in conns.keys():
                chan_type = self._reg.findall(chan)[0][0]
                chan_types.add(chan_type)

        nr = len(chan_types)+2
        color_types = dict()
        for i, chan_type in  enumerate(sorted(chan_types),1):
            color_types[chan_type] = _cmap.spectral(i/nr)

        colors = dict()
        for dev1,conns in self._conn_from_evg.items():
            for chan,devs in conns.items():
                chan_type = self._reg.findall(chan)[0][0]
                for dev2 in devs:
                    colors[(dev1,dev2[0])] = color_types[chan_type]

        self._arrow_colors = colors

    def add_crates_info(self,connections_dict):
        not_used = set()
        for crate, bpms in connections_dict.items():
            my_conns = self._conn_twrds_evg.get(crate)
            if my_conns is None:
                not_used.add(crate)
                continue
            for conn in my_conns.keys():
                for bpm in bpms:
                    self._add_entry_to_map(which_map='from', conn=conn, ele1=crate, ele2=bpm)
                    self._add_entry_to_map(which_map='twrds', conn=conn, ele1=bpm, ele2=crate)
        self._update_related_maps()
        return not_used

    def add_bbb_info(self,connections_dict):
        conn = 'ser1'
        not_used = set()
        for bbb, pss in connections_dict.items():
            my_conns = self._conn_twrds_evg.get(bbb)
            if my_conns is None:
                not_used.add(bbb)
                continue
            for ps in pss:
                self._add_entry_to_map(which_map='from', conn=conn, ele1=bbb, ele2=ps)
                self._add_entry_to_map(which_map='twrds', conn=conn, ele1=ps, ele2=bbb)
        self._update_related_maps()
        return not_used

    def _add_entry_to_map(self, which_map, conn, ele1, ele2):
        mapp = self._conn_from_evg if which_map=='from' else self._conn_twrds_evg
        ele1_entry = mapp.get(ele1)
        if not ele1_entry:
            mapp[ele1] = {  conn:( (ele2,conn), )  }
        else:
            conn_entry = ele1_entry.get(conn)
            if not conn_entry:
                ele1_entry[conn]  = ((ele2,conn),)
            else:
                ele1_entry[conn] += ((ele2,conn),)

    @property
    def conn_from_evg(self): return _copy.deepcopy(self._conn_from_evg)

    @property
    def conn_twrds_evg(self): return _copy.deepcopy(self._conn_twrds_evg)

    @property
    def final_receivers(self): return _copy.deepcopy(self._final_receiver_devs)

    @property
    def top_chain_senders(self): return _copy.deepcopy(self._top_chain_devs)

    @property
    def relations_from_evg(self): return _copy.deepcopy(self._devices_relations)

    @property
    def hierarchy_list(self): return _copy.deepcopy(self._hierarchy_map)

    @property
    def all_devices(self): return _copy.deepcopy(self._all_devices)

_timedata = None
def  _get_timedata():
    # encapsulating _bbbdata within a function avoid creating the global object
    # (which is time consuming) at module load time.
    global _timedata
    if _timedata is None:
        _timedata = _TimeDevData()
    return _timedata


# TIMEDATA API
# ==========
def reset():
    global _timedata
    _timedata = _TimeDevData()

def server_online():
    """Return True/False if Sirius web server is online."""
    return _web.server_online()

def get_connections_from_evg():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.conn_from_evg

def get_connections_twrds_evg():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.conn_twrds_evg

def get_top_chain_senders():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.top_chain_senders

def get_final_receivers():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.final_receivers

def get_relations_from_evg():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.relations_from_evg

def get_hierarchy_list():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.hierarchy_list

def get_all_devices():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.all_devices

def add_bbb_info(connections_dict):
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.add_bbb_info(connections_dict)

def add_crates_info(connections_dict):
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.add_crates_info(connections_dict)

def plot_network():
    """Return a dictionary with the beaglebone to power supply mapping."""
    timedata =  _get_timedata()
    return timedata.plot_network()