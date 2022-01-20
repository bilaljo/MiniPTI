#include "system_phases.h"
#include <gsl/gsl_multimin.h>
#include <math.h>

#define DEBUG
#define STEP_SIZE 1e-4
#define TOLERANCE 1e-4
#define MAX_STEPS 1000

#define CIRCLE(x, y) pow(x, 2) + pow(y, 2)

static void scale_signal(double (*intensity)[DATA_SIZE]) {
  double min = (*intensity)[0];
  double max = (*intensity)[0];
  for (int i = 0; i < DATA_SIZE; i++) {
    if ((*intensity)[i] < min) {
      min = (*intensity)[i];
    }
    if ((*intensity)[i] > max) {
      max = (*intensity)[i];
    }
  }
  for (int i = 0; i < DATA_SIZE; i++) {
    (*intensity)[i] = 2 * ((*intensity)[i] - min) / (max - min) - 1;
  }
}

void set_intensities(double (*intensity_1)[DATA_SIZE], double (*intensity_2)[DATA_SIZE],
                     double (*intensity_3)[DATA_SIZE], struct intensity (*intensties)[DATA_SIZE]) {
  scale_signal(intensity_1);
  scale_signal(intensity_2);
  scale_signal(intensity_3);
  for (int i = 0; i < DATA_SIZE; i++) {
    (*intensties)[i].detector_1 = (*intensity_1)[i];
    (*intensties)[i].detector_2 = (*intensity_2)[i];
    (*intensties)[i].detector_3 = (*intensity_3)[i];
  }
}

static double get_mean(const double (*data)[DATA_SIZE]) {
  double mean = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    mean += (*data)[i];
  }
  return mean / DATA_SIZE;
}

static double get_variance(const double (*data)[DATA_SIZE]) {
  double mean = get_mean(data);
  double variance = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    variance += pow(mean - (*data)[i], 2);
  }
  return variance;
}

static double standard_deviation_circle(const gsl_vector *v, void *params) {
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  struct intensity intensities_dc[DATA_SIZE];
  double circle_result[DATA_SIZE] = {0};
  for (size_t i = 0; i < DATA_SIZE; i++) {
    intensities_dc[i] = ((struct intensity *)params)[i];
  }
  for (size_t i = 0; i < DATA_SIZE; i++) {
    circle_result[i] = CIRCLE(intensities_dc[i].detector_1 + intensities_dc[i].detector_2 * cos(x) +
                              intensities_dc[i].detector_3 * cos(y), intensities_dc[i].detector_2 * sin(x) +
                              intensities_dc[i].detector_3 * sin(y));
  }
  return get_variance(&circle_result);
}

static void gradient(const gsl_vector *v, void *params, gsl_vector *df) {
  struct intensity intensities_dc[DATA_SIZE];

  #define PHI(i, x, y) CIRCLE((intensities_dc[i].detector_1 + intensities_dc[i].detector_2 * cos(x) + \
                        intensities_dc[i].detector_3 * cos(y)), intensities_dc[i].detector_2 * sin(x) + \
                        intensities_dc[i].detector_3 * sin(y))

  #define PSI_X(i, x, y) (2 * intensities_dc[i].detector_2 * (intensities_dc[i].detector_2  * sin(x) \
                         + intensities_dc[i].detector_3 * sin(y)) * cos(x) - 2 * intensities_dc[i].detector_2 \
                         * (intensities_dc[i].detector_1 + intensities_dc[i].detector_2 * cos(x) \
                         + intensities_dc[i].detector_3 * cos(y)) * sin(x))

  #define PSI_Y(i, x, y) (2 * intensities_dc[i].detector_3 * (intensities_dc[i].detector_2 * sin(x) \
                         + intensities_dc[i].detector_3 * sin(y)) * cos(y) - 2 * intensities_dc[i].detector_3 \
                         * (intensities_dc[i].detector_1 + intensities_dc[i].detector_2 * cos(x) \
                         + intensities_dc[i].detector_3 * cos(y)) * sin(y))

  for (size_t i = 0; i < DATA_SIZE; i++) {
    intensities_dc[i] = ((struct intensity *)params)[i];
  }
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
  for (size_t i = 0; i < DATA_SIZE; i++) {
    double phi = PHI(i, x, y);
    double phi_x = (phi - mean);
    double phi_y = (phi - mean);
    double psi_x = PSI_X(i, x, y) - mean_psi_x;
    double psi_y = PSI_Y(i, x, y) - mean_psi_y;
    phi_x *= psi_x;
    phi_y *= psi_y;
    x += phi_x;
    y += phi_y;
  }
  gsl_vector_set(df, 0, x);
  gsl_vector_set(df, 1, y);
}

void function_gradient_value(const gsl_vector *x, void *params, double *f, gsl_vector *df) {
  *f = standard_deviation_circle(x, params);
  gradient(x, params, df);
}

void get_phases(double (*system_phases)[2], struct intensity (*intensities)[DATA_SIZE]) {
  int iterations = 0;
  int status;
  const gsl_multimin_fdfminimizer_type *T;
  gsl_multimin_fdfminimizer *s;
  gsl_multimin_function_fdf minimizer;
  minimizer.n = 2;
  minimizer.f = &standard_deviation_circle;
  minimizer.df = &gradient;
  minimizer.fdf = &function_gradient_value;
  minimizer.params = (void *)(*intensities);
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
      printf("The system phases are %1.10f and %1.10f.\n", gsl_vector_get(s->x, 0), gsl_vector_get(s->x, 1));
      printf("%d iteration steps were needed.\n", iterations);
    }
#endif
    /* We have to limit the maximum steps for case that we do not reach the needed percision in time. */
  } while (status == GSL_CONTINUE && iterations < MAX_STEPS);
  (*system_phases)[0] = gsl_vector_get(s->x, 0);
  (*system_phases)[1] = gsl_vector_get(s->x, 1);
  gsl_multimin_fdfminimizer_free(s);
  gsl_vector_free(x);
}
