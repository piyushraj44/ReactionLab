import { request } from './request.js'

export function extractReaction(file, signal) {
  const body = new FormData()
  body.append('file', file)
  return request('/api/extract', { method: 'POST', body }, signal)
}
