// SPDX-License-Identifier: BSD-3-Clause

package main

import (
	"context"
	"net"
	"net/netip"
	"os"
	"slices"
	"testing"
)

type fixedResolver struct{ addresses []netip.Addr }

func (r fixedResolver) LookupNetIP(context.Context, string, string) ([]netip.Addr, error) {
	return r.addresses, nil
}

type recordingDialer struct{ addresses []string }

func (d *recordingDialer) DialContext(_ context.Context, _, address string) (net.Conn, error) {
	d.addresses = append(d.addresses, address)
	client, server := net.Pipe()
	go server.Close()
	return client, nil
}

func TestPublicPolicyPermittedIP(t *testing.T) {
	policy := publicPolicy()
	blocked := []string{"127.0.0.1", "10.42.10.53", "172.20.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "::1", "fd00::1", "fe80::1", "192.0.2.1"} // public-safety: allow=rfc1918-ipv4 reason=negative-test
	for _, value := range blocked {
		if policy.permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected %s to be blocked", value)
		}
	}
	for _, value := range []string{"1.1.1.1", "8.8.8.8", "2606:4700:4700::1111"} {
		if !policy.permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected %s to be permitted", value)
		}
	}
}

func TestNormalizedAddress(t *testing.T) {
	policy := publicPolicy()
	if _, _, err := policy.normalizedAddress("example.com:22", "443"); err == nil {
		t.Fatal("expected port 22 to be blocked")
	}
	host, port, err := policy.normalizedAddress("example.com", "443")
	if err != nil || host != "example.com" || port != "443" {
		t.Fatalf("unexpected normalized address: %q %q %v", host, port, err)
	}
}

func TestResolvePublicRejectsPrivateOnlyDNS(t *testing.T) {
	p := &proxy{resolver: fixedResolver{addresses: []netip.Addr{netip.MustParseAddr("127.0.0.1"), netip.MustParseAddr("10.42.10.53")}}, policy: publicPolicy()} // public-safety: allow=rfc1918-ipv4 reason=negative-test
	if _, err := p.resolvePermitted(context.Background(), "rebind.invalid"); err == nil {
		t.Fatal("expected private-only DNS result to be rejected")
	}
}

func TestDialValidatedPinsResolvedPublicIP(t *testing.T) {
	dialer := &recordingDialer{}
	p := &proxy{
		resolver: fixedResolver{addresses: []netip.Addr{netip.MustParseAddr("127.0.0.1"), netip.MustParseAddr("1.1.1.1")}},
		dialer:   dialer,
		policy:   publicPolicy(),
	}
	connection, err := p.dialValidated(context.Background(), "tcp", "rebind.invalid:443")
	if err != nil {
		t.Fatal(err)
	}
	connection.Close()
	if !slices.Equal(dialer.addresses, []string{"1.1.1.1:443"}) {
		t.Fatalf("dialer must receive only the validated literal public IP, got %v", dialer.addresses)
	}
}

func TestDialValidatedRejectsBlockedLiteralWithoutDNS(t *testing.T) {
	dialer := &recordingDialer{}
	p := &proxy{resolver: fixedResolver{}, dialer: dialer, policy: publicPolicy()}
	if _, err := p.dialValidated(context.Background(), "tcp", "169.254.169.254:80"); err == nil {
		t.Fatal("expected metadata address to be rejected")
	}
	if len(dialer.addresses) != 0 {
		t.Fatalf("blocked literal reached dialer: %v", dialer.addresses)
	}
}

func TestInternalPolicyAllowsOnlyConfiguredPrivateDestinations(t *testing.T) {
	prefixes, err := parseInternalPrefixes("10.42.0.0/16,100.96.0.0/11") // public-safety: allow=rfc1918-ipv4 reason=synthetic-policy-test
	if err != nil {
		t.Fatal(err)
	}
	ports, err := parseInternalPorts("443,8006")
	if err != nil {
		t.Fatal(err)
	}
	policy := destinationPolicy{mode: proxyModeInternal, allowedPrefixes: prefixes, allowedPorts: ports}
	for _, value := range []string{"10.42.10.53", "100.100.100.100"} { // public-safety: allow=rfc1918-ipv4 reason=synthetic-policy-test
		if !policy.permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected configured internal address %s to be permitted", value)
		}
	}
	for _, value := range []string{"1.1.1.1", "10.43.0.1", "127.0.0.1", "169.254.169.254"} { // public-safety: allow=rfc1918-ipv4 reason=negative-test
		if policy.permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected unconfigured address %s to be blocked", value)
		}
	}
	if !policy.permittedPort("8006") || policy.permittedPort("22") {
		t.Fatal("internal port allowlist was not enforced")
	}
}

func TestInternalPolicyRejectsPublicAndSpecialCIDRs(t *testing.T) {
	for _, value := range []string{"0.0.0.0/0", "127.0.0.0/8", "169.254.0.0/16", "192.0.2.0/24"} {
		if _, err := parseInternalPrefixes(value); err == nil {
			t.Fatalf("expected %s to be rejected", value)
		}
	}
}

func TestInternalDialPinsAllowedAddress(t *testing.T) {
	prefixes, err := parseInternalPrefixes("10.42.0.0/16") // public-safety: allow=rfc1918-ipv4 reason=synthetic-policy-test
	if err != nil {
		t.Fatal(err)
	}
	dialer := &recordingDialer{}
	p := &proxy{
		resolver: fixedResolver{addresses: []netip.Addr{netip.MustParseAddr("1.1.1.1"), netip.MustParseAddr("10.42.10.53")}}, // public-safety: allow=rfc1918-ipv4 reason=synthetic-policy-test
		dialer:   dialer,
		policy: destinationPolicy{
			mode:            proxyModeInternal,
			allowedPrefixes: prefixes,
			allowedPorts:    map[string]struct{}{"443": {}},
		},
	}
	connection, err := p.dialValidated(context.Background(), "tcp", "internal.example.test:443")
	if err != nil {
		t.Fatal(err)
	}
	connection.Close()
	if !slices.Equal(dialer.addresses, []string{"10.42.10.53:443"}) { // public-safety: allow=rfc1918-ipv4 reason=synthetic-policy-test
		t.Fatalf("dialer must receive only the configured internal IP, got %v", dialer.addresses)
	}
}

func TestPolicyFromEnvironmentFailsClosed(t *testing.T) {
	t.Setenv("PANTHEON_PROXY_MODE", proxyModeInternal)
	t.Setenv("PANTHEON_PROXY_ALLOWED_CIDRS", "")
	t.Setenv("PANTHEON_PROXY_ALLOWED_PORTS", "443")
	if _, err := policyFromEnvironment(os.Getenv); err == nil {
		t.Fatal("expected empty internal prefix configuration to fail")
	}
	t.Setenv("PANTHEON_PROXY_MODE", proxyModePublic)
	t.Setenv("PANTHEON_PROXY_ALLOWED_CIDRS", "10.0.0.0/8") // public-safety: allow=rfc1918-ipv4 reason=negative-test
	if _, err := policyFromEnvironment(os.Getenv); err == nil {
		t.Fatal("expected public destination override to fail")
	}
}
