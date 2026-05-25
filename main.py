import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("CadAgent (DEMO)")

    layout = QVBoxLayout()
    label = QLabel("Witaj w CadAgent!\n\nPełna wersja GUI powinna być tutaj podpięta (module: gui/main_window.py)")
    layout.addWidget(label)
    window.setLayout(layout)
    window.resize(400, 200)
    window.show()
    sys.exit(app.exec())
