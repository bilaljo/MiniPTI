#pragma once

#include <string>
#include <unordered_map>
#include <map>
#include <vector>

namespace parser {
  class CSV {
   public:
    explicit CSV(const std::string &fileName);

    ~CSV();

    void findDelimter();

    void setDelimiter(char delimiter);

    char getDelimiter() const;

    std::vector<std::string> getNames() const;

    std::vector<double> &operator[](const std::string &key);

    void readFile();

    size_t getSize() const;
    
    int saveData(const std::map<std::string, std::vector<double>> &data) const;

   private:
    std::vector<std::string> _names;

    std::vector<std::vector<double>> _rows;

    std::unordered_map<std::string, std::vector<double>> _columns;

    std::string _fileName;

    char _delimiter;
  };
}
