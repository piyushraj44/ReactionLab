export const GENERIC = 'Something went wrong. Please try again.'

// Shared fetch + error handling. Returns parsed JSON or throws Error(detail).
export async function request(url, init, signal) {
  let res
  try {
    res = await fetch(url, { ...init, signal })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('Could not reach the server. Check your connection and try again.')
  }

  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : null
    throw new Error(detail || GENERIC)
  }
  if (!data || typeof data !== 'object') throw new Error(GENERIC)
  return data
}
