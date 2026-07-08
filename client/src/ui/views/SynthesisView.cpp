

#include "SynthesisView.h"
#include <QLabel>
#include <QTextEdit>
#include <QVBoxLayout>

SynthesisView::SynthesisView(QWidget* parent): QWidget(parent) {

    m_header = new QLabel("Synthesis Overview", this);
    m_header->setObjectName("synthesisHeader");

    m_synthesis = new QTextEdit(this);
    m_synthesis->setReadOnly(true);
    m_synthesis->setPlaceholderText("Run 'Summarize All' to generate a synthesis...");
    m_synthesis->setObjectName("synthesisText");

    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(12, 8, 12, 8);
    layout->setSpacing(6);
    layout->addWidget(m_header);
    layout->addWidget(m_synthesis);
    setLayout(layout);

    hide();
}

void SynthesisView::setSynthesis(const QString& synthesis) {
    m_synthesis->setText(synthesis);
    show();
}