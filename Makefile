CC = gcc
CFLAGS = -Wall -Wextra -O2 -Isrc/c
SRCS = src/c/*.c
TARGET = libquery

ifeq ($(OS),Windows_NT)
    TARGET  = libquery.exe
    LDFLAGS = -lws2_32
else
    LDFLAGS =
endif

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(TARGET) libquery.exe

.PHONY: all clean
