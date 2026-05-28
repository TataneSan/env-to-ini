package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"strings"
)

func main() {
	inputPath := flag.String("i", "", "Fichier .env d'entrée (vide pour stdin)")
	outputPath := flag.String("o", "", "Fichier INI de sortie (vide pour stdout)")
	flag.Parse()

	if *inputPath == "" && *outputPath == "" {
		stat, err := os.Stdin.Stat()
		if err != nil || stat.Mode()&os.ModeNamedPipe == 0 {
			fmt.Fprintln(os.Stderr, "env-to-ini : convertit un fichier .env en format INI")
			fmt.Fprintln(os.Stderr, "")
			fmt.Fprintln(os.Stderr, "Usage :")
			fmt.Fprintln(os.Stderr, "  env-to-ini -i .env")
			fmt.Fprintln(os.Stderr, "  env-to-ini -i .env -o config.ini")
			fmt.Fprintln(os.Stderr, "  cat .env | env-to-ini")
			fmt.Fprintln(os.Stderr, "")
			fmt.Fprintln(os.Stderr, "Options :")
			flag.PrintDefaults()
			os.Exit(1)
		}
	}

	var reader *bufio.Scanner
	if *inputPath != "" {
		f, err := os.Open(*inputPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Erreur : impossible d'ouvrir %s : %v\n", *inputPath, err)
			os.Exit(1)
		}
		defer f.Close()
		reader = bufio.NewScanner(f)
	} else {
		reader = bufio.NewScanner(os.Stdin)
	}

	var writer *bufio.Writer = bufio.NewWriter(os.Stdout)
	if *outputPath != "" {
		f, err := os.Create(*outputPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Erreur : impossible de créer %s : %v\n", *outputPath, err)
			os.Exit(1)
		}
		defer f.Close()
		writer = bufio.NewWriter(f)
	}

	defer writer.Flush()

	count := 0
	for reader.Scan() {
		line := strings.TrimSpace(reader.Text())

		// Ignorer les lignes vides et les commentaires
		if line == "" || strings.HasPrefix(line, "#") {
			if line != "" {
				writer.WriteString(line + "\n")
			}
			continue
		}

		// Trouver le premier =
		idx := strings.Index(line, "=")
		if idx == -1 {
			continue
		}

		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])

		// Nettoyer les guillemets autour de la valeur
		if len(value) >= 2 {
			if (value[0] == '"' && value[len(value)-1] == '"') ||
				(value[0] == '\'' && value[len(value)-1] == '\'') {
				value = value[1 : len(value)-1]
			}
		}

		if key != "" {
			writer.WriteString(key + " = " + value + "\n")
			count++
		}
	}

	if err := reader.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Erreur lors de la lecture : %v\n", err)
		os.Exit(1)
	}

	src := "stdin"
	if *inputPath != "" {
		src = *inputPath
	}
	dst := "stdout"
	if *outputPath != "" {
		dst = *outputPath
	}
	fmt.Fprintf(os.Stderr, "%d variables converties de %s vers %s\n", count, src, dst)
}
