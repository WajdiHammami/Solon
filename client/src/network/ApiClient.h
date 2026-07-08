
#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QUrl>
#include <QJsonObject>
#include <QList>
#include "models/Article.h"
#include <QMap>
#include <QPair>


class ApiClient: public QObject {
    Q_OBJECT
public:
    explicit ApiClient(QObject* parent=nullptr);
    void fetchFeed(const QString& topic, int pageSize, int page);
    void summarizeRequest(const QList<Article>& articles);
    void contentRequest(const QString& url);
signals:
    void summarizationOneArticleReceived(const Article& article);
    void summarizationMultiArticleReceived(const QList<QString>& summaries, const QString& synthesis, const QMap<int, QPair<QString, QString>>& tags);
    void feedReceived(const QList<Article>& articles);
    void errorOccurred(const QString& message);
    void contentReceived(const QString& content);
private:
    Article parseArticle(const QJsonObject& articles);
    QNetworkAccessManager* m_network;
    QUrl m_baseUrl;

};