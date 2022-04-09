#include <stdio.h>
#include "read_binary.h"
#include "lock_in_amplifier.h"
#define BUFFER_SIZE 64

int main(int argc, char **argv) {
  char file_path[BUFFER_SIZE] = "220224_NO2.bin";
  enum mode_t mode = NORMAL;
  parse_command_line(argc, argv, file_path, &mode);
  FILE *binary_file = open_file(file_path);
  FILE *output = NULL;
  if (mode == BINARY) {
    output = fopen("output.bin", "wb");
  } else {
    output = fopen("output.csv", "w");
    fprintf(output, "X1,Y1,X2,Y2,X3,Y3,DC1,DC2,DC3\n");
  }
  process_measurement(binary_file, mode, output);
  fclose(binary_file);
  fclose(output);
  return 0;
}
