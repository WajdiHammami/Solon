
#pragma once

#include <QDialog>
#include "app/ClientSettings.h"

class QLineEdit;
class QSpinBox;
class QLabel;

// Edits a copy of the settings; the caller applies values() on accept.
class SettingsDialog : public QDialog {
    Q_OBJECT
public:
    explicit SettingsDialog(const ClientSettings::Values& current, QWidget* parent = nullptr);
    ClientSettings::Values values() const;

public slots:
    void accept() override;

private:
    void setValues(const ClientSettings::Values& values);

    QLineEdit* m_serverUrl;
    QSpinBox* m_pageSize;
    QSpinBox* m_page;
    QLabel* m_error;
};
