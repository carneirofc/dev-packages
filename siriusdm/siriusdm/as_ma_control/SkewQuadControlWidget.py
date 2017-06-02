from .BaseMagnetControlWidget import BaseMagnetControlWidget

class SiSkewQuadControlWidget(BaseMagnetControlWidget):
    def __init__(self, magnet_list, orientation=0, parent=None):
        super(SiSkewQuadControlWidget, self).__init__(magnet_list, orientation, parent)
        self._setupUi()

    def _getPattern(self):
        return "SI-\w{4}:MA-QS"

    def _getMetric(self):
        return "KL"

    def _getHeader(self):
        return [None, None, None, "Setpoint [A]", "Readback [A]", "KL [1/m]"]

    def _hasTrimButton(self):
        return False

    def _hasScrollArea(self):
        return True

    def _divideBySection(self):
        return True

    def _getGroups(self):
        return [    ('Skew Quad (01 - 10)', '(0\d|10)'),
                    ('Skew Quad (11 - 20)', '(1[1-9]|20)')]

class BoSkewQuadControlWidget(SiSkewQuadControlWidget):

    def _getPattern(self):
        return "BO-\w{3}:MA-QS"

    def _hasScrollArea(self):
        return False

    def _divideBySection(self):
        return False

    def _getGroups(self):
        return [('Skew Quad', '')]