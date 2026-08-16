from PySide6.QtWidgets import QApplication
from app import NumericControl


def test_numeric_control_up_and_down():
    app = QApplication.instance() or QApplication([])

    control = NumericControl(value=100)
    control._up.click()
    assert control.value() == 101

    control._down.click()
    assert control.value() == 100