#include "system_phases.h"
#include <gsl/gsl_multimin.h>
#include <math.h>

#define CIRCLE(x, y) pow(x, 2) + pow(y, 2)

static struct coordinate elipse(const double *intensity_dector_1, const double *intensity_dector_2, const double *intensity_dector_3, double *phi,
                           struct coordinate coordinates[DATA_SIZE]) {
  for (size_t i = 0; i < DATA_SIZE; i++) {
    coordinates[i].x = intensity_dector_1[i] + intensity_dector_2[i] * cos(phi[0]) + intensity_dector_3[i] * cos(phi[1]);
    coordinates[i].y = intensity_dector_2[i] * sin(phi[0]) + intensity_dector_3[i] * sin(phi[1]);
  }
}

static double get_variance(double *values, void *params) {
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
  return variance;
}

/*
 * TODO: The function needs a more understable name.
 */

double phi(const gsl_vector *v, void *params) {
  double *intensities = (double *)params;
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  return pow(intensities[0] + intensities[1] * cos(x) + intensities[2] * cos(y), 2) +
         pow(intensities[1] * sin(x) + intensities[2] * sin(y), 2);
}

/*
 * TODO: The elipse part is still missing!
 */
static double standard_deviation_circle(const gsl_vector *v, void *params) {
 return get_variance(phi(v), params);
}

/*
 * TODO: Find a way to use properly the intensity array. Maybe a good data strucutre is requiered.
 */
static void gradient(const gsl_vector *v, void *params, gsl_vector *df) {
  double **intensities = (double **)params;
  double sum_i_2 = 0;
  double sum_i_3 = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    sum_i_2 += intensities[i][0];
    sum_i_3 += intensities[i][1];
  }
  sum_i_2 /= DATA_SIZE;
  sum_i_3 /= DATA_SIZE;
  double sum_phi = 0;
  for (size_t i = 0; i < DATA_SIZE; i++) {
    sum_phi += phi(v, intensities[i]);
  }
  sum_phi / DATA_SIZE;
  double x = 0;
  double y = 0;
  for (size_t i = 0; i < DATA_SIZE; i++) {
    x += 2 * (intensities[i][0] - sum_i_2) * (phi(v, intensities[i]) - sum_phi);
    y += 2 * (intensities[i][1] - sum_i_3) * (phi(v, intensities[i]) - sum_phi);
  }
  gsl_vector_set(df, 0, x);
  gsl_vector_set(df, 1, y);
}

/*
 * TODO: Those functions and structs need better names.
 */

void fdf(const gsl_vector *x, void *params, double *f, gsl_vector *df) {
  *f = standard_deviation_circle(x, params);
  gradient(x, params, df);
}

double get_phases(void) {
  size_t iteration_step = 0;
  const gsl_multimin_fdfminimizer_type *T;
  gsl_multimin_fdfminimizer *s;
  gsl_multimin_function_fdf function;
  function.n = 2;
  function.f = &standard_deviation_circle;
  function.df = &gradient;
  function.fdf = &fdf;
  function.params;
}
