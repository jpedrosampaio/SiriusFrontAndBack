// Only finite public metadata may be rendered/copied as provider diagnostics.
const publicFields = new Set(['model', 'store', 'contents', 'contents.parts', 'systemInstruction', 'systemInstruction.parts',
  'tools', 'toolConfig', 'generationConfig', 'generationConfig.maxOutputTokens', 'generationConfig.responseFormat',
  'generationConfig.responseFormat.text', 'generationConfig.responseFormat.text.mimeType', 'generationConfig.responseFormat.text.schema',
  'generationConfig.responseMimeType', 'generationConfig.responseJsonSchema', 'generationConfig.responseSchema',
  'messages', 'max_completion_tokens', 'response_format', 'response_format.json_schema',
  'response_format.json_schema.schema', 'response_format.json_schema.strict']);
const publicStatuses = new Set(['INVALID_ARGUMENT', 'FAILED_PRECONDITION', 'OUT_OF_RANGE', 'UNIMPLEMENTED', 'NOT_FOUND',
  'PERMISSION_DENIED', 'UNAUTHENTICATED', 'RESOURCE_EXHAUSTED', 'UNAVAILABLE', 'INTERNAL', 'DEADLINE_EXCEEDED']);
const publicCategories = new Set(['unknown_field', 'invalid_value', 'missing_field', 'unsupported', 'output_validation', 'context_limit', 'unspecified']);
const publicProviderCodes = new Set(['json_validate_failed', 'model_decommissioned', 'model_not_found', 'context_length_exceeded', 'invalid_api_key', 'rate_limit_exceeded', 'tool_use_failed']);
const publicProviderTypes = new Set(['invalid_request_error', 'authentication_error', 'permission_error', 'rate_limit_error', 'server_error']);
const publicModels = new Set(['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b']);
export const rejectionCategories = { unknown_field: 'Campo não reconhecido', invalid_value: 'Valor inválido', missing_field: 'Campo obrigatório ausente', unsupported: 'Recurso não suportado', output_validation: 'Resposta gerada fora do contrato', context_limit: 'Entrada acima do limite do modelo', unspecified: 'Motivo específico não informado' };
export const analysisStages = [['inventory', 'Descoberta'], ['scope', 'Associações'], ['detail', 'Conteúdo'], ['verify', 'Comparação de fontes']];

export function stageProgress(rows, kind) {
  const active = (Array.isArray(rows) ? rows : []).filter(row => row.kind === kind && row.status !== 'split' && Number.isInteger(row.units) && row.units > 0);
  const total = active.reduce((n, row) => n + row.units, 0), done = active.filter(row => row.status === 'completed').reduce((n, row) => n + row.units, 0);
  return { total, done, pending: total - done };
}

export function publicDiagnostic(item) {
  const failure = item?.failure || {}, rejection = failure.provider_rejection || {}, result = {};
  if (typeof item?.reference === 'string' && /^[a-f0-9-]{36}$/i.test(item.reference)) result.reference = item.reference;
  if (typeof item?.unit_id === 'string' && /^[a-f0-9-]{36}$/i.test(item.unit_id)) result.unit_id = item.unit_id;
  if (analysisStages.some(([kind]) => kind === item?.kind)) result.stage = item.kind;
  if (['gemini', 'groq'].includes(item?.last_observed_model?.provider)) result.provider = item.last_observed_model.provider;
  const model = item?.last_observed_model?.model;
  if (publicModels.has(model)) result.model = model;
  if (Number.isInteger(failure.http_status) && failure.http_status >= 100 && failure.http_status <= 599) result.http_status = failure.http_status;
  if (publicStatuses.has(rejection.status)) result.provider_status = rejection.status;
  if (publicProviderCodes.has(rejection.provider_code)) result.provider_code = rejection.provider_code;
  if (publicProviderTypes.has(rejection.provider_type)) result.provider_type = rejection.provider_type;
  if (publicCategories.has(rejection.category)) result.category = rejection.category;
  result.fields = [...new Set((Array.isArray(rejection.fields) ? rejection.fields : []).slice(0, 8).filter(value => publicFields.has(value)))];
  if (['gemini_response_format', 'groq_json_schema'].includes(failure.request_format)) result.request_format = failure.request_format;
  if (typeof failure.schema_sha256 === 'string' && /^[a-f0-9]{64}$/.test(failure.schema_sha256)) result.schema_sha256 = failure.schema_sha256;
  if (Number.isInteger(failure.schema_bytes) && failure.schema_bytes > 0 && failure.schema_bytes <= 60000) result.schema_bytes = failure.schema_bytes;
  if (Number.isInteger(item?.provider_calls) && item.provider_calls >= 0) result.unit_reserved_calls = item.provider_calls;
  return result;
}
