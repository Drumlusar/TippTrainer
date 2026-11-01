"""Tipptrainer starten:  python main.py"""
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import load_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Tipptrainer")
    app.setStyleSheet(load_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
