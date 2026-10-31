

#include "ArticleDetailView.h"
#include <QDialog>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QRegularExpression>
#include <QScrollArea>
#include <QTextBrowser>
#include <QVBoxLayout>
#include "ui/ArticleItemDelegate.h"
#include "ui/Format.h"

namespace {

QString linkHtml(const QString& url, const QString& text){
    return QString("<a href=\"%1\" style=\"color:#89dceb; text-decoration:none;\">%2</a>")
        .arg(url.toHtmlEscaped(), text.toHtmlEscaped());
}

// Plain text -> paragraphs; blank lines (or single newlines) separate them.
QString paragraphsHtml(const QString& text){
    const QString normalized = QString(text).replace("\r\n", "\n");
    const QStringList blocks = normalized.contains("\n\n")
        ? normalized.split(QRegularExpression("\n\\s*\n"), Qt::SkipEmptyParts)
        : normalized.split('\n', Qt::SkipEmptyParts);
    QString html;
    for (const QString& block : blocks) {
        const QString trimmed = block.trimmed();
        if (!trimmed.isEmpty()) html += "<p>" + trimmed.toHtmlEscaped() + "</p>";
    }
    return html;
}

}  // namespace


ArticleDetailView::ArticleDetailView(QWidget* parent)
    : QWidget(parent),
      m_title(new QLabel(this)),
      m_source(new QLabel(this)),
      m_date(new QLabel(this)),
      m_link(new QLabel(this)),
      m_biasTag(new QLabel(this)),
      m_biasExplanation(new QLabel(this)),
      m_summaryHeading(new QLabel("SUMMARY", this)),
      m_summary(new QLabel(this)),
      m_readButton(new QPushButton("Read Full Article", this)),
      m_summarizeButton(new QPushButton("Summarize", this)) {

    setObjectName("detailPanel");
    setMinimumWidth(380);
    setMaximumWidth(560);

    m_title->setObjectName("detailTitle");
    m_title->setWordWrap(true);
    m_title->setTextInteractionFlags(Qt::TextSelectableByMouse);

    m_source->setObjectName("sourcePill");
    m_date->setObjectName("detailDate");
    m_link->setObjectName("detailLink");
    m_link->setOpenExternalLinks(true);

    m_biasTag->setObjectName("biasChip");
    m_biasExplanation->setObjectName("biasExplanation");
    m_biasExplanation->setWordWrap(true);

    m_summaryHeading->setObjectName("sectionHeading");
    m_summary->setObjectName("detailSummary");
    m_summary->setWordWrap(true);
    m_summary->setTextFormat(Qt::RichText);
    m_summary->setTextInteractionFlags(Qt::TextSelectableByMouse);
    m_summary->setAlignment(Qt::AlignTop | Qt::AlignLeft);

    m_summarizeButton->setObjectName("secondaryButton");

    // Scrollable content: long summaries never push the buttons off-screen.
    QWidget* content = new QWidget(this);
    content->setObjectName("detailContent");
    QVBoxLayout* contentLayout = new QVBoxLayout(content);
    contentLayout->setContentsMargins(22, 20, 22, 16);
    contentLayout->setSpacing(10);

    QHBoxLayout* meta = new QHBoxLayout();
    meta->setSpacing(10);
    meta->addWidget(m_source);
    meta->addWidget(m_date);
    meta->addStretch();

    QHBoxLayout* biasRow = new QHBoxLayout();
    biasRow->addWidget(m_biasTag);
    biasRow->addStretch();

    contentLayout->addLayout(meta);
    contentLayout->addWidget(m_title);
    contentLayout->addWidget(m_link);
    contentLayout->addSpacing(6);
    contentLayout->addLayout(biasRow);
    contentLayout->addWidget(m_biasExplanation);
    contentLayout->addSpacing(8);
    contentLayout->addWidget(m_summaryHeading);
    contentLayout->addWidget(m_summary);
    contentLayout->addStretch();

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setObjectName("detailScroll");
    scroll->setWidget(content);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);

    QHBoxLayout* buttonsLayout = new QHBoxLayout();
    buttonsLayout->setContentsMargins(22, 10, 22, 18);
    buttonsLayout->setSpacing(10);
    buttonsLayout->addWidget(m_readButton);
    buttonsLayout->addWidget(m_summarizeButton);

    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);
    layout->addWidget(scroll, 1);
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
    m_article = article;
    m_title->setText(Format::displayTitle(article.title, article.source_name));
    m_source->setText(article.source_name);
    m_source->setVisible(!article.source_name.isEmpty());
    m_date->setText(Format::longDate(article.published_at));
    m_link->setText(linkHtml(article.url, "Open original ↗"));

    if (article.summary.isEmpty()) {
        m_summary->setText("<span style=\"color:#7f849c;\">Not summarized yet — click "
                           "<b>Summarize</b> to generate a summary and bias check.</span>");
    } else {
        m_summary->setText("<div style=\"line-height:155%;\">"
                           + paragraphsHtml(article.summary) + "</div>");
    }
    updateBias();
    updateButtons();
}


void ArticleDetailView::updateBias(){
    const QString& tag = m_article.tag;
    m_biasTag->setVisible(!tag.isEmpty());
    m_biasExplanation->setVisible(!tag.isEmpty() && !m_article.tag_explanation.isEmpty());
    if (tag.isEmpty()) return;

    // Same colors as the list badges, so a label looks the same everywhere.
    const QColor color = ArticleItemDelegate::badgeColor(tag);
    m_biasTag->setText(tag.compare("None", Qt::CaseInsensitive) == 0
                           ? QString("No notable bias") : QString("Bias: %1").arg(tag));
    m_biasTag->setStyleSheet(QString(
        "color:%1; background-color:rgba(%2,%3,%4,0.15); border:1px solid %1;")
        .arg(color.name()).arg(color.red()).arg(color.green()).arg(color.blue()));
    m_biasExplanation->setText(m_article.tag_explanation);
    m_biasExplanation->setStyleSheet(QString("border-left: 3px solid %1;").arg(color.name()));
}


void ArticleDetailView::updateButtons(){
    // Nothing to act on until an article is shown. Summarize stays available
    // while either part is missing; the server computes only what's missing.
    m_readButton->setEnabled(hasArticle());
    const bool complete = !m_article.summary.isEmpty() && !m_article.tag.isEmpty();
    m_summarizeButton->setEnabled(hasArticle() && !complete);
    m_summarizeButton->setText(complete ? "Summarized ✓" : "Summarize");
}


const Article& ArticleDetailView::article() const {
    return m_article;
}


bool ArticleDetailView::hasArticle() const {
    return m_article.id >= 0;
}


void ArticleDetailView::showContent(const QString& content){
    QDialog* dialog = new QDialog(this);
    dialog->setObjectName("reader");
    dialog->setAttribute(Qt::WA_DeleteOnClose);
    dialog->setWindowTitle(Format::displayTitle(m_article.title, m_article.source_name));
    dialog->resize(880, 760);

    QTextBrowser* browser = new QTextBrowser(dialog);
    browser->setObjectName("readerText");
    browser->setOpenExternalLinks(true);
    browser->setFrameShape(QFrame::NoFrame);
    browser->document()->setDocumentMargin(28);
    browser->document()->setDefaultStyleSheet(R"(
        h1      { font-size: 28px; font-weight: bold; color: #cdd6f4; margin-bottom: 14px; }
        p       { font-size: 17px; line-height: 165%; color: #cdd6f4; margin-bottom: 14px; }
        p.meta  { font-size: 13px; line-height: 100%; color: #7f849c; margin-bottom: 4px; }
        p.link  { font-size: 13px; line-height: 100%; margin-bottom: 30px; }
    )");

    QStringList meta;
    if (!m_article.source_name.isEmpty()) meta << m_article.source_name;
    const QString date = Format::longDate(m_article.published_at);
    if (!date.isEmpty()) meta << date;

    browser->setHtml(
        "<h1>" + Format::displayTitle(m_article.title, m_article.source_name).toHtmlEscaped() + "</h1>"
        + "<p class=\"meta\">" + meta.join("  ·  ").toHtmlEscaped() + "</p>"
        + "<p class=\"link\">" + linkHtml(m_article.url, "Open original ↗") + "</p>"
        + paragraphsHtml(content));

    // A centered column of comfortable measure (~70 characters per line).
    QHBoxLayout* column = new QHBoxLayout();
    column->addStretch(1);
    column->addWidget(browser, 6);
    column->addStretch(1);
    browser->setMinimumWidth(520);
    browser->setMaximumWidth(760);

    QVBoxLayout* layout = new QVBoxLayout(dialog);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addLayout(column);

    dialog->show();
}
