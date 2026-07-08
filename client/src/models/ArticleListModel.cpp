

#include "ArticleListModel.h"


int ArticleListModel::rowCount(const QModelIndex& parent) const {
    if (parent.isValid()) return 0;
    return m_articles.size();
}


QVariant ArticleListModel::data(const QModelIndex& index, int role) const {
    if (!index.isValid() || index.row() >= m_articles.size()) return {};
    switch(role) {
        case Qt::DisplayRole:
        case TitleRole:       return m_articles.at(index.row()).title;
        case SourceRole:      return m_articles.at(index.row()).source_name;
        case UrlRole:         return m_articles.at(index.row()).url;
        case PublishedAtRole: return m_articles.at(index.row()).published_at;
        case SummaryRole:     return m_articles.at(index.row()).summary;
        default:              return {};
    }
}


QHash<int, QByteArray> ArticleListModel::roleNames() const{
    return {
        {TitleRole,       "title"},
        {SourceRole,      "source"},
        {UrlRole,         "url"},
        {PublishedAtRole, "publishedAt"},
        {SummaryRole,     "summary"}
        };
}



void ArticleListModel::setArticles(const QList<Article>& articles){
    beginResetModel();
    m_articles = articles;
    endResetModel();
}


Article ArticleListModel::articleAt(int row) const {
    return m_articles.at(row);
}



QList<Article> ArticleListModel::allArticles(){
    return m_articles;
}