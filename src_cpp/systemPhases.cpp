#include "systemPhases.h"
#include <gsl/gsl_multimin.h>
#include <gsl/gsl_vector.h>
#include <cmath>
#include <cstddef>
#include <string>
#include "readCSV.h"

#define DEBUG

const double stepSize = 8e-2;
const double tolerance = 1e-4;
const size_t maxSteps = 1000;

template <class T>
phaseScan::SystemPhases<T>::SystemPhases() = default;

template <class T>
phaseScan::SystemPhases<T>::~SystemPhases() = default;

#define CIRCLE(x, y) (pow(x, 2) + pow(y, 2))

#define PHI(i, x, y) CIRCLE((_intensities["Detector 1"][i] + _intensities["Detector 2"][i] * cos(x) + \
                          _intensities["Detector 2"][i] * cos(y)), _intensities["Detector 2"][i] * sin(x) + \
                          _intensities["Detector 3"][i] * sin(y))

#define PSI_X(i, x, y) (2 * _intensities["Detector 2"][i] * (_intensities["Detector 2"][i])  * sin(x) \
                         + _intensities["Detector 3"][i] * sin(y)) * cos(x) - 2 * (_intensities["Detector 2"][i] \
                         * (_intensities["Detector 1"][i] + _intensities["Detector 2"][i] * cos(x) \
                         + _intensities["Detector 3"][i] * cos(y)) * sin(x))

#define PSI_Y(i, x, y) (2 * _intensities["Detector 3"][i]  * (_intensities["Detector 2"][i] * sin(x) \
                         + _intensities["Detector 3"][i] * sin(y)) * cos(y) - 2 * _intensities["Detector 3"][i] \
                         * (_intensities["Detector 1"][i] + _intensities["Detector 2"][i] * cos(x) \
                         + _intensities["Detector 3"][i] * cos(y)) * sin(y))

template <class T>
T phaseScan::SystemPhases<T>::getMean(const std::vector<T> &data) const {
  T mean = 0;
  for (const T &element : data) {
    mean += element;
  }
  return mean / data.size();
}

template <class T>
T phaseScan::SystemPhases<T>::getVariance(const std::vector<T> &data) const {
  T mean = getMean(data);
  T variance = 0;
  for (const T &element : data) {
    variance += pow(mean - element, 2);
  }
  return variance;
}

template <class T>
T phaseScan::SystemPhases<T>::varianceCircle(const gsl_vector *v, void *params) const {
  T x = gsl_vector_get(v, 0);
  T y = gsl_vector_get(v, 1);
  std::vector<T> circlePoint;
  circlePoint.reserve(_intensities.getSize());
  for (size_t i = 0; i < _intensities.getSize(); i++) {
    circlePoint[i] = CIRCLE(_intensities["Detector 1"][i] +_intensities["Detector 2"][i] * cos(x) +
                            _intensities["Detector 3"][i] * cos(y), _intensities["Detector 2"][i] * sin(x) +
                            _intensities["Detector 3"][i] * sin(y));
  }
  return getVariance(circlePoint);
}

template <class T>
void phaseScan::SystemPhases<T>::gradient(const gsl_vector *v, void *params, gsl_vector *df) {
  std::vector<T> circlePoint;
  circlePoint.reserve(_intensities.getSize());
  double x = gsl_vector_get(v, 0);
  double y = gsl_vector_get(v, 1);
  double mean = 0;
  double mean_psi_x = 0;
  double mean_psi_y = 0;
  for (size_t i = 0; i < _intensities.getSize(); i++) {
    mean += PHI(i, x, y);
    mean_psi_x += PSI_X(i, x, y);
    mean_psi_y += PSI_Y(i, x, y);
  }
  mean /= _intensities.getSize();
  mean_psi_x /= _intensities.getSize();
  mean_psi_y /= _intensities.getSize();
  double x_component = 0;
  double y_component = 0;
  for (size_t i = 0; i < _intensities.getSize(); i++) {
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


template <class T>
void phaseScan::SystemPhases<T>::function_gradient_value(const gsl_vector *x, void *params, T *f, gsl_vector *df) {
  *f = varianceCircle(x, params);
  *df = gradient(x, params, df);
}

template <class T>
std::array<T, 2> phaseScan::SystemPhases<T>::getPhases() {
  int iterations = 0;
  int status;
  std::array<T, 2> phases;
  const gsl_multimin_fdfminimizer_type *minimizer_type;
  gsl_multimin_fdfminimizer *s;
  gsl_multimin_function_fdf minimizer;
  minimizer.n = 2;
  minimizer.f = this->varianceCircle;
  minimizer.df = this->gradient;
  minimizer.fdf = this->function_gradient_value;
  minimizer.params = nullptr;
  /* Inertial gues. */
  gsl_vector *x = gsl_vector_alloc(2);
  gsl_vector_set(x, 0, 2 * M_PI / 3);
  gsl_vector_set(x, 1, 4 * M_PI / 3);
  minimizer = gsl_multimin_fdfminimizer_conjugate_fr;
  /* The vector for the soluation. */
  s = gsl_multimin_fdfminimizer_alloc(minimizer_type, 2);
  gsl_multimin_fdfminimizer_set(s, &minimizer, x, stepSize, tolerance);
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
  } while (status == GSL_CONTINUE && iterations < maxSteps);
  gsl_vector_free(x);
  phases[0] = gsl_vector_get(s->x, 0);
  phases[1] = gsl_vector_get(s->x, 1);
  gsl_multimin_fdfminimizer_free(s);
  return phases;
}

template class phaseScan::SystemPhases<double>;
