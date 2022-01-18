#ifndef READ_CSV_H
#define READ_CSV_H

#include <stddef.h>

#define BUFFER_SIZE 10000
#define NUMBER_OF_ROWS 500
#define NAME_SIZE 500
#define NUMBER_OF_COLUMNS 2000

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

#endif /* READ_CSV_H */
