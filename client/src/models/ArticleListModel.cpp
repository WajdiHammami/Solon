

#include "ArticleListModel.h"
#include <QBrush>
#include <QColor>


int ArticleListModel::rowCount(const QModelIndex& parent) const {
    if (parent.isValid()) return 0;
    return m_articles.size();
}


QVariant ArticleListModel::data(const QModelIndex& index, int role) const {
    if (!index.isValid() || index.row() >= m_articles.size()) return {};
    const Article& article = m_articles.at(index.row());
    const bool summarized = !article.summary.isEmpty();
    switch(role) {
        case Qt::DisplayRole:
        case TitleRole:       return article.title;
        case SourceRole:      return article.source_name;
        case UrlRole:         return article.url;
        case PublishedAtRole: return article.published_at;
        case SummaryRole:     return article.summary;
        case TagRole:         return article.tag;
        case IdRole:          return article.id;
        case SummarizedRole:  return summarized;
        case Qt::CheckStateRole:
            return m_checked.contains(article.id) ? Qt::Checked : Qt::Unchecked;
        case Qt::ForegroundRole:
            // Summarized titles stand out (Catppuccin green).
            return summarized ? QVariant(QBrush(QColor("#a6e3a1"))) : QVariant();
        case Qt::ToolTipRole: {
            QString tip = QString("%1 · %2").arg(article.source_name, article.published_at.left(10));
            if (summarized) {
                tip += "\nSummarized";
                if (!article.tag_explanation.isEmpty()) tip += "\n" + article.tag_explanation;
            }
            return tip;
        }
        default:              return {};
    }
}


bool ArticleListModel::setData(const QModelIndex& index, const QVariant& value, int role){
    if (role != Qt::CheckStateRole || !index.isValid() || index.row() >= m_articles.size()) return false;
    const int id = m_articles.at(index.row()).id;
    if (value.value<Qt::CheckState>() == Qt::Checked) m_checked.insert(id);
    else m_checked.remove(id);
    emit dataChanged(index, index, {Qt::CheckStateRole});
    emit checkedCountChanged(m_checked.size());
    return true;
}


Qt::ItemFlags ArticleListModel::flags(const QModelIndex& index) const {
    if (!index.isValid()) return Qt::NoItemFlags;
    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsUserCheckable;
}


QHash<int, QByteArray> ArticleListModel::roleNames() const{
    return {
        {TitleRole,       "title"},
        {SourceRole,      "source"},
        {UrlRole,         "url"},
        {PublishedAtRole, "publishedAt"},
        {SummaryRole,     "summary"},
        {TagRole,         "tag"},
        {IdRole,          "id"},
        {SummarizedRole,  "summarized"}
        };
}



void ArticleListModel::setArticles(const QList<Article>& articles){
    beginResetModel();
    m_articles = articles;
    m_checked.clear();   // ids are per-fetch, so old ticks don't carry over
    endResetModel();
    emit checkedCountChanged(0);
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
    emit dataChanged(index(row), index(row),
        {SummaryRole, TagRole, SummarizedRole, Qt::ForegroundRole, Qt::ToolTipRole});
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


QList<Article> ArticleListModel::checkedArticles() const {
    QList<Article> checked;
    for (const Article& article : m_articles) {
        if (m_checked.contains(article.id)) checked.append(article);
    }
    return checked;
}


void ArticleListModel::setAllChecked(bool checked){
    m_checked.clear();
    if (checked) {
        for (const Article& article : m_articles) m_checked.insert(article.id);
    }
    if (!m_articles.isEmpty()) {
        emit dataChanged(index(0), index(m_articles.size() - 1), {Qt::CheckStateRole});
    }
    emit checkedCountChanged(m_checked.size());
}


int ArticleListModel::rowForId(int id) const {
    for (int row = 0; row < m_articles.size(); ++row) {
        if (m_articles.at(row).id == id) return row;
    }
    return -1;
}
