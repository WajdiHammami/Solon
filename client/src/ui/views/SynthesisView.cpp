

#include "SynthesisView.h"
#include <QLabel>
#include <QTextEdit>
#include <QVBoxLayout>

SynthesisView::SynthesisView(QWidget* parent): QWidget(parent) {

    m_header = new QLabel("Synthesis Overview", this);
    m_header->setObjectName("synthesisHeader");

    m_notices = new QLabel(this);
    m_notices->setObjectName("synthesisNotice");
    m_notices->setWordWrap(true);
    m_notices->hide();

    m_synthesis = new QTextEdit(this);
    m_synthesis->setReadOnly(true);
    m_synthesis->setPlaceholderText("Tick articles and run 'Summarize Selected' to generate a synthesis...");
    m_synthesis->setObjectName("synthesisText");

    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(12, 8, 12, 8);
    layout->setSpacing(6);
    layout->addWidget(m_header);
    layout->addWidget(m_notices);
    layout->addWidget(m_synthesis);
    setLayout(layout);

    hide();
}

void SynthesisView::setSynthesis(const QString& synthesis) {
    m_synthesis->setMarkdown(synthesis);
    show();
}

void SynthesisView::setNotices(const QStringList& notices) {
    m_notices->setText(notices.join("\n"));
    m_notices->setVisible(!notices.isEmpty());
}

void SynthesisView::clear() {
    m_synthesis->clear();
    setNotices({});
    hide();
}
