#pragma once

#include <map>
#include <string>
#include <any>
#include <variant>

class Config {
 public:
  explicit Config(const std::string &configFile);
  ~Config();

  std::map<std::string, std::variant<std::string, double>> &operator[](const std::string &section);

 private:
  void openConfigFile(const std::string &configFile);
  std::map<std::string, std::map<std::string, std::variant<std::string, double>>> _options;
};
