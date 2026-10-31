
#include "Application.h"
#include "ui/MainWindow.h"

Application::Application(int argc, char* argv[]): QApplication(argc, argv), m_MainWindow(nullptr){
    // QSettings stores under organization/application, so set both before
    // anything (MainWindow's ClientSettings) reads settings.
    setOrganizationName("Solon");
    setApplicationName("Solon");

    setStyleSheet(R"(
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }

        QMainWindow {
            background-color: #1e1e2e;
        }

        QListView {
            background-color: #181825;
            border: none;
            padding: 4px;
        }

        QListView::item {
            padding: 10px 12px;
            border-radius: 6px;
        }

        QListView::item:hover {
            background-color: #313244;
        }

        QListView::item:selected {
            background-color: #45475a;
        }

        QListView::indicator, QCheckBox::indicator {
            width: 14px;
            height: 14px;
            border: 1px solid #6c7086;
            border-radius: 3px;
            background-color: #313244;
        }

        QListView::indicator:checked, QCheckBox::indicator:checked {
            background-color: #89b4fa;
            border-color: #89b4fa;
        }

        QCheckBox::indicator:indeterminate {
            background-color: rgba(137, 180, 250, 0.45);
            border-color: #89b4fa;
        }

        QComboBox {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 4px 10px;
            color: #cdd6f4;
        }

        QComboBox QAbstractItemView {
            background-color: #313244;
            selection-background-color: #45475a;
            border: 1px solid #45475a;
        }

        QLineEdit {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 6px 10px;
            color: #cdd6f4;
        }

        QLineEdit:focus {
            border: 1px solid #89b4fa;
        }

        QSpinBox {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 5px 8px;
            color: #cdd6f4;
        }

        QSpinBox:focus {
            border: 1px solid #89b4fa;
        }

        QToolBar QToolButton {
            padding: 6px;
            border-radius: 6px;
        }

        QToolBar QToolButton:hover {
            background-color: #313244;
        }

        QLabel#settingsHeader {
            font-size: 15px;
            font-weight: bold;
            color: #89b4fa;
        }

        QLabel#settingsHint {
            color: #6c7086;
            font-size: 11px;
        }

        QLabel#settingsError {
            color: #f38ba8;
            font-weight: bold;
        }

        QPushButton {
            background-color: #89b4fa;
            color: #1e1e2e;
            border: none;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #b4befe;
        }

        QPushButton:pressed {
            background-color: #74c7ec;
        }

        QPushButton:disabled {
            background-color: #313244;
            color: #6c7086;
        }

        QSplitter::handle {
            background-color: #313244;
            width: 2px;
        }

        QStatusBar {
            background-color: #181825;
            color: #6c7086;
            font-size: 11px;
        }

        QStatusBar[severity="success"] { color: #a6e3a1; }
        QStatusBar[severity="warning"] { color: #f9e2af; }
        QStatusBar[severity="error"]   { color: #f38ba8; font-weight: bold; }

        QProgressBar {
            background-color: #313244;
            border: none;
            border-radius: 3px;
            height: 6px;
        }

        QProgressBar::chunk {
            background-color: #89b4fa;
            border-radius: 3px;
        }

        QToolBar {
            background-color: #181825;
            border: none;
            padding: 4px;
        }

        QLabel#title {
            font-size: 16px;
            font-weight: bold;
            color: #cdd6f4;
        }

        QLabel#source {
            color: #89b4fa;
            font-size: 11px;
        }

        QLabel#date {
            color: #6c7086;
            font-size: 11px;
        }

        QLabel#biasTag {
            background-color: #313244;
            color: #f38ba8;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
        }

        QLabel#biasExplanation {
            color: #a6adc8;
            font-size: 11px;
            font-style: italic;
        }

        QLabel#synthesisNotice {
            background-color: #313244;
            color: #f9e2af;
            border-radius: 6px;
            padding: 6px 8px;
            font-size: 12px;
        }

        QLabel#synthesisHeader {
            font-size: 13px;
            font-weight: bold;
            color: #89b4fa;
            padding: 4px 0px;
        }

        QTextEdit#synthesisText {
            background-color: #181825;
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 8px;
            color: #cdd6f4;
            font-size: 13px;
        }

        QTextEdit {
            background-color: #181825;
            border: 1px solid #313244;
            border-radius: 6px;
            color: #cdd6f4;
        }
    )");

    m_MainWindow = new MainWindow(nullptr);
    m_MainWindow->show();
}