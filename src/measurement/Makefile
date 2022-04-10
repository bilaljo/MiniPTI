.PRECIOUS: %.o
.SUFFIXES:
.PHONY: all compile debug clean build test

HEADERS = $(wildcard *.h)

BUILD_DIRECTORY = build
TEST_BUILD_DIRECTORY = build_test
CC = g++ -Wall -g3 #-O3
CXX = g++ -O3 -lgtest -lgtest_main -lpthread
LIBARIES = # -lm -lgsl -lgslcblas
TEST_BINARIES = $(basename $(wildcard *_test.cpp))
OBJECTS = $(addprefix $(BUILD_DIRECTORY)/, $(addsuffix .o, $(basename $(filter-out main.cpp %_test.cpp, $(wildcard *.cpp)))))
TEST_OBJECTS = $(addprefix $(TEST_BUILD_DIRECTORY)/, $(addsuffix .o, $(basename $(filter-out main.c, $(wildcard *.cpp)))))
PROJECT = $(notdir $(CURDIR))

all: build main

main: $(BUILD_DIRECTORY)/main.o $(OBJECTS)
	$(CC) -o $(BUILD_DIRECTORY)/$(PROJECT) $^ $(LIBARIES)

build:
	mkdir -p build

build_test:
	mkdir -p build_test

test: build_test $(TEST_BUILD_DIRECTORY)/$(TEST_BINARIES)
	for T in $(TEST_BINARIES); do ./$(TEST_BUILD_DIRECTORY)/$$T || exit; done

clean:
	rm -f build/*.o
	rm -f build/$(PROJECT)
	rm -f build_test/*.o

$(TEST_BUILD_DIRECTORY)/%_test: $(TEST_BUILD_DIRECTORY)/%_test.o $(TEST_OBJECTS) $(OBJECTS)
	$(CXX) -o $@ $^ $(LIBARIES)

$(BUILD_DIRECTORY)/%.o: %.cpp $(HEADERS)
	$(CC) -c $< -o $@ $(LIBRARIES)

$(TEST_BUILD_DIRECTORY)/%.o: %.cpp $(HEADERS)
	$(CXX) -c $< -o $@ $(LIBRARIES)
