#include "Expections.h"

PTI::Expections::Expections() noexcept = default;

const char* PTI::Expections::what(const char* section) const noexcept {
  return "Section or value is not definied.";
}
