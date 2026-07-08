

#pragma once


#include <QWidget>

class QTextEdit;
class QLabel;

class SynthesisView : public QWidget{
    Q_OBJECT
public:
    SynthesisView(QWidget* parent = nullptr);
    void setSynthesis(const QString& synthesis);

private:
    QLabel* m_header;
    QTextEdit* m_synthesis;
};