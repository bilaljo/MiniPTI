cmake_minimum_required(VERSION 3.16)
project(PTI_Inversion)

set(CMAKE_CXX_STANDARD 17)
set(BUILD_TYPE_RELEASE TRUE)
set(CMAKE_CXX_FLAGS "-g3 -ggdb -Wall -pedantic")

if (WIN64)
    set(PARSER ..\\parser\\)
else()
    set(PARSER ../parser/)
endif(WIN64)

add_executable(decimation DecimationMain.cpp readBinary.cpp lockInAmplifier.cpp ${PARSER}CSV.cpp ${PARSER}CSV.h
               ${PARSER}Config.cpp ${PARSER}Config.h CommonNoiseRecjection.cpp CommonNoiseRecjection.h)
