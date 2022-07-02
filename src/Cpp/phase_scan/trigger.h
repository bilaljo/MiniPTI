#pragma once
#include <set>
#include "../pti/Inversion.h"

namespace phase_scan {
  class trigger: protected pti_inversion::Inversion {
   public:
    trigger();

    ~trigger();

   private:
     std::multiset<double, std::greater<>> phases;
  };
}
