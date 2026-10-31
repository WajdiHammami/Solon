
#pragma once

#include <QString>

class QTextDocument;

// Display helpers shared by the list, detail view and reader.
namespace Format {

// NewsAPI titles often end with " - <Source>"; drop it when the source is shown anyway.
QString displayTitle(const QString& title, const QString& source);

// "just now", "5 min ago", "3 h ago", "Yesterday", "Mon", "29 Oct", "29 Oct 2024".
QString relativeTime(const QString& isoDate);

// "Wed 29 Oct 2026, 17:15" in local time (empty when unparseable).
QString longDate(const QString& isoDate);

// Readable typography for Markdown rendered into a QTextDocument: modest
// heading sizes, comfortable line height and paragraph spacing.
void polishMarkdown(QTextDocument* document);

}  // namespace Format
