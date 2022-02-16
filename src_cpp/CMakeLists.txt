cmake_minimum_required(VERSION 3.21)
project(src_cpp)

set(CMAKE_CXX_STANDARD 20)

add_executable(src_cpp main.cpp readCSV.cpp readCSV.h systemPhases.cpp systemPhases.h helper.cpp helper.h)
