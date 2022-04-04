#include "config.h"
#include <fstream>
#include <string>
#include <algorithm>

Config::Config(const std::string &configFile) {
  this->openConfigFile(configFile);
}

Config::~Config() = default;

void Config::openConfigFile(const std::string &configFile) {
  std::ifstream config(configFile);
  std::string sectionName;
  std::string keyWord;
  std::string key;
  char currentSymbol;
  std::map<std::string, std::any> section;
  while (! config.eof()) {
    while (config >> currentSymbol, currentSymbol == '\n');
    sectionName = "";
    std::getline(config, sectionName, ']');
    config >> currentSymbol;
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
      } catch (std::invalid_argument&) {
        this->_options[sectionName][keyWord] = key;
      }
      key = "";
      keyWord = "";
    }
  }
}

std::map<std::string, std::variant<std::string, double>> &Config::operator[](const std::string &section) {
  return _options[section];
}
