// SPDX-License-Identifier: BSD-3-Clause

package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

const handoffDir = "/run/executor-secrets"
const bunPath = "/usr/local/bin/bun"

var secretNames = []string{"BETTER_AUTH_SECRET", "EXECUTOR_SECRET_KEY", "OP_SERVICE_ACCOUNT_TOKEN"}

func executorCommand() (string, []string) {
	return bunPath, []string{"bun", "run", "dist-server/serve.js"}
}

func readSecrets(dir string) (map[string]string, error) {
	values := make(map[string]string, len(secretNames))
	for _, name := range secretNames {
		data, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil || len(strings.TrimSpace(string(data))) == 0 {
			return nil, fmt.Errorf("invalid runtime secret %s", name)
		}
		values[name] = string(data)
	}
	return values, nil
}

func waitForSecrets(dir string, timeout time.Duration) (map[string]string, error) {
	deadline := time.Now().Add(timeout)
	for {
		values, err := readSecrets(dir)
		if err == nil {
			return values, nil
		}
		if time.Now().After(deadline) {
			return nil, err
		}
		time.Sleep(100 * time.Millisecond)
	}
}

func main() {
	secrets, err := waitForSecrets(handoffDir, 60*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "executor launcher:", err)
		os.Exit(1)
	}
	env := append(
		os.Environ(),
		"BETTER_AUTH_SECRET="+secrets["BETTER_AUTH_SECRET"],
		"EXECUTOR_SECRET_KEY="+secrets["EXECUTOR_SECRET_KEY"],
		"OP_SERVICE_ACCOUNT_TOKEN="+secrets["OP_SERVICE_ACCOUNT_TOKEN"],
	)
	path, args := executorCommand()
	if err := syscall.Exec(path, args, env); err != nil {
		fmt.Fprintln(os.Stderr, "executor launcher: exec failed")
		os.Exit(1)
	}
}
