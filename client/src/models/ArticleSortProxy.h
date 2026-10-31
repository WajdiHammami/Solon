
#pragma once

#include <QSortFilterProxyModel>
#include <QStringList>

// Orders the article list for display. Sorting never touches the source
// model, so ids, checkboxes and analysis stay attached to their articles.
class ArticleSortProxy : public QSortFilterProxyModel {
    Q_OBJECT
public:
    enum class SortKey {
        FeedOrder,
        TitleAsc,
        TitleDesc,
        NewestFirst,
        OldestFirst,
        Source,
        SummarizedFirst,
    };

    explicit ArticleSortProxy(QObject* parent = nullptr);

    // Labels in SortKey order, for a combo box.
    static QStringList labels();

    SortKey sortKey() const { return m_key; }
    void setSortKey(SortKey key);

protected:
    bool lessThan(const QModelIndex& left, const QModelIndex& right) const override;

private:
    SortKey m_key = SortKey::FeedOrder;
};
