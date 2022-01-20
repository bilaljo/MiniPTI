#include "read_csv.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "system_phases.h"

size_t get_names(char *file_name, char names[NUMBER_OF_ROWS][NAME_SIZE]) {
  FILE *file = fopen(file_name, "r");
  if (file == NULL) {
    printf("Error: Could not read the file.\n");
    exit(1);
  }
  char line[BUFFER_SIZE];
  fgets(line, BUFFER_SIZE, file);
  if (feof(file)) {
    return -1;
  }
  char *name = strtok(line, ",");
  size_t number_of_columns = 0;
  for (; number_of_columns < NUMBER_OF_ROWS && name; number_of_columns++) {
    strcpy(names[number_of_columns], name);
    name = strtok(NULL, ",");
  }
  return number_of_columns;
}

void get_data(char *file_name, double data[NUMBER_OF_COLUMNS][NUMBER_OF_ROWS], size_t number_of_columns) {
  FILE *file = fopen(file_name, "r");
  if (file == NULL) {
    printf("Error: Could not read the file.\n");
    exit(1);
  }
  char line[BUFFER_SIZE];
  fgets(line, BUFFER_SIZE, file);  // Skip the first line because it holds only the names.
  for (int i = 0; i < NUMBER_OF_COLUMNS; i++) {
    fgets(line, BUFFER_SIZE, file);
    char *name = strtok(line, ",");
    for (size_t j = 0; j < number_of_columns && name; j++) {
      sscanf(name, "%lf", &data[i][j]);
      name = strtok(NULL, ",");
    }
  }
}

void save_data(const char *file_name, double (*data)[DATA_SIZE]) {
  FILE *file = fopen(file_name, "w");
  if (file == NULL) {
    printf("Error: Could not write file.\n");
    return;
  }
  fprintf(file, "Iteration,Phase\n");
  for (int i = 0; i < DATA_SIZE; i++) {
    fprintf(file, "%d,%1.10f\n", i, (*data)[i]);
  }
}
