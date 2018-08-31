#!/usr/bin/env python-sirius
"""Test webserver implementation module."""
import unittest
from unittest import mock
from urllib.request import URLError

from siriuspy.servweb import implementation
import siriuspy.util as util

# Dependencies
# _envars.server_url_consts
# _urllib_request.urlopen
# _urllib_request.urlopen.read


class TestServWebReadUrl(unittest.TestCase):
    """Test read url method."""

    def setUp(self):
        """Common setup for all tests."""
        # Create mocks
        url_patcher = mock.patch.object(
            implementation, '_urllib_request', autospec=True)
        env_patcher = mock.patch.object(
            implementation, '_envars', autospec=True)
        self.addCleanup(url_patcher.stop)
        self.addCleanup(env_patcher.stop)
        self.url_mock = url_patcher.start()
        self.env_mock = env_patcher.start()
        # Configuration parameters
        self.fake_url = "http://FakeBaseURL/"
        # Mocked methods
        self.url_mock.urlopen.return_value.read.return_value = b'FakeResponse'
        # Mock a property from envars
        type(self.env_mock).server_url_consts = \
            mock.PropertyMock(return_value=self.fake_url)

    def test_read_url_request(self):
        """Test read_rul makes a request using urlopen."""
        implementation.read_url("FakeURL")
        self.url_mock.urlopen.assert_called_once_with(
            self.fake_url + "FakeURL", timeout=1.0)

    def test_read_url_response(self):
        """Test read_url."""
        self.assertEqual(implementation.read_url("FakeURL"), "FakeResponse")

    def test_read_url_exception(self):
        """Test read_url raises exception."""
        self.url_mock.urlopen.side_effect = URLError("FakeError")
        with self.assertRaises(Exception):
            implementation.read_url("FakeURL")


@mock.patch.object(implementation, 'read_url', autospec=True,
                   return_value="FakeResponse")
class TestServWeb(unittest.TestCase):
    """Test servweb."""

    public_interface = {
        'read_url',
        'server_online',
        'magnets_excitation_data_read',
        'magnets_setpoint_limits',
        'pulsed_magnets_setpoint_limits',
        'magnets_excitation_ps_read',
        'ps_pstypes_names_read',
        'ps_pstype_data_read',
        'ps_siggen_configuration_read',
        'ps_pstype_setpoint_limits',
        'pu_pstype_setpoint_limits',
        'ps_psmodels_read',
        'pu_psmodels_read',
        'beaglebone_power_supplies_mapping',
        'beaglebone_bsmp_mapping',
        'bbb_udc_mapping',
        'udc_ps_mapping',
        'crates_mapping',
        'bpms_data',
        'timing_devices_mapping',
        'high_level_triggers',
        'bsmp_dclink_mapping'
    }

    def test_public_interface(self, mock_read):
        """Test module's public interface."""
        valid = util.check_public_interface_namespace(
            implementation, TestServWeb.public_interface)
        self.assertTrue(valid)

    def test_server_online(self, mock_read):
        """Test server_online return True when no exception is issued."""
        self.assertTrue(implementation.server_online())

    def test_server_online_exception(self, mock_read):
        """Test server_online return True when no exception is issued."""
        mock_read.side_effect = Exception()
        self.assertFalse(implementation.server_online())

    def test_magnets_excitation_data_read(self, mock_read):
        """Test magnets_excitation_data_read."""
        filename = "fakefile"
        folder = implementation._excdat_folder
        # Call two times
        resp = implementation.magnets_excitation_data_read(filename)
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.magnets_excitation_data_read(
            filename, timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read was called correctly
        mock_read.assert_has_calls([
            mock.call(folder + filename, timeout=1.0),
            mock.call(folder + filename, timeout=2.0)])

    def test_magnets_setpoint_limits(self, mock_read):
        """"Test magnets_setpoint_limits."""
        url = implementation._magnet_folder + 'magnet-setpoint-limits.txt'
        # Call with different parameters
        resp = implementation.magnets_setpoint_limits()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.magnets_setpoint_limits(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_pulsed_magnets_setpoint_limits(self, mock_read):
        """"Test pulsed_magnets_setpoint_limits."""
        url = \
            implementation._magnet_folder + 'pulsed-magnet-setpoint-limits.txt'
        # Call with different parameters
        resp = implementation.pulsed_magnets_setpoint_limits()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.pulsed_magnets_setpoint_limits(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_magnets_excitation_ps_read(self, mock_read):
        """"Test magnets_excitation_ps_read."""
        url = implementation._magnet_folder + 'magnet-excitation-ps.txt'
        # Call with different parameters
        resp = implementation.magnets_excitation_ps_read()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.magnets_excitation_ps_read(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_ps_pstypes_names_read(self, mock_read):
        """"Test ps_pstypes_names_read."""
        url = implementation._ps_folder + 'pstypes-names.txt'
        # Call with different parameters
        resp = implementation.ps_pstypes_names_read()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.ps_pstypes_names_read(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_ps_pstype_data_read(self, mock_read):
        """"Test ps_pstype_data_read."""
        filename = "fakefilename"
        url = implementation._pstypes_data_folder + filename
        # Call with different parameters
        resp = implementation.ps_pstype_data_read(filename)
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.ps_pstype_data_read(filename, timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_ps_siggen_configuration_read(self, mock_read):
        """Test ps_siggen_configuration_read."""
        url = implementation._ps_folder + 'siggen-configuration.txt'
        # Call with different parameters
        resp = implementation.ps_siggen_configuration_read()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.ps_siggen_configuration_read(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_ps_pstype_setpoint_limits(self, mock_read):
        """Test ps_pstype_setpoint_limits."""
        url = implementation._ps_folder + 'pstypes-setpoint-limits.txt'
        # Call with different parameters
        resp = implementation.ps_pstype_setpoint_limits()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.ps_pstype_setpoint_limits(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_pu_pstype_setpoint_limits(self, mock_read):
        """Test pu_pstype_setpoint_limits."""
        url = implementation._ps_folder + 'putypes-setpoint-limits.txt'
        # Call with different parameters
        resp = implementation.pu_pstype_setpoint_limits()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.pu_pstype_setpoint_limits(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_beaglebone_bsmp_mapping(self, mock_read):
        """Test beaglebnoe_bsmp_mapping."""
        # TODO: implement!
        pass

    def test_beaglebone_power_supplies_mapping(self, mock_read):
        """Test beaglebone_power_supplies_mapping."""
        url = implementation._ps_folder + 'beaglebone-mapping.txt'
        # Call with different parameters
        resp = implementation.beaglebone_power_supplies_mapping()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.beaglebone_power_supplies_mapping(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_crates_mapping(self, mock_read):
        """Test crate_to_bpm_mapping."""
        url = (
            implementation._diag_folder + 'Mapeamento_placas_MicroTCA_vs_BPMs/')
        # Call with different parameters
        resp = implementation.crates_mapping()
        self.assertEqual(resp, "")
        resp = implementation.crates_mapping(timeout=2.0)
        self.assertEqual(resp, "")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_bpms_data(self, mock_read):
        """Test bpms_data."""
        url = implementation._diag_folder + 'bpms-data.txt'
        # Call with different parameters
        resp = implementation.bpms_data()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.bpms_data(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_timing_devices_mapping(self, mock_read):
        """Test timing_devices_mapping."""
        url = implementation._timesys_folder + 'timing-devices-connection.txt'
        # Call with different parameters
        resp = implementation.timing_devices_mapping()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.timing_devices_mapping(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])

    def test_high_level_triggers(self, mock_read):
        """Test high_level_triggers."""
        url = implementation._timesys_folder + 'high-level-triggers.txt'
        # Call with different parameters
        resp = implementation.high_level_triggers()
        self.assertEqual(resp, "FakeResponse")
        resp = implementation.high_level_triggers(timeout=2.0)
        self.assertEqual(resp, "FakeResponse")
        # Assert read_url was called correctly
        mock_read.assert_has_calls([
            mock.call(url, timeout=1.0),
            mock.call(url, timeout=2.0)])


if __name__ == "__main__":
    unittest.main()
