.PRECIOUS: %.o
.SUFFIXES:
.PHONY: all compile debug clean build test

HEADERS = $(wildcard *.h)

BUILD_DIRECTORY = build
TEST_BUILD_DIRECTORY = build_test
CC = gcc -Wall -O3
CXX = g++ -Wall -Wextra -pedantic -O3 -lgtest -lgtest_main -lpthread
LIBARIES = -lm -lgsl -lgslcblas
TEST_BINARIES = $(basename $(wildcard *_test.c))
OBJECTS = $(addprefix $(BUILD_DIRECTORY)/, $(addsuffix .o, $(basename $(filter-out main.c %_test.c, $(wildcard *.c)))))
TEST_OBJECTS = $(addprefix $(TEST_BUILD_DIRECTORY)/, $(addsuffix .o, $(basename $(filter-out main.c, $(wildcard *.cpp)))))
PROJECT = $(notdir $(CURDIR))

all: build main run

run: main
	./$(BUILD_DIRECTORY)/$(PROJECT)

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

$(TEST_BUILD_DIRECTORY)/%_test: $(TEST_BUILD_DIRECTORY)/%_test.o $(TEST_OBJECTS) #../../unity/unity.o
	$(CXX) -o $@ $^ $(LIBARIES)

$(BUILD_DIRECTORY)/%.o: %.c $(HEADERS)
	$(CC) -c $< -o $@ $(LIBRARIES)

$(TEST_BUILD_DIRECTORY)/%.o: %.c $(HEADERS) #../../unity/unity.h
	$(CXX) -c $< -o $@ $(LIBRARIES)

../../unity/unity.o: ../../unity/unity.c ../../unity/unity.h ../../unity/unity_internals.h
	$(CC) -c ../../unity/unity.c -o ../../unity/unity.o -DUNITY_DOUBLE_PRECISION=1e-8f
