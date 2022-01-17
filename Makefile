all: compile

compile:
	gcc -o passepartout main.c read_csv.c

clean:
	rm passepartout
