
#include "Format.h"
#include <QColor>
#include <QDateTime>
#include <QLocale>
#include <QTextBlock>
#include <QTextCursor>
#include <QTextDocument>

namespace {
QDateTime parse(const QString& isoDate){
    QDateTime dt = QDateTime::fromString(isoDate, Qt::ISODate);
    return dt.isValid() ? dt.toLocalTime() : dt;
}
}  // namespace


QString Format::displayTitle(const QString& title, const QString& source){
    const QString suffix = " - " + source;
    if (!source.isEmpty() && title.endsWith(suffix, Qt::CaseInsensitive) && title.size() > suffix.size()) {
        return title.left(title.size() - suffix.size()).trimmed();
    }
    return title;
}


QString Format::relativeTime(const QString& isoDate){
    const QDateTime dt = parse(isoDate);
    if (!dt.isValid()) return {};
    const QDateTime now = QDateTime::currentDateTime();
    const qint64 seconds = dt.secsTo(now);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return QString("%1 min ago").arg(seconds / 60);
    const qint64 days = dt.date().daysTo(now.date());
    if (days == 0) return QString("%1 h ago").arg(seconds / 3600);
    if (days == 1) return "Yesterday";
    const QLocale locale;
    if (days < 7) return locale.toString(dt.date(), "ddd");
    if (dt.date().year() == now.date().year()) return locale.toString(dt.date(), "d MMM");
    return locale.toString(dt.date(), "d MMM yyyy");
}


QString Format::longDate(const QString& isoDate){
    const QDateTime dt = parse(isoDate);
    return dt.isValid() ? QLocale().toString(dt, "ddd d MMM yyyy, HH:mm") : QString();
}


void Format::polishMarkdown(QTextDocument* document){
    QTextCursor cursor(document);
    cursor.beginEditBlock();
    for (QTextBlock block = document->begin(); block.isValid(); block = block.next()) {
        QTextBlockFormat format = block.blockFormat();
        format.setLineHeight(145, QTextBlockFormat::ProportionalHeight);
        const int level = format.headingLevel();
        if (level > 0) {
            format.setTopMargin(block == document->begin() ? 0 : 14);
            format.setBottomMargin(6);
            QTextCharFormat heading;
            heading.setForeground(QColor(level <= 2 ? "#89b4fa" : "#b4befe"));
            QFont font = document->defaultFont();
            font.setPixelSize(level <= 2 ? 16 : 15);
            font.setBold(true);
            heading.setFont(font);
            // Markdown import sizes headings relatively; drop that so ours applies.
            heading.setProperty(QTextFormat::FontSizeAdjustment, 0);
            cursor.setPosition(block.position());
            cursor.setPosition(block.position() + block.length() - 1, QTextCursor::KeepAnchor);
            cursor.mergeCharFormat(heading);
        } else {
            format.setBottomMargin(block.textList() ? 3 : 8);
        }
        cursor.setPosition(block.position());
        cursor.setBlockFormat(format);
    }
    cursor.endEditBlock();
}
