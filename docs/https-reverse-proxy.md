# HTTPS Reverse Proxy Deployment

Aethera does not terminate HTTPS itself. For production `https://` access, deploy an external reverse proxy such as Nginx, Caddy, Traefik, or Nginx Proxy Manager.

The application only guarantees correct behavior behind an HTTPS-aware reverse proxy:

- When the request includes `X-Forwarded-Proto: https`, login and initialization APIs issue `Secure` cookies automatically.
- When the application is accessed directly over local HTTP, cookies are not marked `Secure`.

## Minimum Reverse Proxy Requirements

When forwarding requests to Aethera, preserve at least these headers:

- `Host`
- `X-Forwarded-For`
- `X-Forwarded-Proto`

If `X-Forwarded-Proto` is missing, Aethera cannot know whether the original client request used HTTPS. Authentication cookies will not automatically switch to `Secure`.

## Minimal Nginx Example

```nginx
server {
  listen 80;
  server_name aethera.example.com;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name aethera.example.com;

  ssl_certificate /path/to/fullchain.pem;
  ssl_certificate_key /path/to/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:8173;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
  }
}
```

The `8173` port is only an example. Replace it with `AETHERA_HTTP_PORT` from your deployment.

## Scope

Currently supported:

- root-domain deployment
- HTTPS protocol detection behind a reverse proxy
- automatic `Secure` cookie behavior based on the original request protocol

Currently not covered:

- TLS termination inside the application
- subpath deployment
- automatic certificate issuance

## Operational Notes

- Keep the proxy and Aethera on a trusted network when forwarding protocol headers.
- Do not expose both the raw HTTP service and the HTTPS proxy as equal production entrypoints.
- If login works over HTTP but fails over HTTPS, first inspect whether `X-Forwarded-Proto` reaches the backend as `https`.
- If the browser rejects cookies, verify the external URL, scheme, and proxy headers before changing application code.
