#pragma once

#include <unordered_map>
#include <string>
#include <variant>


namespace parser {
  typedef std::variant<std::string, char, double> option_t;

  class Config {
   public:
    explicit Config(const std::string &configFile);

    ~Config();

    // Reads a *.conf file and saves its content into _options. Because ; is possible as delimiter for the data
    // files, ; is not treated as comment and therefor just a regulary character.
    void openConfigFile();

    std::unordered_map<std::string, option_t> &operator[](const std::string &key);

    // Writes the sections with its key-value pairs into a *.conf file, which are stored in _options.
    // Note that everything in the old *.conf file is overwritten and only the _options is written.
    void writeConfig();

    void addOption(const std::string &section, const std::string &optionName, const option_t &option);

   private:
    // The conf file has the following structure:
    //  [section]
    //  keyword = value
    // We represent the keyword-values as hash tables. And the section of hash tables, of these key-values pairs.
    std::unordered_map<std::string, std::unordered_map<std::string, option_t>> _options;

    std::string _configFileName;
  };
}
