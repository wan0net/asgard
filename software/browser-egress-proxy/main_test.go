// SPDX-License-Identifier: BSD-3-Clause

package main

import (
	"context"
	"net"
	"net/netip"
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

func TestPermittedIP(t *testing.T) {
	blocked := []string{"127.0.0.1", "10.42.10.53", "172.20.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "::1", "fd00::1", "fe80::1", "192.0.2.1"} // public-safety: allow=rfc1918-ipv4 reason=negative-test
	for _, value := range blocked {
		if permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected %s to be blocked", value)
		}
	}
	for _, value := range []string{"1.1.1.1", "8.8.8.8", "2606:4700:4700::1111"} {
		if !permittedIP(netip.MustParseAddr(value)) {
			t.Fatalf("expected %s to be permitted", value)
		}
	}
}

func TestNormalizedAddress(t *testing.T) {
	if _, _, err := normalizedAddress("example.com:22", "443"); err == nil {
		t.Fatal("expected port 22 to be blocked")
	}
	host, port, err := normalizedAddress("example.com", "443")
	if err != nil || host != "example.com" || port != "443" {
		t.Fatalf("unexpected normalized address: %q %q %v", host, port, err)
	}
}

func TestResolvePublicRejectsPrivateOnlyDNS(t *testing.T) {
	p := &proxy{resolver: fixedResolver{addresses: []netip.Addr{netip.MustParseAddr("127.0.0.1"), netip.MustParseAddr("10.42.10.53")}}} // public-safety: allow=rfc1918-ipv4 reason=negative-test
	if _, err := p.resolvePublic(context.Background(), "rebind.invalid"); err == nil {
		t.Fatal("expected private-only DNS result to be rejected")
	}
}

func TestDialValidatedPinsResolvedPublicIP(t *testing.T) {
	dialer := &recordingDialer{}
	p := &proxy{
		resolver: fixedResolver{addresses: []netip.Addr{netip.MustParseAddr("127.0.0.1"), netip.MustParseAddr("1.1.1.1")}},
		dialer:   dialer,
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
	p := &proxy{resolver: fixedResolver{}, dialer: dialer}
	if _, err := p.dialValidated(context.Background(), "tcp", "169.254.169.254:80"); err == nil {
		t.Fatal("expected metadata address to be rejected")
	}
	if len(dialer.addresses) != 0 {
		t.Fatalf("blocked literal reached dialer: %v", dialer.addresses)
	}
}
