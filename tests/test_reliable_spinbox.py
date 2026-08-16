
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app import ReliableSpinBox


def test_reliable_spinbox_up_and_down_clicks():
    app = QApplication.instance() or QApplication([])
    box = ReliableSpinBox()
    box.resize(140, 34)
    box.setRange(1, 20000)
    box.setValue(100)

    right_x = box.width() - 5
    top = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPoint(right_x, 5),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
    )
    box.mousePressEvent(top)
    assert box.value() == 101

    bottom = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPoint(right_x, box.height() - 5),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
    )
    box.mousePressEvent(bottom)
    assert box.value() == 100
