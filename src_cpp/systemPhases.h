#pragma once
#include <gsl/gsl_vector.h>
#include <array>
#include <string>
#include <map>
#include <vector>
#include "readCSV.h"

#define DATA_SIZE 333 //667 //2823

namespace phaseScan {
  template <class T>
  class SystemPhases {
   public:
    SystemPhases();
    ~SystemPhases();

    std::array<T, 2> getPhases();

   private:
    T getMean(const std::vector<T> &data) const;
    T getVariance(const std::vector<T> &data) const;
    void gradient(const gsl_vector *v, void *params, gsl_vector *df);
    T varianceCircle(const gsl_vector *v, void *params) const;
    void function_gradient_value(const gsl_vector *x, void *params, T *f, gsl_vector *df);
    CSVFile<T> _intensities;
  };
};
