
#pragma once

#include <QAbstractListModel>
#include <QList>
#include <optional>
#include "Article.h"
#include "Analysis.h"


class ArticleListModel : public QAbstractListModel{
    Q_OBJECT
public:
    explicit ArticleListModel(QObject* parent=nullptr): QAbstractListModel(parent){}
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role=Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;
    Article articleAt(int row) const;
    const QList<Article>& allArticles() const;
    std::optional<Article> articleById(int id) const;

    // In-place updates; return false when no article matches.
    bool applyAnalysis(int articleId, const ArticleAnalysis& analysis);
    bool setFullText(const QString& url, const QString& text);
public slots:
    void setArticles(const QList<Article>& articles);

private:
    int rowForId(int id) const;
    QList<Article> m_articles;

    enum ArticleRole {
        TitleRole = Qt::UserRole + 1,
        SourceRole,
        UrlRole,
        PublishedAtRole,
        SummaryRole,
        TagRole
};
};

