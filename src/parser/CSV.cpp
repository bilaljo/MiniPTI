#include "CSV.h"
#include <string>
#include <iostream>
#include <fstream>
#include <algorithm>

const int openFailed = 1;

parser::CSV::CSV(const std::string &fileName) {
  _fileName = fileName;
  _delimiter = ',';
}

parser::CSV::~CSV() = default;

void parser::CSV::findDelimter() {
  std::ifstream file(_fileName);
  std::string line;
  std::getline(file, line);
  // The first line contains only the headers. To distinguish delimiter we need
  // to take a look into a row with values.
  std::getline(file, line);
  for (const char& character : line) {
    // FIXME: Why should this be alawys true?
    if ((character != 'E' || character != 'e' || character != '+' ||
        character != '-' || character != '.') && ! std::isalpha(character)) {
      _delimiter = character;
      break;
    }
  }
}

void parser::CSV::setDelimiter(char delimiter) {
   _delimiter = delimiter;
}

char parser::CSV::getDelimiter() const {
  return _delimiter;
}

void parser::CSV::readFile() {
  std::ifstream file(_fileName);
  std::string line;
  if (file.is_open()) {
    std::cout << "Opened file " << _fileName << std::endl;
  } else {
    std::cerr << "Could not open the file." << std::endl;
    exit(1);
  }
  std::getline(file, line);
  std::string name;
  // On windows systems every line has a carriage return charachter which we should remove.
  line.erase(std::remove(line.begin(), line.end(), '\r'), line.end());
  for (const auto& character : line) {
    if (character == _delimiter) {
      _names.push_back(name);
      name = "";
    } else {
      name.push_back(character);
    }
  }
  _names.push_back(name);
  name = "";
  _rows.reserve(_names.size());
  for (size_t i = 0; i < _names.size(); i++) {
    _rows.emplace_back(std::vector<double>());
  }
  while (getline(file, line)) {
    int i = 0;
    for (const char character : line) {
      if (character == _delimiter) {
        _rows[i++].push_back(std::stod(name));
        name = "";
      } else {
        name.push_back(character);
      }
    }
    _rows[i].push_back(std::stod(name));
    name = "";
  }
  for (int i = static_cast<int>(_names.size()) - 1; i >= 0; i--) {
    _columns[_names[i]] = _rows[i];
  }
}

std::vector<std::string> parser::CSV::getNames() const {
  return _names;
}

std::vector<double>& parser::CSV::operator[](const std::string &key){
  return _columns.at(key);
}

size_t parser::CSV::getSize() const {
  return _rows[0].size();
}

int parser::CSV::saveData(const std::map<std::string, std::vector<double>>& data) const {
  std::ofstream outputData(_fileName);
  if (!outputData.is_open()) {
    return openFailed;
  }
  std::vector<std::string> headers;
  std::vector<std::vector<double>> rows;
  rows.resize((*data.begin()).second.size());
  int i = 0;
  for (const auto& [header, column] : data) {
    headers.push_back(header);
    for (const double& value : column) {
      rows[i].push_back(value);
      i++;
    }
    i = 0;
  }
  for (auto header = headers.begin(); header != headers.end() - 1; header++) {
    outputData << *header << _delimiter;
  }
  outputData << *(headers.end() - 1) << std::endl;
  for (const auto& row : rows) {
    for (auto value = row.begin(); value != row.end() - 1; value++) {
      outputData << *value << _delimiter;
    }
    outputData << *(row.end() - 1) << std::endl;
  }
  return 0;
}
