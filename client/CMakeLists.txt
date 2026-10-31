
cmake_minimum_required(VERSION 3.16)
project(solon LANGUAGES CXX VERSION 0.1)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)


set(CMAKE_CXX_STANDARD 17)
# Writes build/compile_commands.json so clangd/IDEs find the Qt headers.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(Qt6 REQUIRED COMPONENTS Core Network Widgets)

add_executable(Solon 
                src/main.cpp 
                src/app/Application.cpp 
                src/ui/MainWindow.cpp 
                src/network/ApiClient.cpp 
                src/models/ArticleListModel.cpp
                src/ui/views/ArticleDetailView.cpp
                src/ui/views/SynthesisView.cpp
                )
target_include_directories(Solon PRIVATE src/)
target_link_libraries(Solon Qt6::Core Qt6::Network Qt6::Widgets)
