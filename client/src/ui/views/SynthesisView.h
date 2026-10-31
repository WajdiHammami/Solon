

#pragma once


#include <QWidget>
#include <QStringList>

class QTextEdit;
class QLabel;

class SynthesisView : public QWidget{
    Q_OBJECT
public:
    SynthesisView(QWidget* parent = nullptr);
    void setSynthesis(const QString& synthesis);
    // Lines shown above the synthesis (failed / skipped articles); empty hides it.
    void setNotices(const QStringList& notices);
    void clear();

private:
    QLabel* m_header;
    QLabel* m_notices;
    QTextEdit* m_synthesis;
};
