#include "system_phases.h"
#include <gsl/gsl_multimin.h>
#include <gsl/gsl_vector.h>
#include <math.h>
#include <stdio.h>

// #define DEBUG
#define STEP_SIZE 8e-4
#define TOLERANCE 1e-9
#define MAX_STEPS 1000

#define CIRCLE(x, y) (pow(x, 2) + pow(y, 2))

#define PHI(i, x, y) CIRCLE((intensities->detector_1[i] + intensities->detector_2[i] * cos(x) + \
                        intensities->detector_3[i] * cos(y)), intensities->detector_2[i] * sin(x) + \
                        intensities->detector_3[i] * sin(y))

#define PSI_X(i, x, y) (2 * intensities->detector_2[i] * (intensities->detector_2[i]  * sin(x) \
                         + intensities->detector_3[i] * sin(y)) * cos(x) - 2 * intensities->detector_2[i] \
                         * (intensities->detector_1[i] + intensities->detector_2[i] * cos(x) \
                         + intensities->detector_3[i] * cos(y)) * sin(x))

#define PSI_Y(i, x, y) (2 * intensities->detector_3[i] * (intensities->detector_2[i] * sin(x) \
                         + intensities->detector_3[i] * sin(y)) * cos(y) - 2 * intensities->detector_3[i] \
                         * (intensities->detector_1[i] + intensities->detector_2[i] * cos(x) \
                         + intensities->detector_3[i] * cos(y)) * sin(y))

void scale_signal(double *intensity) {
  double min = intensity[0];
  double max = intensity[0];
  for (int i = 0; i < DATA_SIZE; i++) {
    if (intensity[i] < min) {
      min = intensity[i];
    }
    if (intensity[i] > max) {
      max = intensity[i];
    }
  }
  for (int i = 0; i < DATA_SIZE; i++) {
    intensity[i] = 2 * (intensity[i] - min) / (max - min) - 1;
  }
}

static double get_mean(const double *data) {
  double mean = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    mean += data[i];
  }
  return mean / DATA_SIZE;
}

static double get_variance(const double *data) {
  double mean = get_mean(data);
  double variance = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    variance += pow(mean - data[i], 2);
  }
  return variance / DATA_SIZE;
}

static double standard_deviation_circle(const gsl_vector *v, void *params) {
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  struct intensities *intensities;
  double circle_result[DATA_SIZE] = {0};
  for (size_t i = 0; i < DATA_SIZE; i++) {
    intensities = (struct intensities*)params;
    circle_result[i] = CIRCLE(intensities->detector_1[i] + intensities->detector_2[i] * cos(x) +
                              intensities->detector_3[i] * cos(y), intensities->detector_2[i] * sin(x) +
                              intensities->detector_3[i] * sin(y));
  }
  return get_variance(circle_result);
}

static void gradient(const gsl_vector *v, void *params, gsl_vector *df) {
  struct intensities *intensities = (struct intensities *)params;
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  double mean = 0;
  double mean_psi_x = 0;
  double mean_psi_y = 0;
  for (size_t i = 0; i < DATA_SIZE; i++) {
    mean += PHI(i, x, y);
    mean_psi_x += PSI_X(i, x, y);
    mean_psi_y += PSI_Y(i, x, y);
  }
  mean /= DATA_SIZE;
  mean_psi_x /= DATA_SIZE;
  mean_psi_y /= DATA_SIZE;
  double x_component = 0;
  double y_component = 0;
  for (size_t i = 0; i < DATA_SIZE; i++) {
    double phi = PHI(i, x, y);
    double phi_x = (phi - mean);
    double phi_y = (phi - mean);
    double psi_x = PSI_X(i, x, y) - mean_psi_x;
    double psi_y = PSI_Y(i, x, y) - mean_psi_y;
    phi_x *= psi_x;
    phi_y *= psi_y;
    x_component += phi_x;
    y_component += phi_y;
  }
  x_component *= 2;
  y_component *= 2;
  gsl_vector_set(df, 0, x_component);
  gsl_vector_set(df, 1, y_component);
}

void function_gradient_value(const gsl_vector *x, void *params, double *f, gsl_vector *df) {
  *f = standard_deviation_circle(x, params);
  gradient(x, params, df);
}

void get_phases(double *system_phases, struct intensities *intensities) {
  int iterations = 0;
  int status;
  const gsl_multimin_fdfminimizer_type *T;
  gsl_multimin_fdfminimizer *s;
  gsl_multimin_function_fdf minimizer;
  minimizer.n = 2;
  minimizer.f = &standard_deviation_circle;
  minimizer.df = &gradient;
  minimizer.fdf = &function_gradient_value;
  minimizer.params = (void *)(intensities);
  /* Inertial gues. */
  gsl_vector *x = gsl_vector_alloc(2);
  gsl_vector_set(x, 0, 2 * M_PI / 3);
  gsl_vector_set(x, 1, 4 * M_PI / 3);
  T = gsl_multimin_fdfminimizer_conjugate_fr;
  /* The vector for the soluation. */
  s = gsl_multimin_fdfminimizer_alloc(T, 2);
  gsl_multimin_fdfminimizer_set(s, &minimizer, x, STEP_SIZE, TOLERANCE);
  do {
    iterations++;
    status = gsl_multimin_fdfminimizer_iterate(s);
    if (status) {
      break;
    }
    status = gsl_multimin_test_gradient(s->gradient, 1e-4);
#ifdef DEBUG
    if (status == GSL_SUCCESS) {
      printf("The system phases are %1.10f and %1.10f.\n",
             gsl_vector_get(s->x, 0) / M_PI * 180, gsl_vector_get(s->x, 1) / M_PI * 180);
      printf("%d iteration steps were needed.\n", iterations);
    }
#endif
  } while (status == GSL_CONTINUE && iterations < MAX_STEPS);
  gsl_vector_free(x);
  system_phases[0] = gsl_vector_get(s->x, 0);
  system_phases[1] = gsl_vector_get(s->x, 1);
  gsl_multimin_fdfminimizer_free(s);
}
