from pathlib import Path

def test_no_stale_reliable_spinbox_reference():
    text = Path("src/app.py").read_text(encoding="utf-8")
    assert "ReliableSpinBox" not in text
    assert "NumericControl" in text
