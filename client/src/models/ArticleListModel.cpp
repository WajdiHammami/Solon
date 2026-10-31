

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
        case TagRole:         return m_articles.at(index.row()).tag;
        default:              return {};
    }
}


QHash<int, QByteArray> ArticleListModel::roleNames() const{
    return {
        {TitleRole,       "title"},
        {SourceRole,      "source"},
        {UrlRole,         "url"},
        {PublishedAtRole, "publishedAt"},
        {SummaryRole,     "summary"},
        {TagRole,         "tag"}
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



const QList<Article>& ArticleListModel::allArticles() const {
    return m_articles;
}


std::optional<Article> ArticleListModel::articleById(int id) const {
    int row = rowForId(id);
    if (row < 0) return std::nullopt;
    return m_articles.at(row);
}


bool ArticleListModel::applyAnalysis(int articleId, const ArticleAnalysis& analysis){
    int row = rowForId(articleId);
    if (row < 0) return false;

    // Only overwrite what the analysis actually produced; keep the rest.
    Article& article = m_articles[row];
    if (!analysis.summary.isEmpty()) article.summary = analysis.summary;
    if (!analysis.biasLabel.isEmpty()) {
        article.tag = analysis.biasLabel;
        article.tag_explanation = analysis.biasExplanation;
    }
    emit dataChanged(index(row), index(row), {SummaryRole, TagRole});
    return true;
}


bool ArticleListModel::setFullText(const QString& url, const QString& text){
    bool found = false;
    for (Article& article : m_articles) {
        if (article.url == url) {
            article.full_text = text;
            found = true;
        }
    }
    return found;
}


int ArticleListModel::rowForId(int id) const {
    for (int row = 0; row < m_articles.size(); ++row) {
        if (m_articles.at(row).id == id) return row;
    }
    return -1;
}
