"""
Dark mode stylesheet inspired by Windows 11 design language.
"""

DARK_THEME_STYLESHEET = """
QMainWindow {
    background-color: #202020;
    color: #ffffff;
}

QWidget {
    font-family: 'Segoe UI Variable', 'Segoe UI', 'San Francisco', sans-serif;
    font-size: 10pt;
    color: #ffffff;
}

/* Command Bar (LineEdit) */
QLineEdit {
    background-color: #333333;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11pt;
    color: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #0078d4;
    background-color: #383838;
}

/* Buttons */
QPushButton {
    background-color: #333333;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 6px 16px;
    color: #ffffff;
}

QPushButton:hover {
    background-color: #3a3a3a;
    border: 1px solid #555555;
}

QPushButton:pressed {
    background-color: #282828;
    border: 1px solid #454545;
    color: #d0d0d0;
}

QPushButton#accentButton {
    background-color: #0078d4;
    border: 1px solid #0078d4;
    color: #ffffff;
}

QPushButton#accentButton:hover {
    background-color: #2b88d8;
    border: 1px solid #2b88d8;
}

QPushButton#accentButton:pressed {
    background-color: #006cbe;
    border: 1px solid #006cbe;
}

/* Table View */
QTableView {
    background-color: #2b2b2b;
    alternate-background-color: #303030;
    border: 1px solid #454545;
    border-radius: 6px;
    gridline-color: #454545;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #202020;
    color: #cccccc;
    padding: 4px;
    border: 1px solid #333333;
    border-top: none;
    border-left: none;
    font-weight: bold;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #202020;
    width: 14px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    min-height: 30px;
    border-radius: 7px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #777777;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Text Edit (Logs) */
QTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 8px;
    font-family: 'Consolas', monospace;
    font-size: 9pt;
    color: #cccccc;
}

/* Labels */
QLabel {
    color: #e0e0e0;
}

QLabel#headerLabel {
    font-size: 14pt;
    font-weight: bold;
    color: #ffffff;
}
"""
