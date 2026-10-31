

#include "MainWindow.h"
#include "models/ArticleListModel.h"
#include "network/ApiClient.h"
#include <QListView>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QToolBar>
#include "ui/views/ArticleDetailView.h"
#include "ui/views/SynthesisView.h"



MainWindow::MainWindow(QWidget* parent): QMainWindow(parent), m_apiClient(new ApiClient(this)), m_articleListModel(new ArticleListModel(this)){

   setupUI();
   setupConnections();
}



void MainWindow::setupUI(){
    setWindowTitle("Solon");
    resize(1200, 800);

    QToolBar* toolbar = new QToolBar(this);
    this->addToolBar(Qt::LeftToolBarArea, toolbar);

    // Create the container widget
    QWidget* centralWidget = new QWidget(this);

    m_searchBar = new QLineEdit(centralWidget);
    m_searchButton = new QPushButton("Search", centralWidget);
    m_batchSummarize = new QPushButton("Summarize All", centralWidget);
    m_batchSummarize->setEnabled(false);  // until there are articles
    m_splitter = new QSplitter(Qt::Horizontal, centralWidget);
    m_synthesisSpliter = new QSplitter(Qt::Vertical, centralWidget);
    m_synthesisView = new SynthesisView(centralWidget);

    m_progressBar = new QProgressBar(this);
    m_progressBar->setRange(0, 0);
    m_progressBar->hide();

    m_statusBar = statusBar();
    statusBar()->addPermanentWidget(m_progressBar);
    statusBar()->showMessage("Ready");


    QVBoxLayout* main_layout = new QVBoxLayout(centralWidget);
    QHBoxLayout* searchLayout = new QHBoxLayout();
    main_layout->addLayout(searchLayout);

    searchLayout->addWidget(m_searchBar);
    searchLayout->addWidget(m_searchButton);
    searchLayout->addWidget(m_batchSummarize);

    main_layout->addWidget(m_splitter);


    m_articlesView = new QListView(centralWidget);
    m_articlesView->setModel(m_articleListModel);
    m_detailView = new ArticleDetailView(m_splitter);
    m_splitter->addWidget(m_synthesisSpliter);
    m_splitter->addWidget(m_detailView);

    m_synthesisSpliter->addWidget(m_articlesView);
    m_synthesisSpliter->addWidget(m_synthesisView);

    m_detailView->hide();

    setCentralWidget(centralWidget);
}


void MainWindow::setupConnections(){
    // Feed
    connect(m_searchButton, &QPushButton::clicked, this, [this](){
        m_apiClient->fetchFeed(m_searchBar->text(), 5, 1);
        beginRequest("Loading...");
        m_synthesisView->clear();
    });
    connect(m_searchBar, &QLineEdit::returnPressed, m_searchButton, &QPushButton::click);
    connect(m_apiClient, &ApiClient::feedReceived, this, [this](const QList<Article>& articles){
        m_articleListModel->setArticles(articles);
        m_batchSummarize->setEnabled(!articles.isEmpty() && !m_batchInFlight);
        endRequest();
        m_statusBar->showMessage(QString("Loaded %1 articles").arg(articles.size()));
    });
    connect(m_articlesView, &QListView::clicked, this, [this](const QModelIndex& index){
        m_detailView->setArticle(m_articleListModel->articleAt(index.row()));
        m_detailView->show();
    });

    // Batch analysis
    connect(m_batchSummarize, &QPushButton::clicked, this, [this](){
        const QList<Article>& articles = m_articleListModel->allArticles();
        if (articles.isEmpty()) return;
        m_apiClient->analyzeArticles(articles);
        m_batchInFlight = true;
        m_batchSummarize->setEnabled(false);
        beginRequest(QString("Analyzing %1 articles...").arg(articles.size()));
    });
    connect(m_apiClient, &ApiClient::batchAnalysisReceived, this, &MainWindow::onBatchAnalysis);

    // Single article
    connect(m_detailView, &ArticleDetailView::summarizeRequest, this, [this](const Article& article){
        m_apiClient->analyzeArticle(article);
        beginRequest("Analyzing article...");
    });
    connect(m_apiClient, &ApiClient::articleAnalysisReceived, this, &MainWindow::onArticleAnalysis);

    // Full content
    connect(m_detailView, &ArticleDetailView::contentRequest, this, [this](const QString& url){
        m_apiClient->contentRequest(url);
        beginRequest("Downloading content...");
    });
    connect(m_apiClient, &ApiClient::contentReceived, this, &MainWindow::onContent);

    connect(m_apiClient, &ApiClient::errorOccurred, this, &MainWindow::onError);
}


void MainWindow::onBatchAnalysis(const BatchAnalysis& batch){
    for (auto it = batch.analyses.begin(); it != batch.analyses.end(); ++it) {
        m_articleListModel->applyAnalysis(it.key(), it.value());
        refreshDetailView(it.key());
    }

    QStringList notices;
    for (const TaskFailure& failure : batch.failed) {
        notices << describeFailure(failure);
    }
    if (!batch.skipped.isEmpty()) {
        QStringList titles;
        for (int id : batch.skipped) {
            if (auto article = m_articleListModel->articleById(id)) titles << article->title;
        }
        notices << QString("Skipped to stay within the token budget: %1").arg(titles.join("; "));
    }
    m_synthesisView->setNotices(notices);
    m_synthesisView->setSynthesis(batch.synthesis.isEmpty()
        ? QString("*No synthesis available.*")
        : batch.synthesis);

    m_batchInFlight = false;
    m_batchSummarize->setEnabled(!m_articleListModel->allArticles().isEmpty());
    endRequest();
    m_statusBar->showMessage(QString("Analyzed %1 articles — %2 failed tasks, %3 skipped")
        .arg(batch.analyses.size()).arg(batch.failed.size()).arg(batch.skipped.size()));
}


void MainWindow::onArticleAnalysis(int articleId, const ArticleAnalysis& analysis, const QList<TaskFailure>& failures){
    m_articleListModel->applyAnalysis(articleId, analysis);
    refreshDetailView(articleId);
    endRequest();

    if (failures.isEmpty()) {
        m_statusBar->showMessage("Article analyzed");
        return;
    }
    QStringList messages;
    for (const TaskFailure& failure : failures) messages << describeFailure(failure);
    m_statusBar->showMessage("Partly analyzed — " + messages.join("; "));
}


void MainWindow::onContent(const QString& url, const QString& content){
    m_articleListModel->setContent(url, content);
    endRequest();
    m_statusBar->showMessage("Article's content received");

    // Only open the reader if the user is still looking at that article.
    if (m_detailView->hasArticle() && m_detailView->article().url == url) {
        refreshDetailView(m_detailView->article().id);
        m_detailView->showContent(content);
    }
}


void MainWindow::onError(ApiClient::Request request, const QString& message){
    endRequest();
    QString what;
    switch (request) {
        case ApiClient::Request::Feed:
            what = "Loading articles";
            break;
        case ApiClient::Request::Analyze:
            what = "Analysis";
            m_batchInFlight = false;
            m_batchSummarize->setEnabled(!m_articleListModel->allArticles().isEmpty());
            break;
        case ApiClient::Request::AnalyzeArticle:
            what = "Article analysis";
            // Re-enables the detail view's "Summarize" button.
            if (m_detailView->hasArticle()) refreshDetailView(m_detailView->article().id);
            break;
        case ApiClient::Request::Content:
            what = "Downloading content";
            break;
    }
    m_statusBar->showMessage(QString("%1 failed: %2").arg(what, message));
}


void MainWindow::beginRequest(const QString& status){
    ++m_pendingRequests;
    m_progressBar->show();
    m_statusBar->showMessage(status);
}


void MainWindow::endRequest(){
    m_pendingRequests = qMax(0, m_pendingRequests - 1);
    if (m_pendingRequests == 0) m_progressBar->hide();
}


void MainWindow::refreshDetailView(int articleId){
    if (!m_detailView->hasArticle() || m_detailView->article().id != articleId) return;
    if (auto article = m_articleListModel->articleById(articleId)) {
        m_detailView->setArticle(*article);
    }
}


QString MainWindow::describeFailure(const TaskFailure& failure) const {
    static const QMap<QString, QString> taskNames = {
        {"summarize", "Summary"},
        {"detect_bias", "Bias detection"},
        {"synthesize", "Synthesis"},
    };
    QString what = taskNames.value(failure.task, failure.task);
    if (failure.articleId >= 0) {
        if (auto article = m_articleListModel->articleById(failure.articleId)) {
            what += QString(" for \"%1\"").arg(article->title);
        }
    }
    return QString("%1 failed%2").arg(what, failure.retryable ? " (try again later)" : "");
}
