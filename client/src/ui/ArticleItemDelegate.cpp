
#include "ArticleItemDelegate.h"
#include <QApplication>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include "models/ArticleListModel.h"
#include "ui/Format.h"

namespace {
constexpr int kRowHeight = 62;
constexpr int kRowGap = 4;          // vertical space between cards
constexpr int kSidePadding = 14;
constexpr int kCheckboxSize = 16;
constexpr int kBadgeHeight = 20;
constexpr int kBadgePadding = 8;
constexpr int kMaxBadgeWidth = 150;

const QColor kText("#cdd6f4");
const QColor kMuted("#7f849c");
const QColor kGreen("#a6e3a1");
const QColor kHover("#262637");
const QColor kSelected("#313244");
const QColor kCheckBorder("#6c7086");
const QColor kAccent("#89b4fa");
const QColor kCardBase("#1e1e2e");

QFont withPixelSize(QFont font, int px, bool bold = false){
    font.setPixelSize(px);
    font.setBold(bold);
    return font;
}
}  // namespace


QString ArticleItemDelegate::badgeText(const QString& biasLabel){
    return biasLabel.compare("None", Qt::CaseInsensitive) == 0 ? QString("No bias") : biasLabel;
}


QColor ArticleItemDelegate::badgeColor(const QString& biasLabel){
    if (biasLabel.compare("None", Qt::CaseInsensitive) == 0) return kGreen;
    // Catppuccin accents, skipping green (reserved for "no bias").
    static const QColor palette[] = {
        QColor("#f38ba8"), QColor("#fab387"), QColor("#f9e2af"),
        QColor("#cba6f7"), QColor("#f5c2e7"), QColor("#94e2d5"), QColor("#89dceb"),
    };
    const size_t n = sizeof(palette) / sizeof(palette[0]);
    return palette[qHash(biasLabel.toLower()) % n];
}


QSize ArticleItemDelegate::sizeHint(const QStyleOptionViewItem& option, const QModelIndex&) const {
    return QSize(option.rect.width(), kRowHeight + kRowGap);
}


QRect ArticleItemDelegate::checkboxRect(const QRect& row){
    const QRect card = row.adjusted(0, 0, 0, -kRowGap);
    return QRect(card.left() + kSidePadding, card.center().y() - kCheckboxSize / 2,
                 kCheckboxSize, kCheckboxSize);
}


void ArticleItemDelegate::paint(QPainter* painter, const QStyleOptionViewItem& option, const QModelIndex& index) const {
    const QString title = Format::displayTitle(index.data(ArticleListModel::TitleRole).toString(),
                                               index.data(ArticleListModel::SourceRole).toString());
    const QString source = index.data(ArticleListModel::SourceRole).toString();
    const QString when = Format::relativeTime(index.data(ArticleListModel::PublishedAtRole).toString());
    const QString bias = index.data(ArticleListModel::TagRole).toString();
    const bool summarized = index.data(ArticleListModel::SummarizedRole).toBool();
    const bool checked = index.data(Qt::CheckStateRole).value<Qt::CheckState>() == Qt::Checked;
    const bool selected = option.state & QStyle::State_Selected;
    const bool hovered = option.state & QStyle::State_MouseOver;

    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);

    // Card background.
    const QRectF card = QRectF(option.rect.adjusted(2, 0, -2, -kRowGap));
    QPainterPath cardPath;
    cardPath.addRoundedRect(card, 8, 8);
    painter->fillPath(cardPath, selected ? kSelected : hovered ? kHover : kCardBase);

    // Green accent bar for summarized articles.
    if (summarized) {
        QPainterPath bar;
        bar.addRoundedRect(QRectF(card.left() + 3, card.top() + 10, 3, card.height() - 20), 1.5, 1.5);
        painter->fillPath(bar, kGreen);
    }

    // Checkbox.
    const QRectF box = QRectF(checkboxRect(option.rect)).adjusted(0.5, 0.5, -0.5, -0.5);
    QPainterPath boxPath;
    boxPath.addRoundedRect(box, 4, 4);
    if (checked) {
        painter->fillPath(boxPath, kAccent);
        QPen tick(kCardBase, 2, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
        painter->setPen(tick);
        painter->drawPolyline(QPolygonF({
            QPointF(box.left() + 3.5, box.center().y() + 0.5),
            QPointF(box.left() + 6.5, box.bottom() - 4),
            QPointF(box.right() - 3.5, box.top() + 4.5)}));
    } else {
        painter->setPen(QPen(kCheckBorder, 1.2));
        painter->drawPath(boxPath);
    }

    // Bias badge (right end), measured first so the text can stop before it.
    int textRight = int(card.right()) - kSidePadding;
    if (summarized && !bias.isEmpty()) {
        const QFont badgeFont = withPixelSize(option.font, 11, true);
        const QFontMetrics metrics(badgeFont);
        const QString label = metrics.elidedText(badgeText(bias), Qt::ElideRight, kMaxBadgeWidth - 2 * kBadgePadding);
        const int badgeWidth = metrics.horizontalAdvance(label) + 2 * kBadgePadding;
        const QRectF badge(card.right() - kSidePadding - badgeWidth,
                           card.center().y() - kBadgeHeight / 2.0, badgeWidth, kBadgeHeight);
        const QColor color = badgeColor(bias);
        QColor fill = color;
        fill.setAlpha(38);
        QPainterPath badgePath;
        badgePath.addRoundedRect(badge, kBadgeHeight / 2.0, kBadgeHeight / 2.0);
        painter->fillPath(badgePath, fill);
        painter->setPen(QPen(color, 1));
        painter->drawPath(badgePath);
        painter->setFont(badgeFont);
        painter->drawText(badge, Qt::AlignCenter, label);
        textRight = int(badge.left()) - 12;
    }

    // Title and meta line.
    const int textLeft = int(box.right()) + 12;
    const int textWidth = qMax(0, textRight - textLeft);
    const QFont titleFont = withPixelSize(option.font, 14, true);
    const QFont metaFont = withPixelSize(option.font, 12);
    const QFontMetrics titleMetrics(titleFont);
    const QFontMetrics metaMetrics(metaFont);
    const int blockHeight = titleMetrics.height() + 4 + metaMetrics.height();
    const int top = int(card.center().y()) - blockHeight / 2;

    painter->setFont(titleFont);
    painter->setPen(kText);
    painter->drawText(QRect(textLeft, top, textWidth, titleMetrics.height()), Qt::AlignLeft | Qt::AlignVCenter,
                      titleMetrics.elidedText(title, Qt::ElideRight, textWidth));

    QStringList metaParts;
    if (!source.isEmpty()) metaParts << source;
    if (!when.isEmpty()) metaParts << when;
    QString meta = metaParts.join("  ·  ");
    const QRect metaRect(textLeft, top + titleMetrics.height() + 4, textWidth, metaMetrics.height());
    painter->setFont(metaFont);
    painter->setPen(kMuted);
    const QString elidedMeta = metaMetrics.elidedText(meta, Qt::ElideRight, textWidth);
    painter->drawText(metaRect, Qt::AlignLeft | Qt::AlignVCenter, elidedMeta);
    if (summarized) {
        const int metaWidth = metaMetrics.horizontalAdvance(elidedMeta);
        const QString marker = QStringLiteral("  ·  ✓ Summarized");
        if (metaWidth + metaMetrics.horizontalAdvance(marker) <= textWidth) {
            painter->setPen(kGreen);
            painter->drawText(metaRect.adjusted(metaWidth, 0, 0, 0), Qt::AlignLeft | Qt::AlignVCenter, marker);
        }
    }

    painter->restore();
}


bool ArticleItemDelegate::editorEvent(QEvent* event, QAbstractItemModel* model,
                                      const QStyleOptionViewItem& option, const QModelIndex& index){
    if (event->type() != QEvent::MouseButtonRelease) return false;
    auto* mouse = static_cast<QMouseEvent*>(event);
    // A little slack around the box makes it easier to hit.
    if (mouse->button() != Qt::LeftButton
        || !checkboxRect(option.rect).adjusted(-6, -6, 6, 6).contains(mouse->position().toPoint())) {
        return false;
    }
    const bool checked = index.data(Qt::CheckStateRole).value<Qt::CheckState>() == Qt::Checked;
    return model->setData(index, checked ? Qt::Unchecked : Qt::Checked, Qt::CheckStateRole);
}
