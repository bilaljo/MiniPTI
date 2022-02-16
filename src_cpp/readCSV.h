#pragma once

#include <string>
#include <map>
#include <vector>


template<class T>
class CSVFile {
 public:
  CSVFile(const std::string &fileName);
  ~CSVFile();
  std::vector<std::string> getNames() const;
  std::vector<T> operator[](const std::string &key) const;
  void readFile();
  size_t getSize() const;

 private:
  std::vector<std::string> _names;
  std::vector<std::vector<T>> _rows;
  std::map<std::string, std::vector<T>> _columns;
  std::string _fileName;
};
