
#include "SettingsDialog.h"
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QVBoxLayout>

SettingsDialog::SettingsDialog(const ClientSettings::Values& current, QWidget* parent)
    : QDialog(parent),
      m_serverUrl(new QLineEdit(this)),
      m_pageSize(new QSpinBox(this)),
      m_page(new QSpinBox(this)),
      m_error(new QLabel(this)) {

    setWindowTitle("Settings");
    setMinimumWidth(420);

    QLabel* header = new QLabel("Request settings", this);
    header->setObjectName("settingsHeader");

    m_serverUrl->setPlaceholderText("http://localhost:8000");
    m_pageSize->setRange(ClientSettings::kMinPageSize, ClientSettings::kMaxPageSize);
    m_page->setRange(ClientSettings::kMinPage, ClientSettings::kMaxPage);

    QLabel* hint = new QLabel(
        "NewsAPI's free plan returns at most 100 results per search "
        "(page × articles per page ≤ 100).", this);
    hint->setObjectName("settingsHint");
    hint->setWordWrap(true);

    m_error->setObjectName("settingsError");
    m_error->setWordWrap(true);
    m_error->hide();

    QFormLayout* form = new QFormLayout();
    form->setSpacing(10);
    form->addRow("Server URL", m_serverUrl);
    form->addRow("Articles per page", m_pageSize);
    form->addRow("Page", m_page);

    QDialogButtonBox* buttons = new QDialogButtonBox(
        QDialogButtonBox::Save | QDialogButtonBox::Cancel | QDialogButtonBox::RestoreDefaults, this);
    connect(buttons, &QDialogButtonBox::accepted, this, &SettingsDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &SettingsDialog::reject);
    connect(buttons->button(QDialogButtonBox::RestoreDefaults), &QPushButton::clicked, this, [this](){
        setValues(ClientSettings::defaults());
    });

    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(20, 16, 20, 16);
    layout->setSpacing(10);
    layout->addWidget(header);
    layout->addLayout(form);
    layout->addWidget(hint);
    layout->addWidget(m_error);
    layout->addStretch();
    layout->addWidget(buttons);

    setValues(current);
}


ClientSettings::Values SettingsDialog::values() const {
    return {QUrl(m_serverUrl->text().trimmed()), m_pageSize->value(), m_page->value()};
}


void SettingsDialog::accept(){
    // Keep the dialog open on invalid input instead of silently discarding it.
    const QString error = ClientSettings::validate(values());
    if (!error.isEmpty()) {
        m_error->setText(error);
        m_error->show();
        return;
    }
    QDialog::accept();
}


void SettingsDialog::setValues(const ClientSettings::Values& values){
    m_serverUrl->setText(values.serverUrl.toString());
    m_pageSize->setValue(values.pageSize);
    m_page->setValue(values.page);
    m_error->hide();
}
