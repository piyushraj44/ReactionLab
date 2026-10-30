import { request } from './request.js'

export function predictReaction({ reactants, conditions }, signal) {
  return request(
    '/api/predict',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reactants, conditions: conditions || '' }),
    },
    signal,
  )
}
