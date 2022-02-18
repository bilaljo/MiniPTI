#ifndef SYSTEM_PHASES_H
#define SYSTEM_PHASES_H

#include <stddef.h>

#define DATA_SIZE 333

struct intensities {
  double *detector_1;
  double *detector_2;
  double *detector_3;
};

void scale_signal(double *intensity);

void get_phases(double *system_phases, struct intensities *intensities);

#endif /* SYSTEM_PHASES_H */
