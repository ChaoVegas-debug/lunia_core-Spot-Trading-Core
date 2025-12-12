import { apiFetch, type ClientOptions } from './client';
import type {
  ActivityResponse,
  ArbitrageOpportunities,
  AuditEvent,
  BalancesResponse,
  CapitalSnapshot,
  FuturesTradeRequest,
  FeatureFlag,
  HealthResponse,
  LimitEntry,
  LoginResponse,
  LogsResponse,
  OpsState,
  PortfolioAggregate,
  PortfolioSnapshot,
  ResearchResponse,
  SignalPayload,
  SignalsEnvelope,
  SignalsFeed,
  SpotRiskConfig,
  StatusSnapshot,
  StrategyWeightsRequest,
  TradeRequest,
  UserProfile
} from './types';

export function getHealth(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<HealthResponse>('/health', { method: 'GET', signal }, client);
}

export function getStatus(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<StatusSnapshot>('/status', { method: 'GET', signal }, client);
}

export function postLogin(body: { email: string; password: string }, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<LoginResponse>('/auth/login', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function getCurrentUser(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<UserProfile>('/auth/me', { method: 'GET', signal }, client);
}

export function getActivity(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<ActivityResponse>('/ops/activity', { method: 'GET', signal }, client);
}

export function getOpsState(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<OpsState>('/ops/state', { method: 'GET', signal }, client);
}

export function getPortfolio(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<PortfolioSnapshot>('/portfolio', { method: 'GET', signal }, client);
}

export function getPortfolioSnapshot(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<PortfolioAggregate>('/portfolio/snapshot', { method: 'GET', signal }, client);
}

export function getBalances(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<BalancesResponse>('/balances', { method: 'GET', signal }, client);
}

export function getArbOpps(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<ArbitrageOpportunities>('/arbitrage/opps', { method: 'GET', signal }, client);
}

export function getSignalsFeed(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<SignalsFeed>('/ai/signals', { method: 'GET', signal }, client);
}

export function getRisk(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<SpotRiskConfig>('/spot/risk', { method: 'GET', signal }, client);
}

export function getCapital(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<CapitalSnapshot>('/ops/capital', { method: 'GET', signal }, client);
}

export function getLogs(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<LogsResponse>('/ops/logs', { method: 'GET', signal }, client);
}

export function getAudit(signal: AbortSignal, client?: ClientOptions, params?: { limit?: number; actor?: string; action?: string; result?: string }) {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.actor) query.set('actor', params.actor);
  if (params?.action) query.set('action', params.action);
  if (params?.result) query.set('result', params.result);
  const path = `/admin/audit${query.toString() ? `?${query.toString()}` : ''}`;
  return apiFetch<{ items: AuditEvent[] }>(path, { method: 'GET', signal }, client);
}

export function getUsers(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<{ items: UserProfile[] }>('/admin/users', { method: 'GET', signal }, client);
}

export function createUser(body: { email: string; password: string; role: string }, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<UserProfile>('/admin/users', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function updateUser(userId: number, body: Partial<UserProfile>, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<UserProfile>(`/admin/users/${userId}`, { method: 'PUT', signal, body: JSON.stringify(body) }, client);
}

export function getFlags(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<{ items: FeatureFlag[] }>('/admin/flags', { method: 'GET', signal }, client);
}

export function updateFlag(key: string, body: { value: unknown }, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<FeatureFlag>(`/admin/flags/${key}`, { method: 'PUT', signal, body: JSON.stringify(body) }, client);
}

export function getLimits(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<{ items: LimitEntry[] }>('/admin/limits', { method: 'GET', signal }, client);
}

export function upsertLimit(body: { scope: string; subject?: string | null; key: string; value: unknown }, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<LimitEntry>('/admin/limits', { method: 'PUT', signal, body: JSON.stringify(body) }, client);
}

export function postSpotTrade(body: TradeRequest, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/trade/spot/demo', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postFuturesTrade(body: FuturesTradeRequest, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/trade/futures/demo', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postSignal(body: SignalPayload | SignalsEnvelope, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/signal', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postAutoOn(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ops/auto_on', { method: 'POST', signal }, client);
}

export function postAutoOff(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ops/auto_off', { method: 'POST', signal }, client);
}

export function postStopAll(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ops/stop_all', { method: 'POST', signal }, client);
}

export function postStartAll(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ops/start_all', { method: 'POST', signal }, client);
}

export function postOpsState(body: Partial<OpsState>, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ops/state', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postRisk(body: SpotRiskConfig, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/spot/risk', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postStrategyWeights(body: StrategyWeightsRequest, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/spot/strategies', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postResearch(body: Record<string, unknown>, signal: AbortSignal, client?: ClientOptions) {
  return apiFetch<ResearchResponse>('/ai/research/analyze_now', { method: 'POST', signal, body: JSON.stringify(body) }, client);
}

export function postAiRun(signal: AbortSignal, client?: ClientOptions) {
  return apiFetch('/ai/run', { method: 'POST', signal }, client);
}
