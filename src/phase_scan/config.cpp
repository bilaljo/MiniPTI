#include "config.h"
#include <fstream>
#include <string>
#include <variant>
#include <algorithm>

parser::Config::Config(const std::string &configFileName) {
  _configFileName = configFileName;
}

parser::Config::~Config() = default;

void parser::Config::openConfigFile() {
  std::ifstream config(_configFileName);
  std::string sectionName;
  std::string keyWord;
  std::string key;
  char currentSymbol;
  std::unordered_map<std::string, option_t> section;
  while (! config.eof()) {
    while (config >> currentSymbol, currentSymbol == '\n');
    sectionName = "";
    std::getline(config, sectionName, ']');
    while (config >> currentSymbol, ! config.eof() && currentSymbol != '[' && currentSymbol != '\n') {
      while (! config.eof() && currentSymbol != '=' && currentSymbol) {
        keyWord.append(1, currentSymbol);
        config >> currentSymbol;
      }
      keyWord.erase(std::remove(keyWord.begin(), keyWord.end(), ' '), keyWord.end());
      keyWord.erase(std::remove(keyWord.begin(), keyWord.end(), '\n'), keyWord.end());
      keyWord.erase(std::remove(keyWord.begin(), keyWord.end(), ';'), keyWord.end());
      while (! config.eof() && currentSymbol != '\n' && currentSymbol != ';') {
        config >> std::noskipws >> currentSymbol;
        key.append(1, currentSymbol);
      }
      key.erase(std::remove(key.begin(), key.end(), ' '), key.end());
      key.erase(std::remove(key.begin(), key.end(), '\n'), key.end());
      key.erase(std::remove(key.begin(), key.end(), ';'), key.end());
      try {
        this->_options[sectionName][keyWord] = std::stod(key);
      } catch (const std::invalid_argument&) {
        this->_options[sectionName][keyWord] = key;
      }
      key = "";
      keyWord = "";
    }
  }
}

void parser::Config::addOption(const std::string &section, const std::string &optionName, const option_t &option) {
  _options[section][optionName] = option;
}

void parser::Config::writeConfig() {
  std::fstream config(_configFileName, std::ios_base::out);
  for (const auto&[sectionName, section]: _options) {
    config << "[" << sectionName << "]" << "\n";
    for (const auto&[optionName, option]: section) {
      try {
        config << optionName << " = " << std::get<double>(option) << "\n";
      } catch (const std::bad_variant_access &) {
        config << optionName << " = " << std::get<std::string>(option) << "\n";
      }
    }
    config << "\n";
  }
}

std::unordered_map<std::string, parser::option_t> &parser::Config::operator[](const std::string &section) {
  return _options.at(section);
}

