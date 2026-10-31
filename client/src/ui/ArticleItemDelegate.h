
#pragma once

#include <QColor>
#include <QStyledItemDelegate>

// Paints an article as a two-line card: checkbox, title, then
// "source · 3 h ago"; summarized articles get a green accent bar, a
// "✓ Summarized" marker and a colored bias badge at the right end.
class ArticleItemDelegate : public QStyledItemDelegate {
    Q_OBJECT
public:
    using QStyledItemDelegate::QStyledItemDelegate;

    void paint(QPainter* painter, const QStyleOptionViewItem& option, const QModelIndex& index) const override;
    QSize sizeHint(const QStyleOptionViewItem& option, const QModelIndex& index) const override;

    // Text shown in the badge for a bias label ("None" reads "No bias").
    static QString badgeText(const QString& biasLabel);
    // Green for no bias; otherwise a stable color per label, so the same
    // label always looks the same and different labels are easy to tell apart.
    static QColor badgeColor(const QString& biasLabel);

protected:
    // The checkbox is drawn at a custom position, so toggling is hit-tested here.
    bool editorEvent(QEvent* event, QAbstractItemModel* model,
                     const QStyleOptionViewItem& option, const QModelIndex& index) override;

private:
    static QRect checkboxRect(const QRect& row);
};
