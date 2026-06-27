
cmake_minimum_required(VERSION 3.16)
project(solon LANGUAGES CXX VERSION 0.1)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)


set(CMAKE_CXX_STANDARD 17)

find_package(Qt6 REQUIRED COMPONENTS Core Network Widgets)

add_executable(Solon src/main.cpp src/app/Application.cpp src/ui/MainWindow.cpp)
target_include_directories(Solon PRIVATE src/)
target_link_libraries(Solon Qt6::Core Qt6::Network Qt6::Widgets)
