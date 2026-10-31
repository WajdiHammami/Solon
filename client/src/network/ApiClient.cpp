
#include "ApiClient.h"
#include <QUrl>
#include <QUrlQuery>
#include <QDebug>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonArray>
#include <QNetworkRequest>
#include <QUuid>

namespace {
// Analysis makes several LLM calls per article; give it room.
constexpr int kFeedTimeoutMs = 30'000;
constexpr int kAnalyzeTimeoutMs = 180'000;
constexpr int kContentTimeoutMs = 60'000;
const QByteArray kRequestIdHeader = "X-Request-ID";

// Every request carries an id the backend stamps on its log lines, so an
// error shown here can be found in backend/logs/solon.log.
QNetworkRequest makeRequest(const QUrl& url, int timeoutMs){
    QNetworkRequest request(url);
    request.setTransferTimeout(timeoutMs);
    request.setRawHeader(kRequestIdHeader, QUuid::createUuid().toString(QUuid::Id128).left(12).toLatin1());
    return request;
}
}

ApiClient::ApiClient(QObject* parent): QObject(parent), m_network(new QNetworkAccessManager(this)), m_baseUrl("http://localhost:8000"){}

void ApiClient::setBaseUrl(const QUrl& baseUrl){
    m_baseUrl = baseUrl;
}

void ApiClient::fetchFeed(const QString& topic, int pageSize, int page){
    QUrl url(m_baseUrl);
    QUrlQuery query;

    url.setPath("/feed");
    // No topic means top headlines (the backend treats missing/blank alike).
    if(!topic.trimmed().isEmpty()) query.addQueryItem("topic", topic.trimmed());
    query.addQueryItem("page", QString::number(page));
    query.addQueryItem("page_size", QString::number(pageSize));
    url.setQuery(query);

    handleReply(m_network->get(makeRequest(url, kFeedTimeoutMs)), Request::Feed, [this](const QByteArray& body){
        QJsonDocument doc;
        if(!parseJson(Request::Feed, body, doc)) return;
        if(!doc.isArray()){
            emit errorOccurred(Request::Feed, "Unexpected feed format: expected a JSON array");
            return;
        }
        QList<Article> articles;
        for(const QJsonValue& val: doc.array()){
            articles.append(parseArticle(val.toObject()));
        }
        emit feedReceived(articles);
    });
}


void ApiClient::analyzeArticles(const QList<Article>& articles){
    QJsonArray jsonArray;
    for(const auto& article: articles){
        jsonArray.append(toJson(article));
    }
    QJsonObject requestBody;
    requestBody["articles"] = jsonArray;

    handleReply(postJson("/analyze", requestBody, kAnalyzeTimeoutMs), Request::Analyze, [this](const QByteArray& body){
        QJsonDocument doc;
        if(!parseJson(Request::Analyze, body, doc)) return;
        QJsonObject obj = doc.object();
        if(!obj["analyses"].isObject()){
            emit errorOccurred(Request::Analyze, "Unexpected response from server (no analyses)");
            return;
        }

        BatchAnalysis batch;
        QJsonObject analyses = obj["analyses"].toObject();
        for(auto it = analyses.begin(); it != analyses.end(); ++it){
            batch.analyses[it.key().toInt()] = parseAnalysis(it.value().toObject());
        }
        batch.synthesis = obj["synthesis"].toString();
        for(const QJsonValue& id: obj["sources"].toArray()) batch.sources.append(id.toInt());
        for(const QJsonValue& id: obj["skipped"].toArray()) batch.skipped.append(id.toInt());
        for(const QJsonValue& f: obj["failed"].toArray()) batch.failed.append(parseFailure(f.toObject()));
        batch.estimatedTokens = obj["estimated_tokens"].toInt();
        emit batchAnalysisReceived(batch);
    });
}


void ApiClient::analyzeArticle(const Article& article){
    const int articleId = article.id;
    handleReply(postJson("/analyze/article", toJson(article), kAnalyzeTimeoutMs), Request::AnalyzeArticle, [this, articleId](const QByteArray& body){
        QJsonDocument doc;
        if(!parseJson(Request::AnalyzeArticle, body, doc)) return;
        QJsonObject obj = doc.object();
        if(!obj["analysis"].isObject()){
            emit errorOccurred(Request::AnalyzeArticle, "Unexpected response from server (no analysis)");
            return;
        }

        QList<TaskFailure> failures;
        for(const QJsonValue& f: obj["failures"].toArray()) failures.append(parseFailure(f.toObject()));
        emit articleAnalysisReceived(articleId, parseAnalysis(obj["analysis"].toObject()), failures);
    });
}


void ApiClient::contentRequest(const QString& url){
    QUrl requestUrl(m_baseUrl);
    QUrlQuery query;
    requestUrl.setPath("/article/content");
    query.addQueryItem("url", url);
    requestUrl.setQuery(query);

    handleReply(m_network->get(makeRequest(requestUrl, kContentTimeoutMs)), Request::Content, [this, url](const QByteArray& body){
        // The endpoint returns a bare JSON string; wrap it so QJsonDocument can parse it.
        QJsonDocument doc;
        if(!parseJson(Request::Content, QByteArray("[") + body + QByteArray("]"), doc)) return;
        emit contentReceived(url, doc.array().first().toString());
    });
}


QNetworkReply* ApiClient::postJson(const QString& path, const QJsonObject& body, int timeoutMs){
    QUrl url(m_baseUrl);
    url.setPath(path);
    QNetworkRequest request = makeRequest(url, timeoutMs);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    return m_network->post(request, QJsonDocument(body).toJson(QJsonDocument::Compact));
}


void ApiClient::handleReply(QNetworkReply* reply, Request request, std::function<void(const QByteArray&)> onSuccess){
    connect(reply, &QNetworkReply::finished, this, [this, reply, request, onSuccess](){
        const QByteArray body = reply->readAll();
        if(reply->error() == QNetworkReply::NoError){
            onSuccess(body);
        }else{
            const QString requestId = QString::fromLatin1(reply->request().rawHeader(kRequestIdHeader));
            qWarning() << "Request failed:" << reply->url().path() << "id" << requestId << reply->errorString();
            emit errorOccurred(request, errorMessage(reply, body) + QString(" [request %1]").arg(requestId));
        }
        reply->deleteLater();
    });
}


bool ApiClient::parseJson(Request request, const QByteArray& body, QJsonDocument& doc){
    QJsonParseError parseError;
    doc = QJsonDocument::fromJson(body, &parseError);
    if(parseError.error != QJsonParseError::NoError){
        qWarning() << "JSON parsing failed:" << parseError.errorString();
        emit errorOccurred(request, "Malformed response from server: " + parseError.errorString());
        return false;
    }
    return true;
}


QString ApiClient::errorMessage(QNetworkReply* reply, const QByteArray& body){
    // FastAPI errors look like {"detail": "..."}, {"detail": {"message": "..."}}
    // or, for validation errors, {"detail": [{"msg": "...", ...}, ...]}.
    const QJsonValue detail = QJsonDocument::fromJson(body).object()["detail"];
    if(detail.isString()) return detail.toString();
    if(detail.isObject() && detail.toObject()["message"].isString()){
        return detail.toObject()["message"].toString();
    }
    if(detail.isArray() && detail.toArray().first().toObject()["msg"].isString()){
        return "Invalid request: " + detail.toArray().first().toObject()["msg"].toString();
    }
    if(reply->error() == QNetworkReply::OperationCanceledError){
        return "Request timed out";
    }
    if(reply->error() == QNetworkReply::ConnectionRefusedError
       || reply->error() == QNetworkReply::HostNotFoundError){
        return QString("Can't reach the Solon server at %1 — is it running?")
            .arg(reply->url().adjusted(QUrl::RemovePath | QUrl::RemoveQuery).toString());
    }
    return reply->errorString();
}


QJsonObject ApiClient::toJson(const Article& article){
    QJsonObject obj;
    obj["id"] = article.id;
    obj["title"] = article.title;
    obj["url"] = article.url;
    obj["source_name"] = article.source_name;
    obj["published_at"] = article.published_at;
    obj["content"] = article.content;
    // summary/tag are not sent: the backend never trusts client-side analysis.
    return obj;
}


Article ApiClient::parseArticle(const QJsonObject& object){
    Article article{};
    article.title = object["title"].toString();
    article.id = object["id"].toInt();
    article.url = object["url"].toString();
    article.source_name = object["source_name"].toString();
    article.tag = object["tag"].toString();
    article.published_at = object["published_at"].toString();
    article.content = object["content"].toString();
    article.summary = object["summary"].toString();

    return article;
}


ArticleAnalysis ApiClient::parseAnalysis(const QJsonObject& object){
    ArticleAnalysis analysis;
    analysis.summary = object["summary"].toString();
    QJsonObject bias = object["bias"].toObject();
    analysis.biasLabel = bias["label"].toString();
    analysis.biasExplanation = bias["explanation"].toString();
    return analysis;
}


TaskFailure ApiClient::parseFailure(const QJsonObject& object){
    TaskFailure failure;
    failure.task = object["task"].toString();
    failure.error = object["error"].toString();
    failure.retryable = object["retryable"].toBool();
    failure.articleId = object["article_id"].isNull() ? -1 : object["article_id"].toInt();
    return failure;
}
