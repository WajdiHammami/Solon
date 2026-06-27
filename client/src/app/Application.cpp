
#include "Application.h"
#include "ui/MainWindow.h"

Application::Application(int argc, char* argv[]): QApplication(argc, argv), m_MainWindow(new MainWindow(nullptr)){
    setApplicationName("Solon");
    m_MainWindow->show();
}