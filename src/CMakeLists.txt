cmake_minimum_required(VERSION 3.21.1)
project(signal_analysis)

set(CMAKE_C_STANDARD 11)

set(CMAKE_C_FLAGS_RELEASE "-O3")

add_executable(signal_analysis
        passepartout_main.c
        read_csv.c
        read_csv.h
        system_phases.c
        system_phases.h
        )

target_link_libraries(signal_analysis PRIVATE m gsl gslcblas)
