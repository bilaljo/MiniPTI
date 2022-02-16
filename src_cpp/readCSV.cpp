#include "readCSV.h"
#include <string>
#include <iostream>
#include <fstream>

template<class T>
CSVFile<T>::CSVFile(const std::string &fileName) {
  this->_fileName = fileName;
}

template<class T>
CSVFile<T>::~CSVFile() = default;

template<class T>
void CSVFile<T>::readFile() {
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
    if (character == ',') {
      _names.push_back(name);
      name = "";
    } else {
      name.push_back(character);
    }
  }
  _names.push_back(name);
  name = "";
  _rows.reserve(_names.size());
  for (int i = 0; i < _names.size(); i++) {
    _rows.push_back(std::vector<T>());
  }
  while (getline(file, line)) {
    int i = 0;
    for (const char character : line) {
      if (character == ',') {
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

template<class T>
std::vector<std::string> CSVFile<T>::getNames() const {
  return _names;
}

template<class T>
std::vector<T> CSVFile<T>::operator[](const std::string &key) const {
  return _columns[key];
}

template<class T>
size_t CSVFile<T>::getSize() const {
  return _rows.size();
}

template class CSVFile<double>;
