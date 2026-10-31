
#include "ArticleItemDelegate.h"
#include <QApplication>
#include <QPainter>
#include <QPainterPath>
#include "models/ArticleListModel.h"

namespace {
constexpr int kBadgeHeight = 18;
constexpr int kBadgePadding = 7;    // horizontal, inside the badge
constexpr int kBadgeMargin = 10;    // between badge and row edge / title
constexpr int kMaxBadgeWidth = 140;

QFont badgeFont(const QFont& base){
    QFont font = base;
    // The stylesheet sizes fonts in px, which leaves pointSize at -1.
    if (base.pixelSize() > 0) font.setPixelSize(qMax(9, qRound(base.pixelSize() * 0.8)));
    else font.setPointSizeF(qMax(7.0, base.pointSizeF() * 0.8));
    font.setBold(true);
    return font;
}
}  // namespace


QString ArticleItemDelegate::badgeText(const QString& biasLabel){
    return biasLabel.compare("None", Qt::CaseInsensitive) == 0 ? QString("No bias") : biasLabel;
}


QColor ArticleItemDelegate::badgeColor(const QString& biasLabel){
    if (biasLabel.compare("None", Qt::CaseInsensitive) == 0) return QColor("#a6e3a1");  // green
    // Catppuccin accents, skipping green (reserved for "no bias").
    static const QColor palette[] = {
        QColor("#f38ba8"), QColor("#fab387"), QColor("#f9e2af"),
        QColor("#cba6f7"), QColor("#f5c2e7"), QColor("#94e2d5"), QColor("#89dceb"),
    };
    const size_t n = sizeof(palette) / sizeof(palette[0]);
    return palette[qHash(biasLabel.toLower()) % n];
}


void ArticleItemDelegate::paint(QPainter* painter, const QStyleOptionViewItem& option, const QModelIndex& index) const {
    const QString bias = index.data(ArticleListModel::TagRole).toString();
    const bool summarized = index.data(ArticleListModel::SummarizedRole).toBool();
    if (!summarized || bias.isEmpty()) {
        QStyledItemDelegate::paint(painter, option, index);
        return;
    }

    const QFont font = badgeFont(option.font);
    const QFontMetrics metrics(font);
    const QString text = metrics.elidedText(badgeText(bias), Qt::ElideRight, kMaxBadgeWidth - 2 * kBadgePadding);
    const int badgeWidth = metrics.horizontalAdvance(text) + 2 * kBadgePadding;

    // Row background across the full width, then the standard content in the
    // space left of the badge so long titles elide instead of running under it.
    QStyleOptionViewItem opt = option;
    initStyleOption(&opt, index);
    QStyle* style = opt.widget ? opt.widget->style() : QApplication::style();
    style->drawPrimitive(QStyle::PE_PanelItemViewItem, &opt, painter, opt.widget);
    opt.rect.setRight(opt.rect.right() - badgeWidth - 2 * kBadgeMargin);
    style->drawControl(QStyle::CE_ItemViewItem, &opt, painter, opt.widget);

    const QRectF badge(option.rect.right() - kBadgeMargin - badgeWidth,
                       option.rect.center().y() - kBadgeHeight / 2.0 + 0.5,
                       badgeWidth, kBadgeHeight);
    const QColor color = badgeColor(bias);
    QColor fill = color;
    fill.setAlpha(45);

    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);
    QPainterPath path;
    path.addRoundedRect(badge, 4, 4);
    painter->fillPath(path, fill);
    painter->setPen(QPen(color, 1));
    painter->drawPath(path);
    painter->setFont(font);
    painter->setPen(color);
    painter->drawText(badge, Qt::AlignCenter, text);
    painter->restore();
}
