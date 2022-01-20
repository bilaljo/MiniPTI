cmake_minimum_required(VERSION 3.21)
project(signal_analysis)

set(CMAKE_C_STANDARD 11)

add_executable(signal_analysis
        passepartout_main.c
        read_csv.c
        read_csv.h
        system_phases.c
        system_phases.h pti_phase.c pti_phase.h lock_in_amplifier.c lock_in_amplifier.h)

target_link_libraries(signal_analysis PRIVATE m gsl gslcblas m)
