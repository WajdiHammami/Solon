
#pragma once

#include <QAbstractListModel>
#include <QList>
#include "Article.h"


class ArticleListModel : public QAbstractListModel{
    Q_OBJECT
public:
    explicit ArticleListModel(QObject* parent=nullptr): QAbstractListModel(parent){}
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role=Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;
    Article articleAt(int row) const;
    QList<Article> allArticles();
public slots:
    void setArticles(const QList<Article>& articles);

private:
    QList<Article> m_articles;
    
    enum ArticleRole {
        TitleRole = Qt::UserRole + 1,
        SourceRole,
        UrlRole,
        PublishedAtRole,
        SummaryRole
};
};


