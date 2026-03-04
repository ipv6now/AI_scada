import sys
import os

# Add the current directory to sys.path so Python can find the scada_app module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scada_app.hmi.main_window import MainWindow
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())