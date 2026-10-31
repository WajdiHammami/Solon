
#include "ClientSettings.h"
#include <QSettings>

namespace {
const char* kServerUrlKey = "server/url";
const char* kPageSizeKey = "feed/pageSize";
const char* kPageKey = "feed/page";
const char* kArticleSortKey = "ui/articleSort";
}


ClientSettings::Values ClientSettings::defaults(){
    return {QUrl("http://localhost:8000"), 5, 1};  // page size matches the backend's /feed default
}


QString ClientSettings::validate(const Values& values){
    const QUrl& url = values.serverUrl;
    if (!url.isValid() || (url.scheme() != "http" && url.scheme() != "https") || url.host().isEmpty()) {
        return "Server URL must look like http://host:port";
    }
    if (!url.path().isEmpty() && url.path() != "/") {
        return "Server URL must not contain a path";
    }
    if (values.pageSize < kMinPageSize || values.pageSize > kMaxPageSize) {
        return QString("Articles per page must be between %1 and %2").arg(kMinPageSize).arg(kMaxPageSize);
    }
    if (values.page < kMinPage || values.page > kMaxPage) {
        return QString("Page must be between %1 and %2").arg(kMinPage).arg(kMaxPage);
    }
    return {};
}


ClientSettings::ClientSettings(QObject* parent): QObject(parent), m_values(defaults()){
    load();
}


bool ClientSettings::apply(const Values& values){
    if (!validate(values).isEmpty()) return false;
    Values normalized = values;
    normalized.serverUrl.setPath({});  // "http://host/" -> "http://host"
    if (normalized.serverUrl == m_values.serverUrl
        && normalized.pageSize == m_values.pageSize
        && normalized.page == m_values.page) {
        return true;
    }
    m_values = normalized;
    save();
    emit changed();
    return true;
}


void ClientSettings::load(){
    QSettings store;
    const Values fallback = defaults();
    Values loaded{
        QUrl(store.value(kServerUrlKey, fallback.serverUrl.toString()).toString()),
        store.value(kPageSizeKey, fallback.pageSize).toInt(),
        store.value(kPageKey, fallback.page).toInt(),
    };
    // A hand-edited or outdated config file must not break requests.
    m_values = validate(loaded).isEmpty() ? loaded : fallback;
    m_values.serverUrl.setPath({});
    m_articleSort = store.value(kArticleSortKey, 0).toInt();
}


void ClientSettings::setArticleSort(int sortKey){
    m_articleSort = sortKey;
    QSettings().setValue(kArticleSortKey, sortKey);
}


void ClientSettings::save() const {
    QSettings store;
    store.setValue(kServerUrlKey, m_values.serverUrl.toString());
    store.setValue(kPageSizeKey, m_values.pageSize);
    store.setValue(kPageKey, m_values.page);
}
