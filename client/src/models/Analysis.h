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

// LLM consumption of one operation, as reported by the backend.
struct LlmUsage {
    int calls = 0;
    int inputTokens = 0;
    int outputTokens = 0;
    bool hasCost = false;     // false when no price is configured on the server
    double cost = 0.0;
    QString currency;
    QString model;

    int totalTokens() const { return inputTokens + outputTokens; }
    LlmUsage& operator+=(const LlmUsage& other) {
        calls += other.calls;
        inputTokens += other.inputTokens;
        outputTokens += other.outputTokens;
        if (other.hasCost) {
            cost += other.cost;
            hasCost = true;
            currency = other.currency;
        }
        if (!other.model.isEmpty()) model = other.model;
        return *this;
    }
};

struct BatchAnalysis {
    QMap<int, ArticleAnalysis> analyses;   // article id -> analysis
    QString synthesis;                     // empty when unavailable
    QList<int> sources;                    // ids the synthesis was built from
    QList<TaskFailure> failed;
    QList<int> skipped;                    // ids dropped by the token budget
    int estimatedTokens = 0;
    LlmUsage usage;
};
