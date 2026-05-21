export function createAuthProviderId() {
  return globalThis.crypto?.randomUUID?.() || `auth-provider-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function createEmptyAuthProvider() {
  return {
    id: createAuthProviderId(),
    type: 'oidc',
    name: '',
    enabled: true,
    issuer_url: '',
    client_id: '',
    client_secret: '',
    scopes: ['openid', 'profile', 'email'],
    discovery_enabled: true,
    authorization_endpoint: '',
    token_endpoint: '',
    userinfo_endpoint: '',
    jwks_uri: '',
    claim_mappings: {
      email: 'email',
      username: 'preferred_username',
      groups: 'groups',
    },
    admin_emails: [],
    allow_local_fallback: true,
  }
}

export function assignAuthProviderForm(form, provider, scopesInput, adminEmailsInput) {
  form.id = provider.id
  form.type = provider.type || 'oidc'
  form.name = provider.name || ''
  form.enabled = provider.enabled !== false
  form.issuer_url = provider.issuer_url || ''
  form.client_id = provider.client_id || ''
  form.client_secret = provider.client_secret || ''
  form.scopes = Array.isArray(provider.scopes) ? [...provider.scopes] : ['openid', 'profile', 'email']
  form.discovery_enabled = provider.discovery_enabled !== false
  form.authorization_endpoint = provider.authorization_endpoint || ''
  form.token_endpoint = provider.token_endpoint || ''
  form.userinfo_endpoint = provider.userinfo_endpoint || ''
  form.jwks_uri = provider.jwks_uri || ''
  form.claim_mappings = Object.assign({
    email: 'email',
    username: 'preferred_username',
    groups: 'groups',
  }, provider.claim_mappings || {})
  form.admin_emails = Array.isArray(provider.admin_emails) ? [...provider.admin_emails] : []
  form.allow_local_fallback = provider.allow_local_fallback !== false
  scopesInput.value = form.scopes.join(', ')
  adminEmailsInput.value = form.admin_emails.join(', ')
}

export function cloneAuthProvider(provider) {
  return {
    ...provider,
    scopes: [...(provider.scopes || [])],
    admin_emails: [...(provider.admin_emails || [])],
    claim_mappings: { ...(provider.claim_mappings || {}) },
  }
}

export function cloneAuthProviderList(providers) {
  return providers.map((provider) => cloneAuthProvider(provider))
}

export function normalizeCommaSeparatedItems(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function formatAuthProviderItems(value, fallback = '') {
  return (value || []).join(', ') || fallback
}
