#pragma once

#include <QList>
#include <QMap>
#include <QString>

// Mirrors of the backend's analysis models (see backend/models.py).

struct ArticleAnalysis {
    QString summary;          // empty when unavailable
    QString biasLabel;        // "None" when no notable bias was found
    QString biasExplanation;
};

struct TaskFailure {
    QString task;             // "summarize" | "detect_bias" | "synthesize"
    QString error;
    bool retryable = false;
    int articleId = -1;       // -1 for batch-level tasks (synthesize)
};

struct BatchAnalysis {
    QMap<int, ArticleAnalysis> analyses;   // article id -> analysis
    QString synthesis;                     // empty when unavailable
    QList<int> sources;                    // ids the synthesis was built from
    QList<TaskFailure> failed;
    QList<int> skipped;                    // ids dropped by the token budget
    int estimatedTokens = 0;
};
