

#include "SynthesisView.h"
#include <QLabel>
#include <QTextEdit>
#include <QVBoxLayout>
#include "ui/Format.h"

SynthesisView::SynthesisView(QWidget* parent): QWidget(parent) {

    m_header = new QLabel("SYNTHESIS", this);
    m_header->setObjectName("synthesisHeader");

    m_notices = new QLabel(this);
    m_notices->setObjectName("synthesisNotice");
    m_notices->setWordWrap(true);
    m_notices->hide();

    m_synthesis = new QTextEdit(this);
    m_synthesis->setReadOnly(true);
    m_synthesis->setPlaceholderText("Tick articles and run 'Summarize Selected' to generate a synthesis...");
    m_synthesis->setObjectName("synthesisText");
    m_synthesis->document()->setDocumentMargin(14);

    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(4, 10, 4, 4);
    layout->setSpacing(8);
    layout->addWidget(m_header);
    layout->addWidget(m_notices);
    layout->addWidget(m_synthesis);
    setLayout(layout);

    hide();
}

void SynthesisView::setSynthesis(const QString& synthesis) {
    m_synthesis->setMarkdown(synthesis);
    Format::polishMarkdown(m_synthesis->document());
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
