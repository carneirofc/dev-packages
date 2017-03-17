import urllib.request as _urllib_request
import siriuspy.envars as _envars


_timeout = 1.0
_excdat_folder = '/magnets/excitation-data/'
_ps_folder = '/power_supplies/'


def read_url(url, timeout=_timeout):
    try:
        response = _urllib_request.urlopen(url, timeout=timeout)
        data = response.read()
        text = data.decode('utf-8')
    except:
        errtxt = 'Error reading url "' + url + '"!'
        raise Exception(errtxt)

    return text


def server_online():
    url = _envars.server_url_web
    try:
        index_html = read_url(url, timeout=_timeout)
        return True
    except:
        return False


def magnets_excitation_data_get_filenames_list(timeout=_timeout):
    """Get list of filenames in magnet excitation data folder at web server."""

    url = _envars.server_url_web + _excdat_folder
    response = _urllib_request.urlopen(url, timeout=timeout)
    data = response.read()
    text = data.decode('utf-8')
    words = text.split('"[TXT]"></td><td><a href="')
    fname_list = []
    for word in words[1:]:
        fname = word.split('.txt">')[1].split('</a></td><td')
        fname_list.append(fname[0])
    return fname_list


def magnets_excitation_data_read(filename, timeout=_timeout):
    """Return the text of the corresponding retrived from the web server."""

    url = _envars.server_url_web + _excdat_folder + filename
    return read_url(url, timeout=timeout)


def magnets_excitation_data_read(filename, timeout=_timeout):
    """Return the text of the corresponding retrieved magnet excitation data from the web server."""

    url = _envars.server_url_web + _excdat_folder + filename
    return read_url(url, timeout=timeout)


def power_supplies_pstypes_names_read(timeout=_timeout):
    """Return the text of the corresponding retrieved power supplies type from the web server."""

    url = _envars.server_url_web + _ps_folder + 'pstypes-names.txt'
    return read_url(url, timeout=timeout)


def power_supplies_pstype_data_read(filename, timeout=_timeout):
    url = _envars.server_url_web + _ps_folder + filename
    return read_url(url, timeout=timeout)

def power_supplies_pstype_setpoint_limits(timeout = _timeout):
    url = _envars.server_url_web + _ps_folder + 'pstypes-setpoint-limits.txt'
    return read_url(url, timeout=timeout)
