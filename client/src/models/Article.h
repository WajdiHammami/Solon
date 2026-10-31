#pragma once

#include <QString>



struct Article{


    int id = -1;
    QString title;
    QString url;
    QString source_name;
    QString tag;
    QString tag_explanation;
    QString published_at;
    QString content;      // as issued by /feed; sent back unchanged (server verifies it)
    QString summary;
    QString full_text;    // scraped for the reader view; never sent to the server

};
