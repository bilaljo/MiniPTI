#ifndef READ_CSV_H
#define READ_CSV_H

#include <stddef.h>
#include <stdio.h>

#define DATA_SIZE 333
#define BUFFER_SIZE 50
#define NAME_SIZE 50
#define COLUMNS 10

struct csv {
  char names[COLUMNS][NAME_SIZE];
  size_t numer_of_columns;
  size_t number_of_rows;
  double data[COLUMNS][DATA_SIZE];
};

FILE *read_csv(char *file_name, struct csv *csv_file);

double *get_column(struct csv *csv_file, char *column);

FILE *save_data(const char *file_name, double (*data)[2]);

#endif /* READ_CSV_H */
