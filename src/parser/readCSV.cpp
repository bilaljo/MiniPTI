#include "readCSV.h"
#include <string>
#include <iostream>
#include <fstream>

parser::CSVFile::CSVFile(const std::string &fileName, const char delimiter) {
  _fileName = fileName;
  _delimiter = delimiter;
}

parser::CSVFile::~CSVFile() = default;

void parser::CSVFile::readFile() {
  std::ifstream file(_fileName);
  std::string line;
  if (file.is_open()) {
    std::cout << "Opened file " << _fileName << std::endl;
  } else {
    std::cerr << "Could not open the file." << std::endl;
    exit(1);
  }
  getline(file, line);
  std::string name;
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
    _rows.push_back(std::vector<double>());
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
  for (int i = _names.size() - 1; i >= 0; i--) {
    _columns[_names[i]] = _rows[i];
  }
}

std::vector<std::string> parser::CSVFile::getNames() const {
  return _names;
}

std::vector<double>& parser::CSVFile::operator[](const std::string &key){
  return _columns.at(key);
}

size_t parser::CSVFile::getSize() const {
  return _rows.size();
}
