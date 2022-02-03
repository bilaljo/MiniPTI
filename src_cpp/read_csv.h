#ifndef READ_CSV_H
#define READ_CSV_H

#include <stddef.h>

#define BUFFER_SIZE 100
#define NUMBER_OF_ROWS 4
#define NAME_SIZE 100
#define NUMBER_OF_COLUMNS 667 //2823

#include "system_phases.h"

enum csv_file_names {
  DC_1 = 1,
  DC_2,
  DC_3,
};

struct csv_file {
  char names[NUMBER_OF_ROWS][NAME_SIZE];
  double data[NUMBER_OF_COLUMNS][NUMBER_OF_ROWS];
};

/*
 * Read the name of every column of a csv file and save it into the array names.
 * Returns the number of found names.
 */
size_t get_names(char *file_name, char names[NUMBER_OF_ROWS][NAME_SIZE]);

void get_data(char *file_name, double data[NUMBER_OF_COLUMNS][NUMBER_OF_ROWS], size_t number_of_columns);

void save_data(const char *file_name, double (*data)[DATA_SIZE]);

#endif /* READ_CSV_H */
