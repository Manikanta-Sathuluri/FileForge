
from PySide6.QtWidgets import QApplication
from app import NumericControl


def test_numeric_control_buttons():
    app = QApplication.instance() or QApplication([])
    c = NumericControl(value=100)
    c._up.click()
    assert c.value() == 101
    c._down.click()
    assert c.value() == 100
