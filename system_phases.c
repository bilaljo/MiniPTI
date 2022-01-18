#include "system_phases.h"
#include <gsl/gsl_multimin.h>
#include <math.h>

#define CIRCLE(x, y) pow(x, 2) + pow(y, 2)

static struct coordinate ellipise(const double *intensity_dector_1, const double *intensity_dector_2, const double *intensity_dector_3, double *phi,
                           struct coordinate coordinates[DATA_SIZE]) {
  for (size_t i = 0; i < DATA_SIZE; i++) {
    coordinates[i].x = intensity_dector_1[i] + intensity_dector_2[i] * cos(phi[0]) + intensity_dector_3[i] * cos(phi[1]);
    coordinates[i].y = intensity_dector_2[i] * sin(phi[0]) + intensity_dector_3[i] * sin(phi[1]);
  }
}

static double standard_deviation_circle(double *phi) {
  struct coordinate circle[DATA_SIZE];
  double mean = 0;
  // ellipise(intensity_dector_1, *intensity_dector_2, intensity_dector_3 phi, circle);
  for (int i = 0; i < DATA_SIZE; i++) {
    mean += CIRCLE(circle[i].x, circle[i].y);
  }
  mean /= DATA_SIZE;
  double variance = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    variance += pow(mean - CIRCLE(circle[i].x, circle[i].y), 2);
  }
  return sqrt(variance);
}

