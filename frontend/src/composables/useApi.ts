/**
 * Typed fetch wrapper for /api/v1/ endpoints.
 *
 * Auth: uses session cookie (SameSite=Strict) — no manual token needed for
 * browser requests. Bearer tokens are for external consumers only.
 *
 * Errors: throws ApiError with status code and detail message.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`${status}: ${detail}`)
    this.name = 'ApiError'
  }
}

type QueryParams = Record<string, string | number | boolean | undefined>

interface RequestOptions {
  params?: QueryParams
  signal?: AbortSignal
}

function buildUrl(path: string, params?: QueryParams): string {
  const url = new URL(path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value))
      }
    }
  }
  return url.toString()
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const url = buildUrl(`/api/v1${path}`, options?.params)

  const headers: Record<string, string> = {
    Accept: 'application/json',
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
    signal: options?.signal,
  })

  if (!response.ok) {
    // Try to extract detail from JSON error response
    let detail = response.statusText
    try {
      const data = await response.json()
      if (data.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      // Response wasn't JSON — use statusText
    }
    throw new ApiError(response.status, detail)
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function useApi() {
  return {
    get<T>(path: string, params?: QueryParams, options?: { signal?: AbortSignal }): Promise<T> {
      return request<T>('GET', path, undefined, { params, signal: options?.signal })
    },

    post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
      return request<T>('POST', path, body, options)
    },

    put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
      return request<T>('PUT', path, body, options)
    },

    delete<T>(path: string, options?: RequestOptions): Promise<T> {
      return request<T>('DELETE', path, undefined, options)
    },
  }
}
