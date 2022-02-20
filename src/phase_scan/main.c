#include <string.h>
#include <stdlib.h>
#include "read_csv.h"
#include "system_phases.h"

int main(int argc, char **argv) {
  struct csv csv_file;
  char file_path[BUFFER_SIZE] = "../dc.csv";
  if (argc > 1) {
    strcpy(file_path, argv[1]);
  }
  if (! read_csv(file_path, &csv_file)) {
    exit(1);
  }
  double correction_phases[2] = {0};
  scale_signal(get_column(&csv_file, "Detector 1"));
  scale_signal(get_column(&csv_file, "Detector 2"));
  scale_signal(get_column(&csv_file, "Detector 3"));
  struct intensities intensities = {
    .detector_1 = get_column(&csv_file, "Detector 1"),
    .detector_2 = get_column(&csv_file, "Detector 2"),
    .detector_3 = get_column(&csv_file, "Detector 3"),
  };
  get_phases(correction_phases, &intensities);
  if (! save_data("phases.csv", &correction_phases)) {
    return 1;
  }
  return 0;
}
