#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include "read_binary.h"
#include "lock_in_amplifier.h"

#define BUFFER_SIZE 64

int main(int argc, char **argv) {
  char file_path[BUFFER_SIZE];
  struct timeval start, end;
  parse_command_line(argc, argv, file_path);
  FILE *file = NULL;
  switch (mode) {
    case DEBUG:
    case VERBOSE:
      gettimeofday(&start, NULL);
      file = fopen("signals.csv", "w");
      break;
    case ONLINE:
    case NORMAL:
      file = fopen("signals.bin", "wb");
      break;
    default:
      break;
  }
  process_measurement(file_path, file);
  if (mode == DEBUG || mode == VERBOSE) {
    gettimeofday(&end, NULL);
    double time_taken = (double) end.tv_sec + (double) end.tv_usec / 1e6
                        - (double) start.tv_sec - (double) start.tv_usec / 1e6;
    printf("Program took %f seconds to execute\n", time_taken);
  }
  return 0;
}
