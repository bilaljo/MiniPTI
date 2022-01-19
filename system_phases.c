#include "system_phases.h"
#include <gsl/gsl_multimin.h>
#include <math.h>

#define DEBUG
#define STEP_SIZE 0.01
#define TOLERANCE 1e-4
#define MAX_STEPS 100
#define CIRCLE(x, y) pow(x, 2) + pow(y, 2)

struct intensity {
  double detector_1;
  double detector_2;
  double detector_3;
};


void get_intensities(struct intensity *intensities) {
  
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
  return variance;
}

static double standard_deviation_circle(const gsl_vector *v, void *params) {
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  struct intensity intensities_dc[DATA_SIZE];
  double circle_result[DATA_SIZE] = {0};
  for (size_t i = 0; i < DATA_SIZE; i++) {
    /* FIXME: Does this work? */
    intensities_dc[i] = *(struct intensity*)params;
  }
  for (size_t i = 0; i < DATA_SIZE; i++) {
    circle_result[i] = CIRCLE(intensities_dc[i].detector_1 + intensities_dc[i].detector_2 * cos(x) +
                              intensities_dc[i].detector_3 * cos(y), intensities_dc[i].detector_2 * sin(x) +
                              intensities_dc[i].detector_3 * sin(y));
  }
  return get_variance(circle_result);
}

static void gradient(const gsl_vector *v, void *params, gsl_vector *df) {
  struct intensity intensities_dc[DATA_SIZE];
  for (size_t i = 0; i < DATA_SIZE; i++) {
    /* FIXME: Does this work? */
    intensities_dc[i] = *(struct intensity*)params;
  }
  double mean = 0;
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  for (size_t i = 0; i < DATA_SIZE; i++) {
    mean += CIRCLE(intensities_dc[i].detector_1 + intensities_dc->detector_2 * cos(x) +
                   intensities_dc[i].detector_3 * cos(y), intensities_dc[i].detector_2 * sin(x) +
                   intensities_dc[i].detector_3 * sin(y));
  }
  mean /= DATA_SIZE;
  for (size_t i = 0; i < DATA_SIZE; i++) {
    double circle_result = CIRCLE(intensities_dc[i].detector_1 + intensities_dc->detector_2 * cos(x) +
                                  intensities_dc[i].detector_3 * cos(y), intensities_dc[i].detector_2 * sin(x) +
                                  intensities_dc[i].detector_3 * sin(y));
    x += 2 * (intensities_dc[i].detector_2 - mean) * (circle_result - mean);
    y += 2 * (intensities_dc[i].detector_3 - mean) * (circle_result - mean);
  }
  gsl_vector_set(df, 0, x);
  gsl_vector_set(df, 1, y);
}

void function_gradient_value(const gsl_vector *x, void *params, double *f, gsl_vector *df) {
  *f = standard_deviation_circle(x, params);
  gradient(x, params, df);
}

void get_phases(double *system_phase_1, double *system_phase_2) {
  struct intensity intensities[DATA_SIZE];
  get_intensities(intensities);
  int iterations = 0;
  int status;
  const gsl_multimin_fdfminimizer_type *T;
  gsl_multimin_fdfminimizer *s;
  gsl_multimin_function_fdf minimizer;
  minimizer.n = 2;
  minimizer.f = &standard_deviation_circle;
  minimizer.df = &gradient;
  minimizer.fdf = &function_gradient_value;
  minimizer.params = (void *)intensities;
  /* Inertial gues. */
  gsl_vector *x = gsl_vector_alloc (2);
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
    status = gsl_multimin_test_gradient(s->gradient, 1e-3);
    #ifdef DEBUG
    if (status == GSL_SUCCESS) {
      printf("The system phases are %1.10f and %1.10f.\n", gsl_vector_get(s->x, 0), gsl_vector_get(s->x, 1));
      printf("%d iteration steps were needed.\n", iterations);
    }
    #endif
  /* We have to limit the maximum steps for case that we do not reach the needed percision in time. */
  } while (status == GSL_CONTINUE && iterations < MAX_STEPS);
  *system_phase_1 = gsl_vector_get(s->x, 0);
  *system_phase_2 = gsl_vector_get(s->x, 1);
  gsl_multimin_fdfminimizer_free(s);
  gsl_vector_free(x);
}
