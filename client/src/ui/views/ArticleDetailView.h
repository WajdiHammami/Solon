
#pragma once

#include <QWidget>
#include "models/Article.h"


class QLabel;
class QPushButton;

class ArticleDetailView : public QWidget {
    Q_OBJECT
public:
    explicit ArticleDetailView(QWidget* parent=nullptr);
    void setArticle(const Article& article);
    const Article& article() const;
    bool hasArticle() const;
    void showContent(const QString& content);

signals:
    void summarizeRequest(const Article article);
    void contentRequest(const QString& url);

private:
    void updateButtons();
    void updateBias();

    QLabel* m_title;
    QLabel* m_source;
    QLabel* m_date;
    QLabel* m_link;
    QLabel* m_biasTag;
    QLabel* m_biasExplanation;
    QLabel* m_summaryHeading;
    QLabel* m_summary;

    Article m_article;

    QPushButton* m_readButton;
    QPushButton* m_summarizeButton;
};
