#include "Expections.h"

PTI::Expections::Expections() noexcept = default;

const char* PTI::Expections::what(const char* section) const noexcept {
  return section;
}
