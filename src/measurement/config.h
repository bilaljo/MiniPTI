#pragma once

#include <unordered_map>
#include <string>
#include <variant>

class Config {
 public:
  Config(const std::string &configFile = "pti.conf");
  ~Config();

  void openConfigFile();

  std::unordered_map<std::string, std::variant<std::string, double>> &operator[](const std::string &section);

  void writeConfig();

  void addOption(const std::string &section, const std::string &optionName, const std::variant<std::string, double> &option);

 private:
  std::unordered_map<std::string, std::unordered_map<std::string, std::variant<std::string, double>>> _options;
  std::string _configFileName;
};
