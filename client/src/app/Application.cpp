
#include "Application.h"
#include <QFile>
#include "ui/MainWindow.h"

Application::Application(int argc, char* argv[]): QApplication(argc, argv), m_MainWindow(nullptr){
    // QSettings stores under organization/application, so set both before
    // anything (MainWindow's ClientSettings) reads settings.
    setOrganizationName("Solon");
    setApplicationName("Solon");

    // Theme lives in app/style.qss, compiled in via resources.qrc.
    QFile style(":/style.qss");
    if (style.open(QIODevice::ReadOnly)) {
        setStyleSheet(QString::fromUtf8(style.readAll()));
    }

    m_MainWindow = new MainWindow(nullptr);
    m_MainWindow->show();
}