#pragma once
#include <exception>
#include <string>
#include <iostream>

namespace PTI {
  class Expections : public std::exception {
   public:
    Expections() noexcept;

    const char* what(const char* section) const noexcept;
  };
};
