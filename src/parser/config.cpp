#include "config.h"
#include <fstream>
#include <string>
#include <variant>
#include <algorithm>

#include <iostream>
parser::Config::Config(const std::string &configFileName) {
  _configFileName = configFileName;
}

parser::Config::~Config() = default;

void parser::Config::openConfigFile() {
  std::ifstream config(_configFileName);
  if (config.is_open()) {
    std::string line;
    std::string currentSection;
    while (!config.eof()) {
#ifndef MAC_OS
      std::getline(config, line, '\n');
#else
      std::getline(config, line, '\r');
#endif
      if (line[0] == '[') {
        currentSection = line.substr(1, line.find(']') - 1);
        continue;
      } else if (line.empty()) {
        continue;
      } else {
        line.erase(std::remove(line.begin(), line.end(), ' '), line.end());
        std::string key = line.substr(0, line.find('='));
        std::string value = line.substr(line.find('=') + 1, line.length() - 1);
        try {
          this->_options[currentSection][key] = std::stod(value);
        } catch (const std::invalid_argument &) {
          if (value.length() == 1) {
            this->_options[currentSection][key] = value[0];
          } else {
            this->_options[currentSection][key] = value;
          }
        }
      }
    }
  } else {
    std::cerr << "Could open config file." << std::endl;
  }
}

void parser::Config::addOption(const std::string &section, const std::string &optionName, const option_t &option) {
  _options[section][optionName] = option;
}

void parser::Config::writeConfig() {
  std::ofstream config(_configFileName); //, std::ios_base::out);
  for (const auto&[sectionName, section]: _options) {
    config << "[" << sectionName << "]" << "\n";
    for (const auto&[optionName, option]: section) {
      config << optionName << " = ";
      try {
        config << std::get<double>(option);
      } catch (const std::bad_variant_access &) {
        try {
        config << std::get<std::string>(option);
        } catch (const std::bad_variant_access &) {
          config << std::get<char>(option);
        }
      }
      config << std::endl;
    }
    config << "\n";
  }
}

std::unordered_map<std::string, parser::option_t> &parser::Config::operator[](const std::string &section) {
  return _options[section];
}
