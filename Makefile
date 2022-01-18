.SUFFIXES:
.PHONY: all compile test checkstyle
.PRECIOUS: %.o

CXX = gcc -pedantic -Wall
HEADERS = $(wildcard *.h)
MAIN_BINARIES = $(basename $(filter %_main.c, $(wildcard *.c)))
TEST_BINARIES = $(basename $(filter %_test.c, $(wildcard *.c)))
OBJECTS = $(addsuffix .o, $(basename $(filter-out %_main.cpp %_test.c, $(wildcard *.c))))
TEST_LIBARIES =
LIBARIES =

all: compile test

compile: $(MAIN_BINARIES) $(TEST_BINARIES)

test: $(TEST_BINARIES)
	for T in $(TEST_BINARIES); do valgrind --leak-check=full --track-origins=yes ./$$T; done

clean:
	rm -f *.o
	rm -f *Main
	rm -f *Test

%Main: %_main.o $(OBJECTS)
	$(CXX) -o $@ $^ $(LIBARIES)

%Test: %_test.o $(OBJECTS)
	$(CXX) -o $@ $^ $(LIBARIES) $(TEST_LIBARIES)

%.o: %.c $(HEADERS)
	$(CXX) -c $<
