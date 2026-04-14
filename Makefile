# Makefile for Custom Shell (advsh)

CC = gcc
CFLAGS = -std=gnu11 -Wall -O2
TARGET = advsh
SRC = shell.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean
