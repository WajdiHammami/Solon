
#pragma once

#include <QMainWindow>
#include <QPushButton>
#include <QSplitter>
#include <QProgressBar>
#include <QLineEdit>
#include <QStatusBar>
#include "models/Analysis.h"
#include "network/ApiClient.h"


class ArticleListModel;
class ClientSettings;
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

    void onBatchAnalysis(const BatchAnalysis& batch);
    void onArticleAnalysis(int articleId, const ArticleAnalysis& analysis, const QList<TaskFailure>& failures);
    void onContent(const QString& url, const QString& content);
    void onError(ApiClient::Request request, const QString& message);
    void openSettings();

    enum class Severity { Info, Success, Warning, Error };
    // Status bar text, colored by severity (see QStatusBar[severity] in the stylesheet).
    void showStatus(const QString& message, Severity severity = Severity::Info);

    // Progress bar stays visible while any request is in flight.
    void beginRequest(const QString& status);
    void endRequest();
    void refreshDetailView(int articleId);
    QString describeFailure(const TaskFailure& failure) const;

    ClientSettings* m_settings;
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
    int m_pendingRequests = 0;
    bool m_batchInFlight = false;
    bool m_feedInFlight = false;
};
