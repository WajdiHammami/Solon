
#include "ArticleSortProxy.h"
#include <QDateTime>
#include "ArticleListModel.h"

namespace {

QDateTime publishedAt(const QModelIndex& index){
    return QDateTime::fromString(index.data(ArticleListModel::PublishedAtRole).toString(), Qt::ISODate);
}

int compareText(const QModelIndex& a, const QModelIndex& b, int role){
    return QString::localeAwareCompare(a.data(role).toString(), b.data(role).toString());
}

}  // namespace


ArticleSortProxy::ArticleSortProxy(QObject* parent): QSortFilterProxyModel(parent){
    // Re-sort when an article changes (e.g. becomes summarized).
    setDynamicSortFilter(true);
    sort(0);
}


QStringList ArticleSortProxy::labels(){
    return {"Feed order", "Title (A–Z)", "Title (Z–A)", "Newest first", "Oldest first", "Source", "Summarized first"};
}


void ArticleSortProxy::setSortKey(SortKey key){
    m_key = key;
    invalidate();
    sort(0);
}


bool ArticleSortProxy::lessThan(const QModelIndex& left, const QModelIndex& right) const {
    // Every key falls back to feed order so ties keep a stable, predictable order.
    const int leftId = left.data(ArticleListModel::IdRole).toInt();
    const int rightId = right.data(ArticleListModel::IdRole).toInt();
    int cmp = 0;

    switch (m_key) {
        case SortKey::FeedOrder:
            break;
        case SortKey::TitleAsc:
            cmp = compareText(left, right, ArticleListModel::TitleRole);
            break;
        case SortKey::TitleDesc:
            cmp = -compareText(left, right, ArticleListModel::TitleRole);
            break;
        case SortKey::NewestFirst:
        case SortKey::OldestFirst: {
            const QDateTime a = publishedAt(left), b = publishedAt(right);
            if (a != b) cmp = a < b ? -1 : 1;
            if (m_key == SortKey::NewestFirst) cmp = -cmp;
            break;
        }
        case SortKey::Source:
            cmp = compareText(left, right, ArticleListModel::SourceRole);
            break;
        case SortKey::SummarizedFirst: {
            const bool a = left.data(ArticleListModel::SummarizedRole).toBool();
            const bool b = right.data(ArticleListModel::SummarizedRole).toBool();
            if (a != b) cmp = a ? -1 : 1;
            break;
        }
    }
    return cmp != 0 ? cmp < 0 : leftId < rightId;
}
