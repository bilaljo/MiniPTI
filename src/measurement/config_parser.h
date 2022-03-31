#ifndef CONFIG_PARSER_H
#define CONFIG_PARSER_H

#define NUMBER_OF_SECTIONS 10
#define BUFFER_SIZE 60

struct conf_t {
  char sections[NUMBER_OF_SECTIONS][BUFFER_SIZE];
};

#endif /* CONFIG_PARSER_H */
