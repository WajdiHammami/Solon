

#include "MainWindow.h"
#include "models/ArticleListModel.h"
#include "network/ApiClient.h"
#include <QListView>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QToolBar>
#include <QStyle>
#include <QCheckBox>
#include <QComboBox>
#include <QLabel>
#include "models/ArticleSortProxy.h"
#include "ui/ArticleItemDelegate.h"
#include "ui/views/ArticleDetailView.h"
#include "ui/views/SynthesisView.h"
#include "ui/dialogs/SettingsDialog.h"
#include "ui/Icons.h"
#include "app/ClientSettings.h"


MainWindow::MainWindow(QWidget* parent): QMainWindow(parent), m_settings(new ClientSettings(this)), m_apiClient(new ApiClient(this)), m_articleListModel(new ArticleListModel(this)), m_sortProxy(new ArticleSortProxy(this)){
    m_apiClient->setBaseUrl(m_settings->serverUrl());

   setupUI();
   setupConnections();
}



void MainWindow::setupUI(){
    setWindowTitle("Solon");
    resize(1200, 800);

    QToolBar* toolbar = new QToolBar(this);
    toolbar->setMovable(false);
    toolbar->setIconSize(QSize(22, 22));
    this->addToolBar(Qt::LeftToolBarArea, toolbar);
    QAction* settingsAction = toolbar->addAction(Icons::settings(QColor("#cdd6f4")), "Settings");
    settingsAction->setToolTip("Settings — server and request parameters");
    connect(settingsAction, &QAction::triggered, this, &MainWindow::openSettings);

    // Create the container widget
    QWidget* centralWidget = new QWidget(this);

    m_searchBar = new QLineEdit(centralWidget);
    m_searchBar->setPlaceholderText("Search a topic — leave empty for top headlines");
    m_searchBar->setClearButtonEnabled(true);
    m_searchButton = new QPushButton("Search", centralWidget);
    m_batchSummarize = new QPushButton(centralWidget);
    m_batchSummarize->setToolTip("Summarize the ticked articles and synthesize them");
    m_splitter = new QSplitter(Qt::Horizontal, centralWidget);
    m_synthesisSpliter = new QSplitter(Qt::Vertical, centralWidget);
    m_synthesisView = new SynthesisView(centralWidget);

    m_progressBar = new QProgressBar(this);
    m_progressBar->setRange(0, 0);
    m_progressBar->hide();

    m_statusBar = statusBar();
    statusBar()->addPermanentWidget(m_progressBar);
    showStatus("Ready");


    QVBoxLayout* main_layout = new QVBoxLayout(centralWidget);
    QHBoxLayout* searchLayout = new QHBoxLayout();
    main_layout->addLayout(searchLayout);

    searchLayout->addWidget(m_searchBar);
    searchLayout->addWidget(m_searchButton);
    searchLayout->addWidget(m_batchSummarize);

    main_layout->addWidget(m_splitter);


    // Article list: [Select all] ........ Sort by [combo] above the list.
    QWidget* listPanel = new QWidget(centralWidget);
    m_selectAll = new QCheckBox("Select all", listPanel);
    m_selectAll->setTristate(false);
    m_sortCombo = new QComboBox(listPanel);
    m_sortCombo->addItems(ArticleSortProxy::labels());
    QHBoxLayout* listHeader = new QHBoxLayout();
    listHeader->setContentsMargins(4, 0, 4, 0);
    listHeader->addWidget(m_selectAll);
    listHeader->addStretch();
    listHeader->addWidget(new QLabel("Sort by", listPanel));
    listHeader->addWidget(m_sortCombo);

    m_sortProxy->setSourceModel(m_articleListModel);
    m_articlesView = new QListView(listPanel);
    m_articlesView->setModel(m_sortProxy);
    m_articlesView->setItemDelegate(new ArticleItemDelegate(m_articlesView));
    m_articlesView->setMouseTracking(true);  // hover highlight + tooltips

    QVBoxLayout* listLayout = new QVBoxLayout(listPanel);
    listLayout->setContentsMargins(0, 0, 0, 0);
    listLayout->setSpacing(6);
    listLayout->addLayout(listHeader);
    listLayout->addWidget(m_articlesView);

    const int savedSort = m_settings->articleSort();
    const int sortIndex = (savedSort >= 0 && savedSort < m_sortCombo->count()) ? savedSort : 0;
    m_sortCombo->setCurrentIndex(sortIndex);
    m_sortProxy->setSortKey(static_cast<ArticleSortProxy::SortKey>(sortIndex));

    m_detailView = new ArticleDetailView(m_splitter);
    m_splitter->addWidget(m_synthesisSpliter);
    m_splitter->addWidget(m_detailView);

    m_synthesisSpliter->addWidget(listPanel);
    m_synthesisSpliter->addWidget(m_synthesisView);
    updateBatchControls();

    m_detailView->hide();

    setCentralWidget(centralWidget);
}


void MainWindow::setupConnections(){
    // Feed
    connect(m_searchButton, &QPushButton::clicked, this, [this](){
        if (m_feedInFlight) return;
        const QString topic = m_searchBar->text().trimmed();
        m_apiClient->fetchFeed(topic, m_settings->pageSize(), m_settings->page());
        m_feedInFlight = true;
        m_searchButton->setEnabled(false);
        beginRequest(topic.isEmpty() ? "Loading top headlines..." : QString("Searching \"%1\"...").arg(topic));
        m_synthesisView->clear();
    });
    connect(m_searchBar, &QLineEdit::returnPressed, m_searchButton, &QPushButton::click);
    connect(m_apiClient, &ApiClient::feedReceived, this, [this](const QList<Article>& articles){
        m_feedInFlight = false;
        m_searchButton->setEnabled(true);
        m_articleListModel->setArticles(articles);
        endRequest();
        if (articles.isEmpty()) {
            showStatus("No articles found — try another topic", Severity::Warning);
        } else {
            showStatus(QString("Loaded %1 articles").arg(articles.size()), Severity::Success);
        }
    });
    connect(m_articlesView, &QListView::clicked, this, [this](const QModelIndex& index){
        m_detailView->setArticle(articleAtViewRow(index));
        m_detailView->show();
    });

    // Selection and ordering
    connect(m_articleListModel, &ArticleListModel::checkedCountChanged, this, &MainWindow::updateBatchControls);
    connect(m_articleListModel, &QAbstractItemModel::modelReset, this, &MainWindow::updateBatchControls);
    connect(m_selectAll, &QCheckBox::clicked, this, [this](){
        const int total = m_articleListModel->allArticles().size();
        // Anything short of "all ticked" selects all; all ticked clears.
        m_articleListModel->setAllChecked(m_articleListModel->checkedCount() < total);
    });
    connect(m_sortCombo, &QComboBox::currentIndexChanged, this, [this](int index){
        m_sortProxy->setSortKey(static_cast<ArticleSortProxy::SortKey>(index));
        m_settings->setArticleSort(index);
    });

    // Batch analysis (ticked articles only)
    connect(m_batchSummarize, &QPushButton::clicked, this, [this](){
        const QList<Article> articles = m_articleListModel->checkedArticles();
        if (articles.isEmpty()) return;
        m_apiClient->analyzeArticles(articles);
        m_batchInFlight = true;
        updateBatchControls();
        beginRequest(QString("Analyzing %1 selected articles...").arg(articles.size()));
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

    connect(m_settings, &ClientSettings::changed, this, [this](){
        m_apiClient->setBaseUrl(m_settings->serverUrl());
        showStatus(QString("Settings saved — %1 articles per page, page %2, server %3")
            .arg(m_settings->pageSize()).arg(m_settings->page())
            .arg(m_settings->serverUrl().toString()), Severity::Success);
    });
}


void MainWindow::updateBatchControls(){
    const int checked = m_articleListModel->checkedCount();
    const int total = m_articleListModel->allArticles().size();
    m_batchSummarize->setText(checked > 0 ? QString("Summarize Selected (%1)").arg(checked)
                                          : QString("Summarize Selected"));
    m_batchSummarize->setEnabled(checked > 0 && !m_batchInFlight);
    if (m_batchInFlight) m_batchSummarize->setText("Summarizing...");

    // Mirror the ticks in "Select all" without re-triggering it.
    const QSignalBlocker blocker(m_selectAll);
    m_selectAll->setEnabled(total > 0);
    m_selectAll->setCheckState(checked == 0 ? Qt::Unchecked
                               : checked == total ? Qt::Checked : Qt::PartiallyChecked);
}


Article MainWindow::articleAtViewRow(const QModelIndex& viewIndex) const {
    return m_articleListModel->articleAt(m_sortProxy->mapToSource(viewIndex).row());
}


void MainWindow::openSettings(){
    SettingsDialog dialog(m_settings->values(), this);
    if (dialog.exec() == QDialog::Accepted) {
        m_settings->apply(dialog.values());
    }
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
    updateBatchControls();
    endRequest();

    const QString summary = QString("Analyzed %1 articles — %2 failed tasks, %3 skipped")
        .arg(batch.analyses.size()).arg(batch.failed.size()).arg(batch.skipped.size());
    if (batch.analyses.isEmpty() && !batch.failed.isEmpty()) {
        showStatus("Analysis failed — " + summary + " (details above the synthesis)", Severity::Error);
    } else if (!batch.failed.isEmpty() || !batch.skipped.isEmpty()) {
        showStatus(summary + " (details above the synthesis)", Severity::Warning);
    } else {
        showStatus(summary, Severity::Success);
    }
}


void MainWindow::onArticleAnalysis(int articleId, const ArticleAnalysis& analysis, const QList<TaskFailure>& failures){
    m_articleListModel->applyAnalysis(articleId, analysis);
    refreshDetailView(articleId);
    endRequest();

    if (failures.isEmpty()) {
        showStatus("Article analyzed", Severity::Success);
        return;
    }
    QStringList messages;
    for (const TaskFailure& failure : failures) messages << describeFailure(failure);
    const bool nothingProduced = analysis.summary.isEmpty() && analysis.biasLabel.isEmpty();
    showStatus((nothingProduced ? "Article analysis failed — " : "Partly analyzed — ") + messages.join("; "),
               nothingProduced ? Severity::Error : Severity::Warning);
}


void MainWindow::onContent(const QString& url, const QString& content){
    m_articleListModel->setFullText(url, content);
    endRequest();
    if (content.isEmpty()) {
        showStatus("Couldn't extract this article's text (paywalled or unsupported page)", Severity::Warning);
        return;
    }
    showStatus("Article's content received", Severity::Success);

    // Only open the reader if the user is still looking at that article.
    if (m_detailView->hasArticle() && m_detailView->article().url == url) {
        refreshDetailView(m_detailView->article().id);
        m_detailView->showContent(content);
    }
}


void MainWindow::onError(ApiClient::Request request, const QString& message){
    // Every failure ends that request's loading state and re-enables its controls.
    endRequest();
    QString what;
    switch (request) {
        case ApiClient::Request::Feed:
            what = "Loading articles";
            m_feedInFlight = false;
            m_searchButton->setEnabled(true);
            break;
        case ApiClient::Request::Analyze:
            what = "Analysis";
            m_batchInFlight = false;
            updateBatchControls();
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
    showStatus(QString("%1 failed: %2").arg(what, message), Severity::Error);
}


void MainWindow::showStatus(const QString& message, Severity severity){
    static const char* names[] = {"info", "success", "warning", "error"};
    static const char* icons[] = {"", "✔ ", "⚠ ", "✖ "};
    const int i = static_cast<int>(severity);
    m_statusBar->setProperty("severity", names[i]);
    // Re-evaluate the stylesheet now that the property changed.
    m_statusBar->style()->unpolish(m_statusBar);
    m_statusBar->style()->polish(m_statusBar);
    m_statusBar->showMessage(QString::fromUtf8(icons[i]) + message);
}


void MainWindow::beginRequest(const QString& status){
    ++m_pendingRequests;
    m_progressBar->show();
    showStatus(status);
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
