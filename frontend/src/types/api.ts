// Wire contract: contracts/openapi.yaml. Health intentionally has no business envelope.
export interface HealthResponse { status: 'UP'; timestamp: string }
export interface City { id: string; name: string }
export interface CityMeta {
  requestId: string
  dataAsOf: null
  sourceType: 'dev_seed'
  datasetId: 'dev-seed-cities-v1'
}
export interface CitiesResponse {
  code: 'OK'
  message: string
  data: City[]
  meta: CityMeta
}
export type ErrorCode = 'BAD_REQUEST' | 'NOT_FOUND' | 'METHOD_NOT_ALLOWED'
  | 'NOT_ACCEPTABLE' | 'INTERNAL_ERROR' | 'SERVICE_UNAVAILABLE'
export interface ErrorResponse {
  code: ErrorCode
  message: string
  data: null
  meta: { requestId: string; dataAsOf: null; sourceType: null; datasetId: null }
}
