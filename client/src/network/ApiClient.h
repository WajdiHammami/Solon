
#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QUrl>
#include <QJsonObject>
#include <QList>
#include <functional>
#include "models/Article.h"
#include "models/Analysis.h"

class QNetworkReply;

class ApiClient: public QObject {
    Q_OBJECT
public:
    enum class Request { Feed, Analyze, AnalyzeArticle, Content };

    explicit ApiClient(QObject* parent=nullptr);
    void setBaseUrl(const QUrl& baseUrl);
    void fetchFeed(const QString& topic, int pageSize, int page);
    void analyzeArticles(const QList<Article>& articles);
    void analyzeArticle(const Article& article);
    void contentRequest(const QString& url);
signals:
    void feedReceived(const QList<Article>& articles);
    void batchAnalysisReceived(const BatchAnalysis& batch);
    void articleAnalysisReceived(int articleId, const ArticleAnalysis& analysis, const QList<TaskFailure>& failures);
    void contentReceived(const QString& url, const QString& content);
    // Emitted for every failed request (network, HTTP or malformed response).
    void errorOccurred(ApiClient::Request request, const QString& message);
private:
    QNetworkReply* postJson(const QString& path, const QJsonObject& body, int timeoutMs);
    // Calls onSuccess with the body, or emits errorOccurred; always frees the reply.
    void handleReply(QNetworkReply* reply, Request request, std::function<void(const QByteArray&)> onSuccess);
    bool parseJson(Request request, const QByteArray& body, QJsonDocument& doc);

    static QJsonObject toJson(const Article& article);
    static Article parseArticle(const QJsonObject& object);
    static ArticleAnalysis parseAnalysis(const QJsonObject& object);
    static TaskFailure parseFailure(const QJsonObject& object);
    static QString errorMessage(QNetworkReply* reply, const QByteArray& body);

    QNetworkAccessManager* m_network;
    QUrl m_baseUrl;

};
