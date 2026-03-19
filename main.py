import sys

# onnxruntime must be imported before PyQt6 on Windows to avoid DLL conflicts
try:
    import onnxruntime  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
