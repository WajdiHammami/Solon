
#pragma once

#include <QObject>
#include <QString>
#include <QUrl>

// User-adjustable request parameters, persisted between runs (QSettings).
// Limits mirror the backend's /feed validation so the server never has to
// reject a value the dialog allowed.
class ClientSettings : public QObject {
    Q_OBJECT
public:
    struct Values {
        QUrl serverUrl;
        int pageSize;   // articles per request (/feed page_size)
        int page;       // which page of results (/feed page)
    };

    static constexpr int kMinPageSize = 1;
    static constexpr int kMaxPageSize = 100;
    static constexpr int kMinPage = 1;
    static constexpr int kMaxPage = 100;

    static Values defaults();
    // Empty when valid, otherwise a message suitable for the user.
    static QString validate(const Values& values);

    explicit ClientSettings(QObject* parent = nullptr);

    const Values& values() const { return m_values; }
    QUrl serverUrl() const { return m_values.serverUrl; }
    int pageSize() const { return m_values.pageSize; }
    int page() const { return m_values.page; }

    // List ordering (ArticleSortProxy::SortKey as int); a UI preference, so
    // it lives outside Values and doesn't emit changed().
    int articleSort() const { return m_articleSort; }
    void setArticleSort(int sortKey);

    // Stores valid values and emits changed() if anything differs.
    // Returns false, changing nothing, when validate() rejects them.
    bool apply(const Values& values);

signals:
    void changed();

private:
    void load();
    void save() const;

    Values m_values;
    int m_articleSort = 0;
};
