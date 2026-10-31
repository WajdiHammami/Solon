
#pragma once

#include <QColor>
#include <QStyledItemDelegate>

// Paints an article row as usual (checkbox, title) plus, for summarized
// articles, a colored bias badge at the right end of the row.
class ArticleItemDelegate : public QStyledItemDelegate {
    Q_OBJECT
public:
    using QStyledItemDelegate::QStyledItemDelegate;

    void paint(QPainter* painter, const QStyleOptionViewItem& option, const QModelIndex& index) const override;

    // Text shown in the badge for a bias label ("None" reads "No bias").
    static QString badgeText(const QString& biasLabel);
    // Green for no bias; otherwise a stable color per label, so the same
    // label always looks the same and different labels are easy to tell apart.
    static QColor badgeColor(const QString& biasLabel);
};
