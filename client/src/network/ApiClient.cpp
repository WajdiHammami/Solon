
#include "ApiClient.h"
#include <QUrl>
#include <QUrlQuery>
#include <QDebug>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonArray>
#include <QNetworkRequest>

ApiClient::ApiClient(QObject* parent): QObject(parent), m_network(new QNetworkAccessManager(this)), m_baseUrl("http://localhost:8000"){}

void ApiClient::fetchFeed(const QString& topic, int pageSize, int page){
    QUrl url(m_baseUrl);
    QUrlQuery query;

    url.setPath("/feed");
    query.addQueryItem("topic", topic);
    query.addQueryItem("page", QString::number(page));
    query.addQueryItem("page_size", QString::number(pageSize));

    url.setQuery(query);
    qDebug() << url.toString();
    qDebug() << "Sending request to:" << url.toString();
    auto reply = m_network->get(QNetworkRequest(url));
    qDebug() << "Request sent, reply:" << reply;
    connect(reply, &QNetworkReply::finished, this, [this, reply](){
        if(reply->error() == QNetworkReply::NoError){
           QJsonParseError parseError;
           qDebug() << "Reply received, error:" << reply->error();

           QJsonDocument json_response = QJsonDocument::fromJson(reply->readAll(), &parseError);
           if (parseError.error == QJsonParseError::NoError){
            if (json_response.isArray()){
                QJsonArray jsonArray = json_response.array();
                QList<Article> articles;
                for(const QJsonValue& val: jsonArray){
                    articles.append(parseArticle(val.toObject()));
                }
                emit feedReceived(articles);
            }else{
                qDebug() << "The Data is valid json, but it is not an array";
                emit errorOccurred("Unexpected response format: expected a JSON array");
            }
           }else{
                qDebug() << "JSON parsing failed:" << parseError.errorString();
                emit errorOccurred(parseError.errorString());
           }
        }else{
           emit errorOccurred(reply->errorString()); 
        }
        reply->deleteLater();
    });
}



void ApiClient::summarizeRequest(const QList<Article>& articles){
    QUrl url(m_baseUrl);

    url.setPath("/summarize");
    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");

    QJsonArray jsonArray;
    for(const auto& article: articles){
        QJsonObject obj;
        obj["id"] = article.id;
        obj["title"] = article.title;
        obj["url"] = article.url;
        obj["source_name"] = article.source_name;
        obj["tag"] = article.tag;
        obj["published_at"] = article.published_at;
        obj["content"] = article.content;
        obj["summary"] = article.summary;
        jsonArray.append(obj);
    }
    QJsonObject requestBody;
    requestBody["articles"] = jsonArray;
    QJsonDocument jsonBody(requestBody);
    auto* reply = m_network->post(request, jsonBody.toJson());

    connect(reply, &QNetworkReply::finished, this, [this, reply, articles](){
        if(reply->error() == QNetworkReply::NoError){
            QJsonParseError parseError;
            QJsonDocument jsonReply = QJsonDocument::fromJson(reply->readAll(), &parseError);

            if(parseError.error == QJsonParseError::NoError){
                QJsonObject Jobject = jsonReply.object();
                try{
                    if(articles.size() == 1){
                        emit summarizationOneArticleReceived(parseArticle(Jobject));
                    } else {
                        QList<QString> summaries;
                        QJsonArray arr = Jobject["summaries"].toArray();
                        for(const QJsonValue& val : arr){
                            summaries.append(val.toString());
                        }
                        QMap<int, QPair<QString, QString>> tags;
                        QJsonObject tagsObj = Jobject["tags"].toObject();
                        for(auto it = tagsObj.begin(); it != tagsObj.end(); it++){
                            int id = it.key().toInt();
                            QJsonArray pair = it.value().toArray();
                            tags[id] = QPair<QString, QString>(pair[0].toString(), pair[1].toString());
                        }
                        emit summarizationMultiArticleReceived(summaries, Jobject["synthesis"].toString(), tags);
                    }

                }catch(const std::exception& e){
                    emit errorOccurred("Unexpected Json Format");
                }
           }else{
            emit errorOccurred(parseError.errorString());
           }
        }
        reply->deleteLater();
    });
}



void ApiClient::contentRequest(const QString& url){
    QUrl requestUrl(m_baseUrl);
    QUrlQuery query;
    requestUrl.setPath("/article/content");
    query.addQueryItem("url", url);
    requestUrl.setQuery(query);

    auto* reply = m_network->get(QNetworkRequest(requestUrl));
    connect(reply, &QNetworkReply::finished, this, [this, reply](){
        if(reply->error() == QNetworkReply::NoError){
            QByteArray raw = reply->readAll();
            QJsonDocument doc = QJsonDocument::fromJson(QByteArray("[") + raw + QByteArray("]"));
            QString content = doc.array().first().toString();
            emit contentReceived(content);
        }else{
            emit errorOccurred(reply->errorString());
        }
        reply->deleteLater();
    });
    
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