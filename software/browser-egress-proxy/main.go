// SPDX-License-Identifier: BSD-3-Clause

package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/netip"
	"os"
	"strings"
	"time"
)

var blockedPrefixes = mustPrefixes(
	"0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", // public-safety: allow=rfc1918-ipv4 reason=deny-list
	"169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", // public-safety: allow=rfc1918-ipv4 reason=deny-list
	"192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15", // public-safety: allow=rfc1918-ipv4 reason=deny-list
	"198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
	"::/128", "::1/128", "64:ff9b::/96", "100::/64", "2001:db8::/32",
	"fc00::/7", "fe80::/10", "ff00::/8",
)

type proxy struct {
	resolver netIPResolver
	dialer   contextDialer
	client   http.Client
}

type netIPResolver interface {
	LookupNetIP(context.Context, string, string) ([]netip.Addr, error)
}

type contextDialer interface {
	DialContext(context.Context, string, string) (net.Conn, error)
}

func mustPrefixes(values ...string) []netip.Prefix {
	result := make([]netip.Prefix, 0, len(values))
	for _, value := range values {
		result = append(result, netip.MustParsePrefix(value))
	}
	return result
}

func permittedIP(ip netip.Addr) bool {
	if ip.Is4In6() {
		ip = ip.Unmap()
	}
	if !ip.IsValid() || !ip.IsGlobalUnicast() {
		return false
	}
	for _, prefix := range blockedPrefixes {
		if prefix.Contains(ip) {
			return false
		}
	}
	return true
}

func permittedPort(port string) bool {
	return port == "80" || port == "443"
}

func normalizedAddress(hostport, defaultPort string) (string, string, error) {
	host, port, err := net.SplitHostPort(hostport)
	if err != nil {
		if strings.Contains(err.Error(), "missing port") {
			host, port = hostport, defaultPort
		} else {
			return "", "", err
		}
	}
	host = strings.TrimSuffix(strings.TrimSpace(host), ".")
	if host == "" || !permittedPort(port) {
		return "", "", errors.New("destination is not permitted")
	}
	return host, port, nil
}

func (p *proxy) resolvePublic(ctx context.Context, host string) ([]netip.Addr, error) {
	if literal, err := netip.ParseAddr(host); err == nil {
		if !permittedIP(literal) {
			return nil, errors.New("destination address is not permitted")
		}
		return []netip.Addr{literal.Unmap()}, nil
	}
	addresses, err := p.resolver.LookupNetIP(ctx, "ip", host)
	if err != nil {
		return nil, err
	}
	public := make([]netip.Addr, 0, len(addresses))
	for _, address := range addresses {
		address = address.Unmap()
		if permittedIP(address) {
			public = append(public, address)
		}
	}
	if len(public) == 0 {
		return nil, errors.New("destination resolved only to blocked addresses")
	}
	return public, nil
}

func (p *proxy) dialValidated(ctx context.Context, network, address string) (net.Conn, error) {
	host, port, err := normalizedAddress(address, "443")
	if err != nil {
		return nil, err
	}
	addresses, err := p.resolvePublic(ctx, host)
	if err != nil {
		return nil, err
	}
	var last error
	for _, address := range addresses {
		conn, dialErr := p.dialer.DialContext(ctx, network, net.JoinHostPort(address.String(), port))
		if dialErr == nil {
			return conn, nil
		}
		last = dialErr
	}
	return nil, last
}

func (p *proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodConnect {
		p.connect(w, r)
		return
	}
	if r.URL == nil || (r.URL.Scheme != "http" && r.URL.Scheme != "https") {
		http.Error(w, "absolute HTTP(S) URL required", http.StatusBadRequest)
		return
	}
	host, _, err := normalizedAddress(r.URL.Host, map[bool]string{true: "443", false: "80"}[r.URL.Scheme == "https"])
	if err != nil {
		http.Error(w, "destination is not permitted", http.StatusForbidden)
		return
	}
	request := r.Clone(r.Context())
	request.RequestURI = ""
	request.Header.Del("Proxy-Authorization")
	request.Header.Del("Proxy-Connection")
	response, err := p.client.Do(request)
	if err != nil {
		slog.Warn("proxy request failed", "host", host, "error", err.Error())
		http.Error(w, "upstream unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()
	for key, values := range response.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}
	w.WriteHeader(response.StatusCode)
	_, _ = io.Copy(w, io.LimitReader(response.Body, 32<<20))
}

func (p *proxy) connect(w http.ResponseWriter, r *http.Request) {
	host, port, err := normalizedAddress(r.Host, "443")
	if err != nil {
		http.Error(w, "destination is not permitted", http.StatusForbidden)
		return
	}
	upstream, err := p.dialValidated(r.Context(), "tcp", net.JoinHostPort(host, port))
	if err != nil {
		slog.Warn("proxy connect failed", "host", host, "port", port, "error", err.Error())
		http.Error(w, "upstream unavailable", http.StatusBadGateway)
		return
	}
	hijacker, ok := w.(http.Hijacker)
	if !ok {
		upstream.Close()
		http.Error(w, "tunnelling unavailable", http.StatusInternalServerError)
		return
	}
	downstream, _, err := hijacker.Hijack()
	if err != nil {
		upstream.Close()
		return
	}
	_, _ = downstream.Write([]byte("HTTP/1.1 200 Connection Established\r\n\r\n"))
	go tunnel(upstream, downstream)
	go tunnel(downstream, upstream)
}

func tunnel(dst, src net.Conn) {
	defer dst.Close()
	defer src.Close()
	_, _ = io.Copy(dst, io.LimitReader(src, 64<<20))
}

func main() {
	p := &proxy{resolver: net.DefaultResolver, dialer: &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}}
	p.client = http.Client{Transport: &http.Transport{Proxy: nil, DialContext: p.dialValidated, TLSHandshakeTimeout: 10 * time.Second, ResponseHeaderTimeout: 20 * time.Second}, Timeout: 60 * time.Second}
	server := &http.Server{Addr: ":8080", Handler: p, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 32 << 10}
	slog.Info("browser egress proxy listening", "address", server.Addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
