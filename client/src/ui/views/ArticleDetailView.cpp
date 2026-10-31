

#include "ArticleDetailView.h"
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QDialog>
#include <QTextEdit>

ArticleDetailView::ArticleDetailView(QWidget* parent)
    : QWidget(parent),
      m_title(new QLabel(this)),
      m_source(new QLabel(this)),
      m_date(new QLabel(this)),
      m_summary(new QLabel(this)),
      m_biasTag(new QLabel(this)),
      m_biasExplanation(new QLabel(this)),
      m_readButton(new QPushButton("Read Full Article", this)),
      m_summarizeButton(new QPushButton("Summarize", this)) {


    setFixedWidth(420);

    m_title->setObjectName("title");
    m_title->setWordWrap(true);
    m_source->setObjectName("source");
    m_date->setObjectName("date");
    m_biasTag->setObjectName("biasTag");

    m_biasTag->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
    m_biasExplanation->setObjectName("biasExplanation");
    m_biasExplanation->setWordWrap(true);
    m_biasExplanation->hide();
    m_summary->setWordWrap(true);
    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(16, 16, 16, 16);
    layout->setSpacing(4);

    // compact header block
    QVBoxLayout* headerLayout = new QVBoxLayout();
    headerLayout->setSpacing(2);
    headerLayout->addWidget(m_title);

    QHBoxLayout* infoLayout = new QHBoxLayout();
    infoLayout->setSpacing(8);
    infoLayout->addWidget(m_source);
    infoLayout->addWidget(m_date);
    infoLayout->addWidget(m_biasTag);
    infoLayout->addStretch();
    headerLayout->addLayout(infoLayout);

    layout->addLayout(headerLayout);
    layout->addWidget(m_biasExplanation);
    layout->addSpacing(8);
    layout->addWidget(m_summary);
    layout->addStretch();

    QHBoxLayout* buttonsLayout = new QHBoxLayout();
    buttonsLayout->addWidget(m_readButton);
    buttonsLayout->addWidget(m_summarizeButton);
    layout->addLayout(buttonsLayout);
    setLayout(layout);

    updateButtons();

    // Connections:
    connect(m_summarizeButton, &QPushButton::clicked, this, [this](){
        emit summarizeRequest(m_article); 
        m_summarizeButton->setDisabled(true);
    });

    connect(m_readButton, &QPushButton::clicked, this, [this](){
        if(m_article.full_text.isEmpty()){
            emit contentRequest(m_article.url);
        }else{
            showContent(m_article.full_text);
        }

   });
}


void ArticleDetailView::setArticle(const Article& article) {
    m_title->setText(article.title);
    m_source->setText(article.source_name);
    m_date->setText(article.published_at);
    if (article.summary.isEmpty()) {
        m_summary->setText("No summary available.");
    } else {
        m_summary->setText(article.summary);
    }
    if (article.tag.isEmpty()) {
        m_biasTag->setText("No bias tag available.");
    } else if (article.tag == "None") {
        m_biasTag->setText("No notable bias");
    } else {
        m_biasTag->setText(article.tag);
    }
    m_biasExplanation->setText(article.tag_explanation);
    m_biasExplanation->setVisible(!article.tag_explanation.isEmpty());
    m_article = article;
    updateButtons();
}


void ArticleDetailView::updateButtons(){
    // Nothing to act on until an article is shown; summarize only once.
    m_readButton->setEnabled(hasArticle());
    m_summarizeButton->setEnabled(hasArticle() && m_article.summary.isEmpty());
}


const Article& ArticleDetailView::article() const {
    return m_article;
}


bool ArticleDetailView::hasArticle() const {
    return m_article.id >= 0;
}


void ArticleDetailView::showContent(const QString& content){
    QDialog* dialog = new QDialog(this);
    dialog->setAttribute(Qt::WA_DeleteOnClose);
    dialog->setWindowTitle(m_article.title);
    dialog->resize(750, 620);

    QLabel* title = new QLabel(m_article.title, dialog);
    title->setWordWrap(true);
    title->setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4; padding: 0 0 8px 0;");

    QLabel* meta = new QLabel(m_article.source_name + "  •  " + m_article.published_at, dialog);
    meta->setStyleSheet("font-size: 12px; color: #6c7086;");

    QLabel* urlLabel = new QLabel("<a href=\"" + m_article.url + "\" style=\"color: #89dceb; text-decoration: none;\">" + m_article.url + "</a>", dialog);
    urlLabel->setWordWrap(true);
    urlLabel->setOpenExternalLinks(true);
    urlLabel->setStyleSheet("font-size: 12px;");

    QTextEdit* textEdit = new QTextEdit(dialog);
    textEdit->setReadOnly(true);
    textEdit->setPlainText(content);
    textEdit->setStyleSheet(R"(
        QTextEdit {
            font-family: Georgia, serif;
            font-size: 15px;
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: none;
            padding: 8px;
        }
    )");

    QVBoxLayout* layout = new QVBoxLayout(dialog);
    layout->setContentsMargins(24, 20, 24, 20);
    layout->setSpacing(4);
    layout->addWidget(title);
    layout->addWidget(meta);
    layout->addWidget(urlLabel);
    layout->addSpacing(12);
    layout->addWidget(textEdit);

    dialog->show();
}