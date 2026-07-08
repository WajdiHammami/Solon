
#pragma once

#include <QMainWindow>
#include <QPushButton>
#include <QSplitter>
#include <QProgressBar>
#include <QLineEdit>
#include <QStatusBar>


class ApiClient;
class ArticleListModel;
class ArticleDetailView;
class QListView;
class SynthesisView;

class MainWindow : public QMainWindow{
    Q_OBJECT
public:
    MainWindow(QWidget* parent = nullptr);

private:
    void setupUI();
    void setupConnections();
    ApiClient* m_apiClient;
    ArticleListModel* m_articleListModel;
    QLineEdit* m_searchBar;
    QPushButton* m_searchButton;
    QPushButton* m_batchSummarize;
    QSplitter* m_splitter;
    QProgressBar* m_progressBar;
    QStatusBar* m_statusBar;
    QListView* m_articlesView;
    ArticleDetailView* m_detailView;
    QSplitter* m_synthesisSpliter;
    SynthesisView* m_synthesisView;
};