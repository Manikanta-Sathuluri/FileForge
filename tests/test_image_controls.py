
from PySide6.QtWidgets import QApplication, QSpinBox
from app import _configure_spinbox


def test_spinbox_arrow_configuration():
    app = QApplication.instance() or QApplication([])
    box = _configure_spinbox(QSpinBox(), 10)
    box.stepUp()
    assert box.value() == 11
    box.stepDown()
    assert box.value() == 10
    assert box.singleStep() == 1
    assert box.buttonSymbols()
