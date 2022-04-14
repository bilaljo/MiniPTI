cmake_minimum_required(VERSION 3.21)
project(PTI_Inversion)

set(CMAKE_CXX_STANDARD 17)
set(BUILD_TYPE_RELEASE TRUE)
set(CMAKE_CXX_FLAGS "-g3 -Wall -pedantic")

if (WIN64)
    set(PARSER ..\\parser\\)
else()
    set(PARSER ../parser/)
endif(WIN64)

add_executable(PhaseScan PhaseScanMain.cpp OutputPhase.cpp OutputPhase.h ${PARSER}CSV.cpp ${PARSER}CSV.h
               ${PARSER}Config.cpp ${PARSER}Config.h)
