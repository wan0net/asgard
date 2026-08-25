// SPDX-License-Identifier: BSD-3-Clause

package main

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func writeSecret(t *testing.T, dir, name, value string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(value), 0400); err != nil {
		t.Fatal(err)
	}
}

func TestReadSecretsAcceptsCompleteHandoffWithoutRemovingIt(t *testing.T) {
	dir := t.TempDir()
	writeSecret(t, dir, "BETTER_AUTH_SECRET", "auth")
	writeSecret(t, dir, "EXECUTOR_SECRET_KEY", "key")
	writeSecret(t, dir, "OP_SERVICE_ACCOUNT_TOKEN", "ops-token")
	got, err := readSecrets(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got["BETTER_AUTH_SECRET"] != "auth" || got["EXECUTOR_SECRET_KEY"] != "key" || got["OP_SERVICE_ACCOUNT_TOKEN"] != "ops-token" {
		t.Fatal("wrong values")
	}
	for _, name := range secretNames {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Fatalf("%s was removed: %v", name, err)
		}
	}
}

func TestReadSecretsRejectsPartialHandoff(t *testing.T) {
	dir := t.TempDir()
	writeSecret(t, dir, "BETTER_AUTH_SECRET", "auth")
	if _, err := readSecrets(dir); err == nil {
		t.Fatal("expected missing handoff rejection")
	}
}

func TestReadSecretsRejectsEmptyValue(t *testing.T) {
	dir := t.TempDir()
	writeSecret(t, dir, "BETTER_AUTH_SECRET", " \n")
	writeSecret(t, dir, "EXECUTOR_SECRET_KEY", "key")
	writeSecret(t, dir, "OP_SERVICE_ACCOUNT_TOKEN", "ops-token")
	if _, err := readSecrets(dir); err == nil {
		t.Fatal("expected empty handoff rejection")
	}
}

func TestWaitForSecretsIsBoundedForPartialHandoff(t *testing.T) {
	dir := t.TempDir()
	writeSecret(t, dir, "BETTER_AUTH_SECRET", "auth")
	started := time.Now()
	if _, err := waitForSecrets(dir, 20*time.Millisecond); err == nil {
		t.Fatal("expected timeout rejection")
	}
	if time.Since(started) > time.Second {
		t.Fatal("bounded wait exceeded")
	}
}

func TestExecutorCommandMatchesPinnedBaseImageCommand(t *testing.T) {
	path, args := executorCommand()
	if path != "/usr/local/bin/bun" {
		t.Fatalf("unexpected bun path %q", path)
	}
	want := []string{"bun", "run", "dist-server/serve.js"}
	if len(args) != len(want) {
		t.Fatalf("unexpected args: %#v", args)
	}
	for i := range want {
		if args[i] != want[i] {
			t.Fatalf("arg %d = %q, want %q", i, args[i], want[i])
		}
	}
}
