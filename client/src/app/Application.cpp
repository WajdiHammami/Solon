
#include "Application.h"
#include "ui/MainWindow.h"

Application::Application(int argc, char* argv[]): QApplication(argc, argv), m_MainWindow(new MainWindow(nullptr)){
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
            color: #cdd6f4;
        }

        QListView::item:hover {
            background-color: #313244;
        }

        QListView::item:selected {
            background-color: #45475a;
            color: #cdd6f4;
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

    m_MainWindow->show();
}