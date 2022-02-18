#include "read_csv.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "system_phases.h"

void static get_names(FILE *file, struct csv *csv_file) {
  char line[BUFFER_SIZE];
  fgets(line, BUFFER_SIZE, file);
  if (line[strlen(line) - 1] == '\n') {
    line[strlen(line) - 1] = '\0';
  }
  char *sub_string = strtok(line, ",");
  for (int i = 0; i < COLUMNS && sub_string; i++) {
    strcpy(csv_file->names[i], sub_string);
    sub_string = strtok(NULL, ",");
    csv_file->numer_of_columns++;
  }
}

static void get_data(FILE *file, struct csv *csv_file) {
  char line[BUFFER_SIZE];
  char *error_string;
  for (int i = 0; i < DATA_SIZE && ! feof(file); i++) {
    fgets(line, BUFFER_SIZE, file);
    if (line[strlen(line) - 1] == '\n') {
      line[strlen(line) - 1] = '\0';
    }
    char *sub_string = strtok(line, ",");
    for (int j = 0; j < csv_file->numer_of_columns && sub_string; j++) {
      csv_file->data[j][i] = strtod(sub_string, &error_string);
      sub_string = strtok(NULL, ",");
      if (*error_string != '\0') {
        fprintf(stderr, "Error: Given string is no number.\n");
      }
    }
    csv_file->number_of_rows++;
  }
}

double *get_column(struct csv *csv_file, char *column) {
  for (size_t i = 0; i < csv_file->numer_of_columns; i++) {
    if (! strcmp(csv_file->names[i], column)) {
      return csv_file->data[i];
    }
  }
  return NULL;
}

FILE *read_csv(char *file_name, struct csv *csv_file) {
  FILE *file = fopen(file_name, "r");
  if (file == NULL) {
    perror("Error");
    return NULL;
  }
  get_names(file, csv_file);
  get_data(file, csv_file);
  return file;
}

FILE *save_data(const char *file_name, double (*data)[2]) {
  FILE *file = fopen(file_name, "w");
  if (file == NULL) {
    fprintf(stderr, "Error: Could not write file.\n");
    return NULL;
  }
  fprintf(file, "Phase 1,Phase 2\n");
  fprintf(file, "%1.10f,%1.10f\n", (*data)[0], (*data)[1]);
}
