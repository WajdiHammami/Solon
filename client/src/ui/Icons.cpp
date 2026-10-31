
#include "Icons.h"
#include <QPainter>
#include <QPainterPath>
#include <QPixmap>
#include <QtMath>

namespace {

// A gear: toothed outer ring with a hole, drawn on a 24x24 grid.
QPixmap gearPixmap(int size, const QColor& color){
    QPixmap pixmap(size, size);
    pixmap.fill(Qt::transparent);

    QPainter painter(&pixmap);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.scale(size / 24.0, size / 24.0);
    painter.translate(12, 12);

    constexpr int kTeeth = 8;
    constexpr double kOuter = 10.5, kInner = 8.0, kHole = 3.5;
    QPainterPath gear;
    for (int i = 0; i < kTeeth * 2; ++i) {
        // Alternate tooth / gap, each spanning half a tooth period.
        const double radius = (i % 2 == 0) ? kOuter : kInner;
        const double start = qDegreesToRadians(360.0 / (kTeeth * 2) * i - 360.0 / (kTeeth * 4));
        const double end = qDegreesToRadians(360.0 / (kTeeth * 2) * (i + 1) - 360.0 / (kTeeth * 4));
        const QPointF a(radius * qCos(start), radius * qSin(start));
        const QPointF b(radius * qCos(end), radius * qSin(end));
        if (i == 0) gear.moveTo(a); else gear.lineTo(a);
        gear.lineTo(b);
    }
    gear.closeSubpath();
    gear.addEllipse(QPointF(0, 0), kHole, kHole);
    gear.setFillRule(Qt::OddEvenFill);

    painter.fillPath(gear, color);
    return pixmap;
}

}  // namespace


QIcon Icons::settings(const QColor& color){
    QIcon icon;
    for (int size : {16, 24, 32, 48, 64}) {
        icon.addPixmap(gearPixmap(size, color));
    }
    return icon;
}
