package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
)

func main() {
	if len(os.Args) > 2 {
		// Allow flag combinations like -s NAME
		hasFlag := false
		for _, arg := range os.Args[1:] {
			if arg == "-s" || arg == "--section" {
				hasFlag = true
				break
			}
		}
		if !hasFlag {
			fmt.Fprintf(os.Stderr, "Usage: env-to-ini [file.env]\n")
			fmt.Fprintf(os.Stderr, "\nConvert a .env file to INI format.\n")
			fmt.Fprintf(os.Stderr, "Reads from stdin if no file provided.\n")
			fmt.Fprintf(os.Stderr, "\nOptions:\n")
			fmt.Fprintf(os.Stderr, "  -s, --section NAME  Group all keys under a section [NAME]\n")
			fmt.Fprintf(os.Stderr, "\nExamples:\n")
			fmt.Fprintf(os.Stderr, "  env-to-ini config.env\n")
			fmt.Fprintf(os.Stderr, "  cat config.env | env-to-ini\n")
			fmt.Fprintf(os.Stderr, "  env-to-ini -s database config.env\n")
			os.Exit(1)
		}
	}

	var section string
	var filename string
	args := os.Args[1:]

	for len(args) > 0 {
		switch args[0] {
		case "-s", "--section":
			if len(args) < 2 {
				fmt.Fprintf(os.Stderr, "Error: --section requires a value\n")
				os.Exit(1)
			}
			section = args[1]
			args = args[2:]
		default:
			filename = args[0]
			args = args[1:]
		}
	}

	var reader io.Reader
	if filename != "" {
		f, err := os.Open(filename)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error opening file: %v\n", err)
			os.Exit(1)
		}
		defer f.Close()
		reader = f
	} else {
		reader = os.Stdin
	}

	scanner := bufio.NewScanner(reader)
	type envVar struct {
		Key   string
		Value string
	}
	var vars []envVar

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		// Skip export prefix
		line = strings.TrimPrefix(line, "export ")

		idx := strings.IndexByte(line, '=')
		if idx == -1 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])

		// Remove surrounding quotes
		if len(value) >= 2 {
			if (value[0] == '"' && value[len(value)-1] == '"') ||
				(value[0] == '\'' && value[len(value)-1] == '\'') {
				value = value[1 : len(value)-1]
			}
		}

		if key != "" {
			vars = append(vars, envVar{Key: key, Value: value})
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input: %v\n", err)
		os.Exit(1)
	}

	// Output INI format
	if section != "" {
		fmt.Printf("[%s]\n", section)
	}
	for _, v := range vars {
		fmt.Printf("%s = %s\n", v.Key, v.Value)
	}
}
