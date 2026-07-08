

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
    //m_splitter->addWidget();

    m_synthesisSpliter->addWidget(m_articlesView);
    m_synthesisSpliter->addWidget(m_synthesisView);

    m_detailView->hide();

    setCentralWidget(centralWidget);
}


void MainWindow::setupConnections(){
    connect(m_apiClient, &ApiClient::feedReceived, this, [this](const QList<Article>& articles){
        m_articleListModel->setArticles(articles);
        m_progressBar->hide();
        m_statusBar->showMessage("Finished");
    });
    connect(m_searchButton, &QPushButton::clicked, this, [this](){
        m_apiClient->fetchFeed(m_searchBar->text(), 20, 1);
        m_statusBar->showMessage("Loading...");
        m_progressBar->show();
        m_synthesisView->setSynthesis("");
    });
    connect(m_articlesView, &QListView::clicked, this, [this](const QModelIndex& index){
        m_detailView->setArticle(m_articleListModel->articleAt(index.row()));
        m_detailView->show();
    });
    
    // Summarize all articles
    connect(m_batchSummarize, &QPushButton::clicked, this, [this](){
        m_apiClient->summarizeRequest(m_articleListModel->allArticles());
        m_statusBar->showMessage("Summarizing Articles...");
        m_progressBar->show();
    });
    connect(m_apiClient, &ApiClient::summarizationMultiArticleReceived, this, [this](const QList<QString>& summaries, const QString& synthesis, const QMap<int, QPair<QString, QString>>& tags){
       int i = 0;
       QList<Article> updated = m_articleListModel->allArticles();   // Eat a lot of memory need a cleaner fix. Create updateSummaries method.
       for(Article& article : updated){
            article.summary = summaries[i++];
            article.tag = tags[article.id].first;
       }
       m_articleListModel->setArticles(updated);
       m_synthesisView->setSynthesis(synthesis);
       m_statusBar->showMessage("Finished Summarizing Articles");
       m_progressBar->hide();
    });


    connect(m_detailView, &ArticleDetailView::summarizeRequest, m_apiClient, [this](const Article& article){
        m_apiClient->summarizeRequest({article});
        m_progressBar->show();
        m_statusBar->showMessage("Sent a Summarization Request");
    });

    connect(m_apiClient, &ApiClient::summarizationOneArticleReceived, this, [this](const Article& article){
        m_detailView->setArticle(article);
        QList<Article> updated = m_articleListModel->allArticles();
        for(Article& a: updated){
            if (a.id == article.id) {a.summary = article.summary; a.tag = article.tag; break;}
        }

        m_articleListModel->setArticles(updated);
        m_progressBar->hide();
        m_statusBar->showMessage("Article Summarized");
    });

    connect(m_detailView, &ArticleDetailView::contentRequest, this, [this](const QString& url){
        m_apiClient->contentRequest(url);
        m_progressBar->show();
        m_statusBar->showMessage("Download Content");
    });

    connect(m_apiClient, &ApiClient::contentReceived, this, [this](const QString& content){
        Article* article = m_detailView->getArticle();
        QList<Article> updated = m_articleListModel->allArticles();
        for(Article& a: updated){
            if (a.id == article->id) {a.content = content; m_detailView->setArticle(a);};
        }
        m_articleListModel->setArticles(updated);
        m_statusBar->showMessage("Article's Content Received");
        m_progressBar->hide();
        m_detailView->showContent(content);
    });


 }